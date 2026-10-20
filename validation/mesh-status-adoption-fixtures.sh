#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B - "$ROOT" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv[1])


class NativeAdoption(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='native-adoption-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / 'disposable-home'
        (self.home / '.codex/skills/unrelated').mkdir(parents=True)
        self.old_agents = b'Existing owner instructions remain intact.\n'
        (self.home / '.codex/AGENTS.md').write_bytes(self.old_agents)
        (self.home / '.codex/config.toml').write_text(
            'model = "fixture-model"\napproval_policy = "on-request"\n'
            'approvals_reviewer = "auto_review"\nsandbox_mode = "workspace-write"\n')
        self.original_skill = b'---\nname: unrelated\ndescription: preserved fixture\n---\n'
        (self.home / '.codex/skills/unrelated/SKILL.md').write_bytes(self.original_skill)
        self.assets = self.base / 'profile.assets/skills'
        self.source = self.assets / 'mesh-status'
        self.source.mkdir(parents=True)
        (self.assets / 'unrelated').mkdir()
        (self.assets / 'unrelated/SKILL.md').write_bytes(self.original_skill)
        (self.source / 'SKILL.md').write_text(
            '---\nname: mesh-status\ndescription: synthetic native package fixture\n---\n'
            'Read the sibling policy and run report.py locally. No authority.\n')
        (self.source / 'owner-operating-model.contract.json').write_text(
            json.dumps({'version': '1.1.0', 'authority': False}))
        (self.source / 'report.py').write_text(
            'import json\nfrom pathlib import Path\n'
            'print(json.loads((Path(__file__).parent / '
            '"owner-operating-model.contract.json").read_text())["version"])\n')
        self.profile = self.base / 'profile.json'
        self.profile.write_text(json.dumps({
            'schemaVersion': 1, 'secretValues': False,
            'skills': [
                {'name': 'unrelated', 'sourceDir': 'profile.assets/skills/unrelated',
                 'installRoot': 'codex-skills', 'state': 'enabled'},
                {'name': 'mesh-status', 'sourceDir': 'profile.assets/skills/mesh-status',
                 'installRoot': 'codex-skills', 'state': 'enabled'}],
            'taskScopedSkills': [], 'shell': {}, 'mcp': [], 'utilities': []}))
        self.contract = self.base / 'contract.json'
        self.contract.write_text(json.dumps({
            'schemaVersion': 1, 'activationAuthorized': True, 'allowLiveHome': False,
            'authorityReference': 'fixture:source-only-native-mechanics',
            'targetHome': str(self.home), 'version': 'fixture-native',
            'privateProfileSha256': hashlib.sha256(self.profile.read_bytes()).hexdigest(),
            'manageSkillRoots': True, 'codexSystemSkills': []}))
        self.env = dict(os.environ, WORKSTATION_TRANSACTION_ID='fixture-native')
        self.env.pop('PYTHONPATH', None)
        # The disposable target is always different from the invoking home.
        self.assertNotEqual(self.home, Path(self.env['HOME']).resolve())

    def activate(self, env=None):
        return subprocess.run([
            'bash', str(ROOT / 'bin/workstation-activate'),
            '--activation-contract', str(self.contract),
            '--private-profile', str(self.profile), '--home', str(self.home)],
            env=env or self.env, capture_output=True, text=True, timeout=60)

    def successful_activation(self):
        p = self.activate()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        receipt_path = (self.home / '.local/state/engineering-workstation-bootstrap/'
                        'receipts/activation-fixture-native.json')
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt['status'], 'active')
        self.assertFalse(receipt['liveHomeActivated'])
        return receipt_path, receipt

    def test_instruction_preserves_original_execution_policy(self):
        data = (ROOT / 'config/codex/AGENTS.md').read_bytes()
        original = data[:431]
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         '690d03f17dd2a214983d211062dc13b7191f82f4fb1d4f0e38d1fade710f8bab')
        self.assertIn(b'Unknown stays unknown.', data[431:])
        self.assertIn(b'grants no approval, execution, disclosure or live authority', data[431:])

    def test_callsigns_are_display_only_in_staged_codex_instructions(self):
        source = (ROOT / 'config/codex/AGENTS.md').read_text()
        mappings = {
            'segfault': ('ChatGPT architecture/reasoning partner', 'agent'),
            'syscall': ('Codex engineering agent', 'agent'),
            'phorse': ('existing Pale Horse coordinator', 'agent'),
            'GhostMesh': ('overall system', 'system'),
        }
        for name, (meaning, kind) in mappings.items():
            self.assertEqual(source.count(f'- `{name}` = {meaning} (`{kind}`).'), 1)
        self.assertIn('architecture/mesh-presentation-aliases.v1.json', source)
        self.assertIn('ghostmesh-presentation-aliases.v1', source)
        self.assertIn('presentationOnly: true', source)
        self.assertIn('authorityRegistry: architecture/mesh-identity-registry.v1.json', source)
        self.assertIn('A draft PR is candidate evidence, not current-main canon.', source)
        self.assertIn('presentation aliases only', source)
        self.assertIn('They do not create security\nprincipals, permissions, credentials, runtime identities, executor selection,\nor task authority.', source)
        _, receipt = self.successful_activation()
        staged = (Path(receipt['releaseDir']) / 'config/codex/AGENTS.md').read_text()
        self.assertEqual(staged, source)
        self.assertEqual((self.home / '.codex/AGENTS.md').read_text(), source)

    def test_operating_roles_agree_with_system_alias(self):
        instructions = (ROOT / 'config/codex/AGENTS.md').read_text()
        contract = (ROOT / 'docs/AGENT-OPERATING-CONTRACT.md').read_text()
        self.assertIn('- `GhostMesh` = overall system (`system`).', instructions)
        self.assertIn('GhostMesh names the overall system, not an individual agent\n'
                      '  or authorization principal', contract)
        self.assertIn('**Bounded AI executor or coordinator:** an explicitly identified actor',
                      contract)
        self.assertNotIn('**GhostMesh:**', contract)
        self.assertIn('docs/AGENT-OPERATING-CONTRACT.md', (ROOT / 'AGENTS.md').read_text())

    def test_wrapper_and_package_work_without_staging_source(self):
        _, receipt = self.successful_activation()
        release = Path(receipt['releaseDir'])
        wrapper = (self.home / '.codex/skills/mesh-status/SKILL.md').read_text()
        self.assertIn(str(release / 'skill-library/mesh-status/SKILL.md'), wrapper)
        copied = release / 'skill-library/mesh-status'
        for source in self.source.iterdir():
            self.assertEqual(source.read_bytes(), (copied / source.name).read_bytes())
        self.source.rename(self.source.with_name('source-unavailable'))
        p = subprocess.run([sys.executable, '-I', '-B', str(copied / 'report.py')],
                           cwd=self.base, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual((p.returncode, p.stdout), (0, '1.1.0\n'), p.stderr)
        self.assertFalse(list(copied.rglob('__pycache__')))
        self.assertEqual((release / 'skill-library/unrelated/SKILL.md').read_bytes(), self.original_skill)
        config = (release / 'config/codex/config.toml').read_text()
        for value in ['fixture-model', 'on-request', 'auto_review', 'workspace-write']:
            self.assertIn(value, config)

    def test_stale_profile_refuses_before_any_release(self):
        self.profile.write_text(self.profile.read_text() + '\n')
        p = self.activate()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('private profile checksum does not match', p.stderr)
        self.assertFalse((self.home / '.local/share/engineering-workstation-bootstrap').exists())
        self.assertEqual((self.home / '.codex/AGENTS.md').read_bytes(), self.old_agents)

    def test_live_home_gate_refuses_before_any_release(self):
        p = self.activate(dict(self.env, HOME=str(self.home)))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('does not allow the live home', p.stderr)
        self.assertFalse((self.home / '.local/share/engineering-workstation-bootstrap').exists())

    def test_rollback_restores_instructions_and_unrelated_skill(self):
        receipt_path, _ = self.successful_activation()
        p = subprocess.run(['bash', str(ROOT / 'bin/workstation-rollback'),
                            '--receipt', str(receipt_path), '--home', str(self.home)],
                           env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((self.home / '.codex/AGENTS.md').read_bytes(), self.old_agents)
        self.assertEqual((self.home / '.codex/skills/unrelated/SKILL.md').read_bytes(), self.original_skill)
        self.assertFalse((self.home / '.codex/skills/mesh-status').exists())
        self.assertEqual(json.loads(receipt_path.read_text())['status'], 'rolled-back')


unittest.main(argv=['native-adoption'], verbosity=2)
PY
