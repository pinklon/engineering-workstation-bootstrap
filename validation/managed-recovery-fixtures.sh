#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -B - "$ROOT" "$@" <<'PY'
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'lib/workstation-recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='managed-recovery-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = self.base / 'disposable-home'
        (self.home / '.codex/skills/unrelated').mkdir(parents=True)
        (self.home / '.codex/config.toml').write_text('model = "fixture-model"\n')
        (self.home / '.codex/AGENTS.md').write_text('original instructions\n')
        (self.home / '.codex/skills/unrelated/SKILL.md').write_text(
            '---\nname: unrelated\ndescription: preimage fixture\n---\n')
        (self.home / '.zshrc').write_text('# original shell\n')
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for key in list(self.env):
            if key.startswith('WORKSTATION_FAIL') or key.startswith('WORKSTATION_ROLLBACK_FAIL') or key == 'WORKSTATION_DOCTOR_FORCE_FAIL':
                self.env.pop(key)
        self.count = 0
        self.prior = self.activate()
        self.assertEqual(self.prior.returncode, 0, self.prior.stdout + self.prior.stderr)
        self.prior_receipt = self.receipt
        self.prior_txn = self.txn
        self.state = self.home / '.local/state/engineering-workstation-bootstrap'
        self.pointer = self.home / '.local/share/engineering-workstation-bootstrap/current'
        self.baseline_pointer = os.readlink(self.pointer)
        manifest = json.loads(Path(self.data()['backupManifest']).read_text())
        self.names = [x['relativePath'] for x in manifest['paths']]
        self.baseline = self.paths()

    def data(self):
        return json.loads(self.receipt.read_text())

    def paths(self):
        return {name: recovery.fingerprint(self.home / name) for name in self.names}

    def activate(self, **extra):
        self.count += 1
        self.txn = 'fixture-' + str(self.count)
        self.receipt = (self.home / '.local/state/engineering-workstation-bootstrap/receipts' /
                        ('activation-' + self.txn + '.json'))
        contract = self.base / (self.txn + '.json')
        contract.write_text(json.dumps({'schemaVersion': 1, 'activationAuthorized': True,
                                       'allowLiveHome': False, 'authorityReference': 'fixture:owned-recovery',
                                       'targetHome': str(self.home), 'version': self.txn,
                                       'manageSkillRoots': True}))
        return subprocess.run(['bash', str(ROOT / 'bin/workstation-activate'),
                               '--activation-contract', str(contract), '--home', str(self.home)],
                              env=dict(self.env, WORKSTATION_TRANSACTION_ID=self.txn, **extra),
                              capture_output=True, text=True, timeout=90)

    def rollback(self, automatic=False, **extra):
        command = ['bash', str(ROOT / 'bin/workstation-rollback'), '--receipt', str(self.receipt),
                   '--home', str(self.home)]
        if automatic:
            command.append('--automatic')
        return subprocess.run(command, env=dict(self.env, **extra),
                              capture_output=True, text=True, timeout=60)

    def restored(self):
        self.assertEqual(os.readlink(self.pointer), self.baseline_pointer)
        self.assertEqual((self.state / 'current-transaction').read_text().strip(), self.prior_txn)
        self.assertEqual(self.paths(), self.baseline)
        self.assertEqual(self.data()['status'], 'rolled-back')

    def test_original_link_denial_restores_existing_predecessor(self):
        fakebin = self.base / 'fakebin'
        fakebin.mkdir()
        stub = fakebin / 'ln'
        stub.write_text('#!/usr/bin/env bash\nfor arg in "$@"; do\n'
                        'if [[ "$arg" == "$FAULT_LINK" ]]; then exit 73; fi\ndone\nexec /bin/ln "$@"\n')
        stub.chmod(0o755)
        p = self.activate(PATH=str(fakebin) + ':' + self.env['PATH'],
                          FAULT_LINK=str(self.home / '.codex/AGENTS.md'))
        self.assertEqual(p.returncode, 73, p.stdout + p.stderr)
        self.restored()

    def test_error_matrix_across_activation_boundaries(self):
        points = ['after-intent', 'after-current', 'after-marker',
                  'before-path:.codex/AGENTS.md', 'after-remove:.codex/AGENTS.md',
                  'after-path:.codex/AGENTS.md', 'before-doctor', 'after-doctor',
                  'before-active-receipt']
        for point in points:
            with self.subTest(point=point):
                p = self.activate(WORKSTATION_FAIL_POINT=point)
                self.assertEqual(p.returncode, 74, p.stdout + p.stderr)
                self.restored()

    def test_non_err_exit_matrix_recovers_without_forcing_marker(self):
        for point in ['after-intent', 'after-current', 'after-marker',
                      'after-remove:.codex/AGENTS.md', 'before-active-receipt']:
            with self.subTest(point=point):
                p = self.activate(WORKSTATION_FAIL_POINT=point, WORKSTATION_FAIL_MODE='exit')
                self.assertEqual(p.returncode, 75)
                self.assertEqual(self.data()['status'], 'applying')
                r = self.rollback()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.restored()

    def test_prepublication_backup_failure_has_no_managed_effect(self):
        p = self.activate(WORKSTATION_FAIL_POINT='after-backups')
        self.assertEqual(p.returncode, 74)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(os.readlink(self.pointer), self.baseline_pointer)
        self.assertEqual(self.paths(), self.baseline)

    def test_committed_receipt_survives_notification_error(self):
        p = self.activate(WORKSTATION_FAIL_POINT='after-active')
        self.assertEqual(p.returncode, 74)
        self.assertEqual(self.data()['status'], 'active')
        self.assertEqual((self.state / 'current-transaction').read_text().strip(), self.txn)
        self.assertEqual(self.rollback().returncode, 0)
        self.restored()

    def test_rollback_failure_matrix_keeps_preimages_for_retry(self):
        points = ['before-paths', 'after-remove:.zshrc', 'after-path:.zshrc',
                  'before-pointer', 'after-pointer', 'after-marker', 'before-completion']
        for point in points:
            with self.subTest(point=point):
                p = self.activate()
                self.assertEqual(p.returncode, 0, p.stderr)
                r = self.rollback(WORKSTATION_ROLLBACK_FAIL_POINT=point)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(self.data()['status'], 'recovery-required')
                manifest = json.loads(Path(self.data()['backupManifest']).read_text())
                self.assertTrue(all((Path(self.data()['backupManifest']).parent / e['backupRelative']).exists()
                                    or (Path(self.data()['backupManifest']).parent / e['backupRelative']).is_symlink()
                                    for e in manifest['paths'] if e['originalType'] != 'absent'))
                r = self.rollback()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.restored()

    def test_rollback_non_err_exit_is_repeatable(self):
        self.assertEqual(self.activate().returncode, 0)
        r = self.rollback(WORKSTATION_ROLLBACK_FAIL_POINT='after-remove:.zshrc',
                          WORKSTATION_ROLLBACK_FAIL_MODE='exit')
        self.assertEqual(r.returncode, 75)
        self.assertEqual(self.data()['status'], 'rolling-back')
        self.assertEqual(self.rollback().returncode, 0)
        self.restored()

    def test_failed_automatic_recovery_is_reported_not_hidden(self):
        p = self.activate(WORKSTATION_FAIL_POINT='after-current',
                          WORKSTATION_ROLLBACK_FAIL_POINT='before-paths')
        self.assertEqual(p.returncode, 74)
        self.assertIn('REQUIRES_OWNER', p.stderr)
        self.assertEqual(self.data()['status'], 'recovery-required')
        self.assertEqual(self.rollback().returncode, 0)
        self.restored()

    def test_doctor_failure_and_partial_count_still_restore(self):
        for extra in [{'WORKSTATION_DOCTOR_FORCE_FAIL': '1'}, {'WORKSTATION_FAIL_AFTER_PATHS': '3'}]:
            p = self.activate(**extra)
            self.assertNotEqual(p.returncode, 0)
            self.restored()

    def test_unrelated_marker_and_pointer_refuse_without_mutation(self):
        self.assertEqual(self.activate().returncode, 0)
        (self.state / 'current-transaction').write_text('unrelated-fixture\n')
        before = self.paths()
        r = self.rollback()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.paths(), before)
        self.assertEqual((self.state / 'current-transaction').read_text(), 'unrelated-fixture\n')
        (self.state / 'current-transaction').write_text(self.txn + '\n')
        self.pointer.unlink()
        self.pointer.symlink_to(self.baseline_pointer)
        self.assertNotEqual(self.rollback().returncode, 0)
        self.assertEqual(self.paths(), before)
        self.assertEqual(os.readlink(self.pointer), self.baseline_pointer)

    def test_candidate_content_and_backup_corruption_refuse(self):
        self.assertEqual(self.activate().returncode, 0)
        manifest = json.loads(Path(self.data()['backupManifest']).read_text())
        backup = Path(self.data()['backupManifest']).parent / 'files/.zshrc'
        backup.write_text('corrupted preimage\n')
        before = self.paths()
        r = self.rollback()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.paths(), before)
        self.assertEqual(self.data()['status'], 'active')
        self.assertTrue(manifest['paths'])
        # Restore the exact disposable backup then change candidate source.
        backup.write_bytes((self.home / '.zshrc').read_bytes())
        release = Path(self.data()['releaseDir'])
        (release / 'config/codex/AGENTS.md').write_text('unrelated candidate\n')
        self.assertNotEqual(self.rollback().returncode, 0)
        self.assertEqual(self.paths(), before)

    def test_unowned_automatic_and_stale_lock_refuse(self):
        self.assertEqual(self.activate().returncode, 0)
        before = self.paths()
        self.assertNotEqual(self.rollback(automatic=True).returncode, 0)
        lock = self.state / 'activation.lock'
        lock.mkdir()
        r = self.rollback()
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(lock.exists())
        self.assertEqual(self.paths(), before)

    def test_completed_rollback_is_idempotent_and_legacy_normal_supported(self):
        self.assertEqual(self.activate().returncode, 0)
        result = self.rollback()
        self.assertEqual(result.returncode, 0)
        self.restored()
        activation = self.data()
        terminal = Path(activation['rollbackReceipt'])
        fields = json.loads(terminal.read_text())
        self.assertRegex(fields['completedAt'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
        self.assertEqual(activation['rolledBackAt'], fields['completedAt'])
        self.assertIn('Receipt: ' + str(terminal), result.stdout)
        self.assertNotIn('Receipt: ' + str(self.receipt), result.stdout)
        receipt_bytes = self.receipt.read_bytes(), terminal.read_bytes()
        result = self.rollback()
        self.assertEqual(result.returncode, 0)
        self.restored()
        self.assertEqual(receipt_bytes, (self.receipt.read_bytes(), terminal.read_bytes()))
        self.assertIn('Receipt: ' + str(terminal), result.stdout)
        # Only this disposable completed predecessor receipt is projected to
        # the unchanged legacy protocol; no live receipt or marker is forced.
        self.receipt = self.prior_receipt
        legacy = self.data()
        legacy.pop('recoveryProtocol')
        self.receipt.write_text(json.dumps(legacy))
        r = self.rollback()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.home / '.codex/AGENTS.md').read_text(), 'original instructions\n')


unittest.main(argv=['managed-recovery'] + sys.argv[2:], verbosity=2)
PY
