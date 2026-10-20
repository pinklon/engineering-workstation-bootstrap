#!/usr/bin/env python3
"""Disposable-home proof for the managed instruction-only transition."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'lib/workstation-recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
instruction_spec = importlib.util.spec_from_file_location('instructions', ROOT / 'lib/workstation-instructions.py')
instructions = importlib.util.module_from_spec(instruction_spec)
instruction_spec.loader.exec_module(instructions)
CATALOG = {
    'schemaVersion': 'ghostmesh-presentation-aliases.v1',
    'sourceIssue': 'pinklon/shareplane-control-tower#1056',
    'authorityRegistry': 'architecture/mesh-identity-registry.v1.json',
    'presentationOnly': True,
    'aliases': [
        {'alias': 'segfault', 'target': 'ChatGPT architecture/reasoning partner', 'kind': 'agent'},
        {'alias': 'syscall', 'target': 'Codex engineering agent', 'kind': 'agent'},
        {'alias': 'phorse', 'target': 'existing Pale Horse coordinator', 'kind': 'agent'},
        {'alias': 'GhostMesh', 'target': 'overall system', 'kind': 'system'},
    ],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(*args, env=None):
    return subprocess.run(args, check=False, capture_output=True, text=True, env=env, timeout=120)


def fixture_repo(root, path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    for args in [('init', '-q'), ('config', 'user.name', 'Fixture'),
                 ('config', 'user.email', 'fixture@example.invalid'), ('add', '.'),
                 ('commit', '-qm', 'fixture')]:
        result = run('git', '-C', str(root), *args)
        if result.returncode:
            raise AssertionError(result.stderr)
    return run('git', '-C', str(root), 'rev-parse', 'HEAD').stdout.strip()


class InstructionOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='instruction-only-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / 'home'
        (self.home / '.codex').mkdir(parents=True)
        (self.home / '.codex/config.toml').write_text('model = "fixture-model"\n')
        (self.home / '.codex/AGENTS.md').write_text('original instructions\n')
        (self.home / '.zshrc').write_text('# original shell\n')
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for key in list(self.env):
            if key.startswith('WORKSTATION_FAIL') or key.startswith('WORKSTATION_INSTRUCTIONS_FAIL'):
                self.env.pop(key)
        active_contract = self.base / 'active.json'
        active_contract.write_text(json.dumps({
            'schemaVersion': 1, 'activationAuthorized': True, 'allowLiveHome': False,
            'targetHome': str(self.home), 'authorityReference': 'fixture:active',
            'version': 'fixture-active', 'manageSkillRoots': False,
        }))
        result = run('bash', str(ROOT / 'bin/workstation-activate'), '--activation-contract',
                     str(active_contract), '--home', str(self.home),
                     env=dict(self.env, WORKSTATION_TRANSACTION_ID='fixture-active'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.state = self.home / '.local/state/engineering-workstation-bootstrap'
        self.pointer = self.home / '.local/share/engineering-workstation-bootstrap/current'
        self.previous = os.readlink(self.pointer)
        self.previous_txn = (self.state / 'current-transaction').read_text().strip()
        self.prior_receipt = self.state / 'receipts/activation-fixture-active.json'
        self.prior_receipt_bytes = self.prior_receipt.read_bytes()
        self.prior_manifest = Path(json.loads(self.prior_receipt_bytes)['backupManifest'])
        self.prior_manifest_bytes = self.prior_manifest.read_bytes()
        self.link = self.home / '.codex/AGENTS.md'
        self.original_sha = digest(self.link)
        self.managed_names = [x['relativePath'] for x in json.loads(self.prior_manifest_bytes)['paths']]
        self.other_paths = {name: recovery.fingerprint(self.home / name)
                            for name in self.managed_names if name != '.codex/AGENTS.md'}

        self.wsrepo = self.base / 'workstation-source'
        self.ctrepo = self.base / 'catalog-source'
        self.wsrepo.mkdir()
        self.ctrepo.mkdir()
        self.source = 'accepted fixture instructions\n'
        ws_commit = fixture_repo(self.wsrepo, self.wsrepo / 'config/codex/AGENTS.md', self.source)
        ct_commit = fixture_repo(self.ctrepo, self.ctrepo / 'architecture/mesh-presentation-aliases.v1.json',
                                 json.dumps(CATALOG, indent=2) + '\n')
        catalog_blob = run('git', '-C', str(self.ctrepo), 'rev-parse',
                           ct_commit + ':architecture/mesh-presentation-aliases.v1.json').stdout.strip()
        self.contract = self.base / 'instructions.json'
        self.contract.write_text(json.dumps({
            'schemaVersion': 1, 'instructionOnlyAuthorized': True, 'allowLiveHome': False,
            'authorityReference': 'fixture:instruction-only', 'targetHome': str(self.home),
            'version': 'fixture-instructions', 'workstationCommit': ws_commit,
            'workstationInstructionSha256': hashlib.sha256(self.source.encode()).hexdigest(),
            'catalogCommit': ct_commit, 'catalogBlobSha1': catalog_blob,
            'expectedCurrent': self.previous, 'expectedTransaction': self.previous_txn,
            'expectedPreimageSha256': self.original_sha,
        }))
        self.txn = 'fixture-instructions'
        self.receipt = self.state / 'receipts' / ('activation-' + self.txn + '.json')

    def install(self, **extra):
        return run('bash', str(ROOT / 'bin/workstation-instructions'), 'install',
                   '--contract', str(self.contract), '--home', str(self.home),
                   '--workstation-repo', str(self.wsrepo), '--catalog-repo', str(self.ctrepo),
                   env=dict(self.env, WORKSTATION_TRANSACTION_ID=self.txn, **extra))

    def rollback(self):
        return run('bash', str(ROOT / 'bin/workstation-instructions'), 'rollback',
                   '--receipt', str(self.receipt), '--home', str(self.home), env=self.env)

    def unchanged(self):
        self.assertEqual(self.prior_receipt.read_bytes(), self.prior_receipt_bytes)
        self.assertEqual(self.prior_manifest.read_bytes(), self.prior_manifest_bytes)
        self.assertEqual({name: recovery.fingerprint(self.home / name) for name in self.other_paths},
                         self.other_paths)
        self.assertEqual(os.readlink(self.link), str(self.pointer / 'config/codex/AGENTS.md'))

    def test_install_and_receipt_bound_rollback(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt['status'], 'active')
        self.assertEqual(receipt['previousCurrent'], self.previous)
        self.assertEqual(receipt['previousTransaction'], self.previous_txn)
        self.assertEqual(receipt['preimageSha256'], self.original_sha)
        self.assertEqual(receipt['instructionSha256'], digest(self.link))
        self.assertEqual(receipt['nonInstructionTreeSha256'],
                         instructions.tree_without_instructions(Path(self.previous)))
        self.assertEqual(instructions.tree_without_instructions(Path(os.readlink(self.pointer))),
                         receipt['nonInstructionTreeSha256'])
        self.assertEqual(receipt['workstationCommit'], json.loads(self.contract.read_text())['workstationCommit'])
        self.assertEqual(receipt['catalogCommit'], json.loads(self.contract.read_text())['catalogCommit'])
        self.assertEqual(digest(receipt['rollbackEntryPoint']), receipt['rollbackWrapperSha256'])
        self.assertEqual(digest(Path(receipt['rollbackEntryPoint']).parents[1] /
                                'lib/workstation-instructions.py'), receipt['rollbackModuleSha256'])
        self.assertEqual(len(json.loads(Path(receipt['backupManifest']).read_text())['paths']), 1)
        self.assertEqual(self.link.read_text(), self.source)
        self.assertNotEqual(os.readlink(self.pointer), self.previous)
        self.assertEqual((self.state / 'current-transaction').read_text().strip(), self.txn)
        self.unchanged()
        result = self.rollback()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'rolled-back')
        self.assertEqual(os.readlink(self.pointer), self.previous)
        self.assertEqual((self.state / 'current-transaction').read_text().strip(), self.previous_txn)
        self.assertEqual(digest(self.link), self.original_sha)
        self.unchanged()

    def test_wrong_source_or_preimage_refuses_without_switch(self):
        for field, bad in [('workstationInstructionSha256', '0' * 64),
                           ('catalogBlobSha1', '0' * 40), ('expectedPreimageSha256', '0' * 64)]:
            with self.subTest(field=field):
                value = json.loads(self.contract.read_text())
                original = value[field]
                value[field] = bad
                self.contract.write_text(json.dumps(value))
                result = self.install()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(os.readlink(self.pointer), self.previous)
                self.assertEqual((self.state / 'current-transaction').read_text().strip(), self.previous_txn)
                self.assertFalse(self.receipt.exists())
                self.unchanged()
                value[field] = original
                self.contract.write_text(json.dumps(value))

    def test_failure_recovery_at_pointer_and_marker(self):
        for point in ['after-intent', 'after-pointer', 'after-marker', 'before-active']:
            with self.subTest(point=point):
                self.txn = 'fixture-' + point
                self.receipt = self.state / 'receipts' / ('activation-' + self.txn + '.json')
                result = self.install(WORKSTATION_INSTRUCTIONS_FAIL_POINT=point)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(os.readlink(self.pointer), self.previous)
                self.assertEqual((self.state / 'current-transaction').read_text().strip(), self.previous_txn)
                self.assertEqual(digest(self.link), self.original_sha)
                self.assertEqual(json.loads(self.receipt.read_text())['status'], 'rolled-back')
                self.unchanged()

    def test_interrupted_transition_is_recoverable(self):
        result = self.install(WORKSTATION_INSTRUCTIONS_FAIL_POINT='after-pointer',
                              WORKSTATION_INSTRUCTIONS_FAIL_MODE='exit')
        self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'applying')
        self.assertNotEqual(os.readlink(self.pointer), self.previous)
        result = self.rollback()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(os.readlink(self.pointer), self.previous)
        self.assertEqual(digest(self.link), self.original_sha)
        self.unchanged()

    def test_unrelated_custody_refuses_rollback(self):
        self.assertEqual(self.install().returncode, 0)
        (self.state / 'current-transaction').write_text('other-writer\n')
        result = self.rollback()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.state / 'current-transaction').read_text(), 'other-writer\n')
        self.assertEqual(self.link.read_text(), self.source)
        self.unchanged()

    def test_duplicate_transaction_cannot_recover_an_earlier_receipt(self):
        self.assertEqual(self.install().returncode, 0)
        selected = os.readlink(self.pointer)
        receipt_bytes = self.receipt.read_bytes()
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(os.readlink(self.pointer), selected)
        self.assertEqual(self.receipt.read_bytes(), receipt_bytes)
        self.assertEqual(self.link.read_text(), self.source)
        self.unchanged()

    def test_tampered_archived_rollback_code_refuses_before_recovery(self):
        self.assertEqual(self.install().returncode, 0)
        stored = (Path(json.loads(self.receipt.read_text())['rollbackEntryPoint']).parents[1]
                  / 'lib/workstation-recovery.py')
        original = stored.read_bytes()
        stored.write_bytes(original + b'\n# altered\n')
        selected = os.readlink(self.pointer)
        result = self.rollback()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(os.readlink(self.pointer), selected)
        self.assertEqual(self.link.read_text(), self.source)
        stored.write_bytes(original)
        self.assertEqual(self.rollback().returncode, 0)
        self.unchanged()

    def test_unrelated_live_path_drift_blocks_rollback(self):
        self.assertEqual(self.install().returncode, 0)
        config = self.home / '.codex/config.toml'
        original = os.readlink(config)
        config.unlink()
        config.write_text('external drift\n')
        with self.assertRaises(instructions.ManagedPathDrift):
            instructions.verify_managed_paths(self.home, self.prior_manifest,
                {name: recovery.fingerprint(self.home / name) for name in self.managed_names
                 if name != '.codex/config.toml'} |
                {'.codex/config.toml': {'type': 'symlink', 'target': original}})
        result = self.rollback()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'active')
        config.unlink()
        config.symlink_to(original)
        self.assertEqual(self.rollback().returncode, 0)
        self.unchanged()

    def test_unsupported_live_path_type_never_claims_rollback(self):
        config = self.home / '.codex/config.toml'
        original_link = os.readlink(config)
        marker = self.state / 'current-transaction'
        original_atomic = instructions.recovery.atomic_bytes

        def mutate_after_marker(path, value):
            original_atomic(path, value)
            if Path(path) == marker and value == (self.txn + '\n').encode():
                config.unlink()
                os.mkfifo(config)

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(instructions.recovery, 'atomic_bytes', side_effect=mutate_after_marker):
            with self.assertRaises(instructions.ManagedPathDrift):
                instructions.install(arguments)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'recovery-required')
        self.assertNotEqual(os.readlink(self.pointer), self.previous)
        self.assertTrue(config.is_fifo())
        config.unlink()
        config.symlink_to(original_link)
        self.assertEqual(self.rollback().returncode, 0)
        self.unchanged()


if __name__ == '__main__':
    unittest.main(verbosity=2)
