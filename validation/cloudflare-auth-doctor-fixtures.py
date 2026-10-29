"""Offline CLI tests; any attempted provider command is trapped locally."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANARY = 'synthetic-sensitive-value'


def observation(capability='authentication', payload=None, code=0, fmt='wrangler-json', **extra):
    return {'capability': capability, 'format': fmt, 'exitCode': code,
            'stdout': json.dumps(payload), 'stderr': CANARY, **extra}


class OfflineDoctor(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cloudflare-offline-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.home = self.directory / 'home'
        self.home.mkdir()
        (self.home / 'untouched').write_text('existing local state')
        self.bin = self.directory / 'bin'
        self.bin.mkdir()
        (self.bin / 'python3').symlink_to(sys.executable)
        (self.bin / 'dirname').symlink_to('/usr/bin/dirname')
        self.trap = self.directory / 'unexpected-probe'
        for name in ('wrangler', 'gh', 'curl', 'ssh', 'npm', 'npx'):
            command = self.bin / name
            command.write_text('#!/bin/sh\nprintf attempted > "$PROBE_TRAP"\nexit 99\n')
            command.chmod(0o755)
        self.env = {'PATH': str(self.bin), 'HOME': str(self.home), 'PROBE_TRAP': str(self.trap),
                    'PYTHONDONTWRITEBYTECODE': '1'}
        self.before = self.snapshot()

    def snapshot(self):
        return {str(path.relative_to(self.home)): path.read_bytes() for path in self.home.rglob('*') if path.is_file()}

    def run_doctor(self, observations=None, raw=None, path=None, human=False, root=ROOT, args=()):
        command = ['/bin/bash', str(root / 'bin/cloudflare-auth-doctor')]
        if not human:
            command += ['--format', 'json']
        if observations is not None or raw is not None:
            path = self.directory / 'observations.json'
            path.write_text(raw if raw is not None else json.dumps({'schemaVersion': 1, 'observations': observations}))
        if path is not None:
            command += ['--input', str(path)]
        result = subprocess.run(command + list(args), env=self.env, text=True, capture_output=True, timeout=5)
        self.assertFalse(self.trap.exists(), 'provider/subprocess probe attempted')
        self.assertEqual(self.before, self.snapshot())
        self.assertNotIn(CANARY, result.stdout + result.stderr)
        data = json.loads(result.stdout) if result.returncode == 1 and not human else None
        if data:
            self.assertIs(data['ready'], False)
            self.assertIs(data['authorityGranted'], False)
            self.assertIs(data['secretValues'], False)
            self.assertIs(data['probesExecuted'], False)
            self.assertEqual(data['runtimeReadiness'], 'unknown')
            self.assertTrue(all(row['state'] == 'unknown' for row in data['capabilities']))
        return result, data

    @staticmethod
    def reported(data, capability='authentication'):
        return next(row['reportedState'] for row in data['capabilities'] if row['capability'] == capability)

    def test_default_is_unknown_without_invoking_installed_wrangler(self):
        result, data = self.run_doctor()
        self.assertEqual(result.returncode, 1)
        self.assertTrue(all(not row['observationSupplied'] for row in data['capabilities']))
        self.assertIsNone(data['inputSha256'])

    def test_legacy_human_default_is_not_false_success(self):
        result, _ = self.run_doctor(human=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('current Cloudflare readiness is UNKNOWN', result.stdout)

    def test_human_exit_zero_does_not_establish_authentication(self):
        item = observation(fmt='wrangler-human', stdout='You are not authenticated. Please run wrangler login.')
        result, data = self.run_doctor([item])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.reported(data), 'unknown')

    def test_strict_logged_in_boolean_and_success_code(self):
        cases = [({'loggedIn': True}, 0, 'ready'), ({'loggedIn': False}, 0, 'unauthenticated'),
                 ({'loggedIn': 'true'}, 0, 'unknown'), ({'loggedIn': 1}, 0, 'unknown'),
                 ({'loggedIn': True}, 1, 'unknown'), ({}, 0, 'unknown')]
        for payload, code, expected in cases:
            with self.subTest(payload=payload, code=code):
                payload.update({'token': CANARY, 'email': CANARY, 'accounts': [{'name': CANARY}]})
                _, data = self.run_doctor([observation(payload=payload, code=code)])
                self.assertEqual(self.reported(data), expected)
                self.assertEqual(self.reported(data, 'r2-bucket-list'), 'unknown')

    def test_r2_specific_errors_do_not_become_generic_auth_failures(self):
        for codes, expected in [([10042], 'provider-not-enabled'), ([10003], 'insufficient-permission'),
                                ([10042, 10003], 'unknown'), ([403], 'unknown'), ([404], 'unknown')]:
            payload = {'success': False, 'errors': [{'code': code, 'message': CANARY} for code in codes]}
            _, data = self.run_doctor([observation('r2-bucket-list', payload, 1, 'cloudflare-api-json')])
            self.assertEqual(self.reported(data, 'r2-bucket-list'), expected)
            self.assertEqual(self.reported(data), 'unknown')

    def test_r2_error_code_in_other_capability_or_free_text_is_unknown(self):
        payload = {'success': False, 'errors': [{'code': 10042}]}
        _, data = self.run_doctor([observation('pages-project-list', payload, 1, 'cloudflare-api-json')])
        self.assertEqual(self.reported(data, 'pages-project-list'), 'unknown')
        _, data = self.run_doctor([observation('r2-bucket-list', code=1, fmt='wrangler-human', stdout='reference 10042')])
        self.assertEqual(self.reported(data, 'r2-bucket-list'), 'unknown')

    def test_empty_lists_are_reported_healthy_but_never_runtime_verified(self):
        items = [observation('r2-bucket-list', {'success': True, 'result': {'buckets': []}}, fmt='cloudflare-api-json'),
                 observation('pages-project-list', []), observation('worker-deployments', [])]
        _, data = self.run_doctor(items)
        for item in items:
            self.assertEqual(self.reported(data, item['capability']), 'ready')

    def test_wrong_shapes_malformed_and_duplicate_provider_json_are_unknown(self):
        for text in ('true', 'null', '{}', '[1]', '{broken', '{"loggedIn":true,"loggedIn":false}', 'NaN'):
            _, data = self.run_doctor([observation(stdout=text)])
            self.assertEqual(self.reported(data), 'unknown')

    def test_missing_tool_and_timeout_are_only_reported_observations(self):
        for reason, expected in [('missing-tool', 'missing-tool'), ('timeout', 'unknown'), ('output-limit', 'unknown')]:
            _, data = self.run_doctor([observation(payload={'loggedIn': True}, reason=reason)])
            self.assertEqual(self.reported(data), expected)

    def test_invalid_envelope_rejects_without_echo_or_probe(self):
        examples = [[], {'schemaVersion': True, 'observations': []},
                    {'schemaVersion': 1, 'observations': [observation(), observation()]},
                    {'schemaVersion': 1, 'observations': [observation(exitCode=True)]},
                    {'schemaVersion': 1, 'observations': [observation(capability=CANARY)]}]
        for data in examples:
            result, _ = self.run_doctor(raw=json.dumps(data))
            self.assertEqual(result.returncode, 2)
        result, _ = self.run_doctor(raw='{"schemaVersion":1,"schemaVersion":1,"observations":[]}')
        self.assertEqual(result.returncode, 2)

    def test_oversized_file_and_symlink_are_refused(self):
        result, _ = self.run_doctor(raw='x' * 65537)
        self.assertEqual(result.returncode, 2)
        target = self.directory / 'target.json'
        target.write_text('{"schemaVersion":1,"observations":[]}')
        link = self.directory / 'link.json'
        link.symlink_to(target)
        result, _ = self.run_doctor(path=link)
        self.assertEqual(result.returncode, 2)

    def test_fifo_is_refused_without_waiting_for_a_producer(self):
        fifo = self.directory / 'pipe'
        os.mkfifo(fifo)
        result, _ = self.run_doctor(path=fifo)
        self.assertEqual(result.returncode, 2)

    def test_errors_do_not_echo_sensitive_argument_or_path(self):
        result, _ = self.run_doctor(path=self.directory / CANARY)
        self.assertEqual(result.returncode, 2)
        result, _ = self.run_doctor(args=['--unexpected', CANARY])
        self.assertEqual(result.returncode, 2)

    def test_repeat_runs_only_change_classification_time(self):
        items = [observation(payload={'loggedIn': True})]
        _, a = self.run_doctor(items)
        _, b = self.run_doctor(items)
        a.pop('classifiedAt'); b.pop('classifiedAt')
        self.assertEqual(a, b)

    def test_extracted_layout_and_spaces(self):
        package = self.directory / 'extracted package'
        (package / 'bin').mkdir(parents=True); (package / 'lib').mkdir()
        shutil.copy2(ROOT / 'bin/cloudflare-auth-doctor', package / 'bin')
        shutil.copy2(ROOT / 'lib/cloudflare_auth_receipts.py', package / 'lib')
        result, data = self.run_doctor(root=package)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(data['ready'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
