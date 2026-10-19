#!/usr/bin/env python3
"""A v2 stage must remain owned across source inventory revisions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECT = (
    'AGENTS.md', 'config/codex/AGENTS.md', 'config/codex/config.toml.template',
    'docs/CAPABILITY-MAP.md', 'docs/CONNECTOR-FABRIC.md',
    'docs/AGENT-OPERATING-CONTRACT.md', 'manifests/skills.yaml',
    'manifests/mcp.yaml', 'manifests/environment.yaml',
    'manifests/connector-capabilities.json',
    'manifests/connector-hosted-template.json', 'bin/staged-workstation',
    'lib/staged_workstation_receipt.py',
)


class StageAcrossCheckouts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='stage-upgrade-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.stage = self.base / 'stage'
        self.v1, self.v2 = self.base / 'checkout-v1', self.base / 'checkout-v2'
        for checkout in (self.v1, self.v2):
            for name in DIRECT:
                destination = checkout / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, destination)
            shutil.copytree(ROOT / 'skills/workstation-operations',
                            checkout / 'skills/workstation-operations')
        (self.v1 / 'skills/workstation-operations/old').mkdir()
        (self.v1 / 'skills/workstation-operations/old/note.txt').write_text('old approved source\n')
        (self.v2 / 'skills/workstation-operations/new').mkdir()
        (self.v2 / 'skills/workstation-operations/new/note.txt').write_text('new approved source\n')
        self.env = dict(os.environ, HOME=str(self.home), WORKSTATION_STAGE_ROOT=str(self.stage))

    def run_stage(self, checkout, operation):
        return subprocess.run(['bash', str(checkout / 'bin/staged-workstation'), operation],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def old_stage(self):
        result = self.run_stage(self.v1, 'reconcile')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.stage / 'skills/workstation-operations/old/note.txt').is_file())

    def test_rollback_uses_old_receipt_inventory(self):
        self.old_stage()
        result = self.run_stage(self.v2, 'rollback')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.stage.exists())

    def test_reconcile_removes_old_and_adds_new(self):
        self.old_stage()
        result = self.run_stage(self.v2, 'reconcile')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.stage / 'skills/workstation-operations/old').exists())
        new = 'skills/workstation-operations/new/note.txt'
        self.assertEqual((self.stage / new).read_text(), 'new approved source\n')
        receipt = json.loads((self.stage / 'receipt.json').read_text())
        self.assertIn(new, receipt['managed_sha256'])
        self.assertNotIn('skills/workstation-operations/old/note.txt', receipt['managed_sha256'])

    def test_tamper_unknown_and_symlink_still_refuse(self):
        for kind in ('tamper', 'unknown', 'unknown-dir', 'symlink'):
            with self.subTest(kind=kind):
                self.old_stage()
                target = self.stage / 'skills/workstation-operations/old/note.txt'
                if kind == 'tamper':
                    target.write_text('unapproved edit\n')
                elif kind == 'unknown':
                    (self.stage / 'skills/workstation-operations/unowned.txt').write_text('unknown\n')
                elif kind == 'unknown-dir':
                    (self.stage / 'skills/workstation-operations/unowned').mkdir()
                else:
                    target.unlink()
                    target.symlink_to(self.base / 'outside')
                for operation in ('rollback', 'reconcile'):
                    result = self.run_stage(self.v2, operation)
                    self.assertEqual(result.returncode, 64, result.stderr)
                    self.assertTrue(self.stage.exists())
                if kind == 'unknown':
                    (self.stage / 'skills/workstation-operations/unowned.txt').unlink()
                elif kind == 'unknown-dir':
                    (self.stage / 'skills/workstation-operations/unowned').rmdir()
                else:
                    target.unlink()
                    target.write_text('old approved source\n')
                self.assertEqual(self.run_stage(self.v1, 'rollback').returncode, 0)

    def test_receipt_path_traversal_refuses(self):
        self.old_stage()
        receipt_path = self.stage / 'receipt.json'
        original = receipt_path.read_bytes()
        receipt = json.loads(original)
        receipt['managed_sha256']['skills/workstation-operations/../../outside'] = '0' * 64
        receipt_path.write_text(json.dumps(receipt))
        for operation in ('rollback', 'reconcile'):
            result = self.run_stage(self.v2, operation)
            self.assertEqual(result.returncode, 64, result.stderr)
        self.assertTrue((self.stage / 'skills/workstation-operations/old/note.txt').is_file())
        receipt_path.write_bytes(original)
        self.assertEqual(self.run_stage(self.v1, 'rollback').returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
