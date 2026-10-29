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


    def test_recovery_copy_leaf_never_writes_outside(self):
        outside = self.base / 'foreign-restore'
        outside.write_text('other writer\n')
        original_mkdtemp = tempfile.mkdtemp
        injected = False

        def plant_restore_leaf(*args, **kwargs):
            nonlocal injected
            directory = original_mkdtemp(*args, **kwargs)
            if Path(kwargs.get('dir', '')) == self.home and not injected:
                (Path(directory) / 'payload').symlink_to(outside)
                injected = True
            return directory

        with patch.object(recovery.tempfile, 'mkdtemp', plant_restore_leaf):
            with self.assertRaises(FileExistsError):
                recovery.recover(self.prior_receipt, self.home)
        self.assertTrue(injected)
        self.assertEqual(outside.read_text(), 'other writer\n')

    def test_recovery_copy_preserves_regular_file_metadata(self):
        backup = self.prior_manifest.parent / 'files/.zshrc'
        os.utime(backup, ns=(946684800123456789, 946684800123456789))
        backed_up_mtime = backup.stat().st_mtime_ns
        xattr_name = 'user.workstation-recovery-fixture'
        xattr_supported = False
        if hasattr(os, 'setxattr'):
            try:
                os.setxattr(backup, xattr_name, b'fixture')
                xattr_supported = True
            except OSError:
                pass
        recovery.recover(self.prior_receipt, self.home)
        restored = self.home / '.zshrc'
        self.assertEqual(restored.stat().st_mtime_ns, backed_up_mtime)
        if xattr_supported:
            self.assertEqual(os.getxattr(restored, xattr_name), b'fixture')

    def test_upgrade_instruction_leaf_never_writes_outside(self):
        release = self.pointer.parent / 'versions' / ('fixture-instructions-' + self.txn)
        candidate = release / 'config/codex/AGENTS.md'
        outside = self.base / 'foreign-upgrade-instructions'
        outside.write_text('other writer\n')
        original_copytree = instructions.shutil.copytree
        injected = False

        def plant_upgrade_leaf(source, destination, *args, **kwargs):
            nonlocal injected
            result = original_copytree(source, destination, *args, **kwargs)
            if Path(destination) == release:
                if candidate.exists() or candidate.is_symlink():
                    candidate.unlink()
                candidate.symlink_to(outside)
                injected = True
            return result

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(instructions.shutil, 'copytree', plant_upgrade_leaf):
            with self.assertRaises(FileExistsError):
                instructions.install(arguments)
        self.assertTrue(injected)
        self.assertEqual(outside.read_text(), 'other writer\n')
        self.assertFalse(self.receipt.exists())
        self.unchanged()


class LinuxFirstInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='linux-first-install-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / 'home'
        (self.home / '.codex').mkdir(parents=True)
        self.config = self.home / '.codex/config.toml'
        self.config.write_text('model = "existing-owner-model"\n')
        self.shell = self.home / '.zshrc'
        self.shell.write_text('# unrelated shell\n')
        self.config_bytes = self.config.read_bytes()
        self.shell_bytes = self.shell.read_bytes()
        self.wsrepo = self.base / 'workstation-source'
        self.ctrepo = self.base / 'catalog-source'
        self.wsrepo.mkdir()
        self.ctrepo.mkdir()
        self.source = 'pinned Linux fixture instructions\n'
        ws_commit = fixture_repo(self.wsrepo, self.wsrepo / 'config/codex/AGENTS.md', self.source)
        ct_commit = fixture_repo(self.ctrepo, self.ctrepo / 'architecture/mesh-presentation-aliases.v1.json',
                                 json.dumps(CATALOG, indent=2) + '\n')
        catalog_blob = run('git', '-C', str(self.ctrepo), 'rev-parse',
                           ct_commit + ':architecture/mesh-presentation-aliases.v1.json').stdout.strip()
        self.contract = self.base / 'first-install.json'
        self.contract.write_text(json.dumps({
            'schemaVersion': 1, 'linuxFirstInstallAuthorized': True, 'allowLiveHome': False,
            'authorityReference': 'fixture:linux-first-install', 'targetHome': str(self.home),
            'version': 'fixture-first', 'workstationCommit': ws_commit,
            'workstationInstructionSha256': hashlib.sha256(self.source.encode()).hexdigest(),
            'catalogCommit': ct_commit, 'catalogBlobSha1': catalog_blob,
        }))
        self.txn = 'fixture-first-install'
        self.state = self.home / '.local/state/engineering-workstation-bootstrap'
        self.share = self.home / '.local/share/engineering-workstation-bootstrap'
        self.pointer = self.share / 'current'
        self.marker = self.state / 'current-transaction'
        self.link = self.home / '.codex/AGENTS.md'
        self.receipt = self.state / 'receipts' / ('activation-' + self.txn + '.json')
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', WORKSTATION_TRANSACTION_ID=self.txn)
        for key in list(self.env):
            if key.startswith('WORKSTATION_FAIL') or key.startswith('WORKSTATION_INSTRUCTIONS_FAIL'):
                self.env.pop(key)

    def command(self, action, **extra):
        return run('bash', str(ROOT / 'bin/workstation-instructions'), action,
                   '--contract', str(self.contract), '--home', str(self.home),
                   '--workstation-repo', str(self.wsrepo), '--catalog-repo', str(self.ctrepo),
                   env=dict(self.env, **extra))

    def rollback(self):
        return run('bash', str(ROOT / 'bin/workstation-instructions'), 'rollback',
                   '--receipt', str(self.receipt), '--home', str(self.home), env=self.env)

    def unrelated_unchanged(self):
        self.assertEqual(self.config.read_bytes(), self.config_bytes)
        self.assertEqual(self.shell.read_bytes(), self.shell_bytes)

    def test_read_only_preflight_install_and_exact_rollback(self):
        result = self.command('first-install-preflight')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'FIRST_INSTALL_READY')
        self.assertFalse((self.home / '.local').exists())
        result = self.command('first-install')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt['status'], 'active')
        self.assertEqual(receipt['preimageType'], 'absent')
        self.assertEqual(receipt['previousCurrent'], '')
        self.assertEqual(receipt['previousTransaction'], '')
        self.assertEqual(self.link.read_text(), self.source)
        self.assertEqual(os.readlink(self.link), str(self.pointer / 'config/codex/AGENTS.md'))
        self.assertEqual(self.marker.read_text().strip(), self.txn)
        self.unrelated_unchanged()
        result = self.rollback()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'rolled-back')
        self.assertFalse(self.link.exists() or self.link.is_symlink())
        self.assertFalse(self.pointer.exists() or self.pointer.is_symlink())
        self.assertFalse(self.marker.exists())
        self.unrelated_unchanged()

    def test_partial_or_occupied_state_refuses_without_writes(self):
        for relative, kind in [('.codex/AGENTS.md', 'file'),
                               ('.local/share/engineering-workstation-bootstrap', 'directory'),
                               ('.local/state/engineering-workstation-bootstrap', 'directory'),
                               ('.codex/AGENTS.md', 'broken-link')]:
            with self.subTest(relative=relative, kind=kind):
                path = self.home / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if kind == 'directory':
                    path.mkdir()
                elif kind == 'broken-link':
                    path.symlink_to('missing')
                else:
                    path.write_text('unmanaged instructions\n')
                result = self.command('first-install')
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.receipt.exists())
                self.assertFalse(self.pointer.is_symlink())
                self.assertFalse(self.marker.exists())
                self.unrelated_unchanged()
                if kind == 'directory':
                    path.rmdir()
                else:
                    path.unlink()

    def test_wrong_pin_refuses_before_host_state(self):
        value = json.loads(self.contract.read_text())
        value['workstationInstructionSha256'] = '0' * 64
        self.contract.write_text(json.dumps(value))
        result = self.command('first-install')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / '.local').exists())
        self.unrelated_unchanged()

    def test_competing_share_root_is_preserved_on_race(self):
        original_mkdir = Path.mkdir

        def competing_mkdir(path, *args, **kwargs):
            if path == self.share:
                original_mkdir(path, *args, **kwargs)
                raise FileExistsError('another source created the share root')
            return original_mkdir(path, *args, **kwargs)

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(Path, 'mkdir', competing_mkdir):
            with self.assertRaises(FileExistsError):
                instructions.first_install(arguments)
        self.assertTrue(self.share.is_dir())
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.pointer.is_symlink())
        self.assertFalse(self.marker.exists())
        self.unrelated_unchanged()

    def test_competing_backup_directory_is_never_removed(self):
        backup = self.state / 'backups' / self.txn
        original_mkdir = Path.mkdir

        def competing_mkdir(path, *args, **kwargs):
            if path == backup:
                original_mkdir(path, *args, **kwargs)
                (path / 'other-writer.txt').write_text('foreign evidence\n')
                raise FileExistsError('another writer created the backup')
            return original_mkdir(path, *args, **kwargs)

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(Path, 'mkdir', competing_mkdir):
            with self.assertRaises(FileExistsError):
                instructions.first_install(arguments)
        self.assertEqual((backup / 'other-writer.txt').read_text(), 'foreign evidence\n')
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.pointer.is_symlink())
        self.assertFalse(self.link.is_symlink())
        self.unrelated_unchanged()

    def test_competing_instruction_leaf_never_writes_outside(self):
        candidate = self.share / 'versions' / ('fixture-first-' + self.txn) / 'config/codex/AGENTS.md'
        outside = self.base / 'foreign-instructions'
        outside.write_text('other writer\n')
        original_mkdir = Path.mkdir
        injected = False

        def plant_leaf(path, *args, **kwargs):
            nonlocal injected
            result = original_mkdir(path, *args, **kwargs)
            if path == candidate.parent:
                candidate.symlink_to(outside)
                injected = True
            return result

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(Path, 'mkdir', plant_leaf):
            with self.assertRaises(FileExistsError):
                instructions.first_install(arguments)
        self.assertTrue(injected)
        self.assertEqual(outside.read_text(), 'other writer\n')
        self.assertFalse(self.receipt.exists())
        self.unrelated_unchanged()

    def test_competing_rollback_bundle_leaf_never_writes_outside(self):
        target = self.state / 'backups' / self.txn / 'recovery/bin/workstation-instructions'
        outside = self.base / 'foreign-rollback-wrapper'
        outside.write_text('other writer\n')
        original_mkdir = Path.mkdir
        injected = False

        def plant_leaf(path, *args, **kwargs):
            nonlocal injected
            result = original_mkdir(path, *args, **kwargs)
            if path == target.parent:
                target.symlink_to(outside)
                injected = True
            return result

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(Path, 'mkdir', plant_leaf):
            with self.assertRaises(FileExistsError):
                instructions.first_install(arguments)
        self.assertTrue(injected)
        self.assertEqual(outside.read_text(), 'other writer\n')
        self.assertFalse(self.receipt.exists())
        self.unrelated_unchanged()

    def test_share_parent_replacement_refuses_before_staging_outside_home(self):
        original_mkdir = Path.mkdir
        parent = self.home / '.local/share'
        moved = self.home / '.local/share-moved'
        outside = self.base / 'outside-share'
        outside.mkdir()

        def replace_parent(path, *args, **kwargs):
            result = original_mkdir(path, *args, **kwargs)
            if path == self.share:
                parent.rename(moved)
                parent.symlink_to(outside, target_is_directory=True)
            return result

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(Path, 'mkdir', replace_parent):
            with self.assertRaises(instructions.ManagedPathDrift):
                instructions.first_install(arguments)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.link.is_symlink())
        self.assertTrue((moved / 'engineering-workstation-bootstrap').is_dir())
        self.unrelated_unchanged()

    def test_interrupted_pointer_recovers_from_exact_receipt(self):
        result = self.command('first-install', WORKSTATION_INSTRUCTIONS_FAIL_POINT='after-pointer',
                              WORKSTATION_INSTRUCTIONS_FAIL_MODE='exit')
        self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'applying')
        self.assertTrue(self.pointer.is_symlink())
        result = self.rollback()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.pointer.is_symlink())
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.link.is_symlink())
        self.unrelated_unchanged()

    def test_codex_parent_drift_holds_without_following_symlink(self):
        original_atomic = instructions.recovery.atomic_bytes
        moved = self.home / '.codex-moved'

        def swap_after_marker(path, value):
            original_atomic(path, value)
            if Path(path) == self.marker and value == (self.txn + '\n').encode():
                (self.home / '.codex').rename(moved)
                (self.home / '.codex').symlink_to(moved)

        arguments = SimpleNamespace(home=str(self.home), contract=self.contract,
                                    workstation_repo=self.wsrepo, catalog_repo=self.ctrepo)
        with patch.dict(os.environ, WORKSTATION_TRANSACTION_ID=self.txn), \
             patch.object(instructions.recovery, 'atomic_bytes', side_effect=swap_after_marker):
            with self.assertRaises(instructions.ManagedPathDrift):
                instructions.first_install(arguments)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'recovery-required')
        self.assertFalse((moved / 'AGENTS.md').exists())
        (self.home / '.codex').unlink()
        moved.rename(self.home / '.codex')
        self.assertEqual(self.rollback().returncode, 0)
        self.unrelated_unchanged()

    def test_failure_after_link_recovers_and_other_writer_blocks_rollback(self):
        result = self.command('first-install', WORKSTATION_INSTRUCTIONS_FAIL_POINT='after-link')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'rolled-back')
        self.assertFalse(self.link.is_symlink())
        self.unrelated_unchanged()
        # A second, fresh disposable home checks the active-receipt writer fence.
        self.state.rename(self.base / 'old-state')
        self.share.rename(self.base / 'old-share')
        self.assertEqual(self.command('first-install').returncode, 0)
        self.marker.write_text('other-writer\n')
        result = self.rollback()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.link.is_symlink())
        self.marker.write_text(self.txn + '\n')
        self.assertEqual(self.rollback().returncode, 0)
        self.unrelated_unchanged()


if __name__ == '__main__':
    unittest.main(verbosity=2)
