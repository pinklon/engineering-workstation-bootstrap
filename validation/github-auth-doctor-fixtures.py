"""Offline process-level doctor fixtures. PATH contains only local command doubles."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANARY = 'synthetic-sensitive-canary'
STUB = r'''
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
scenario = os.environ.get('SCENARIO', 'healthy')
with open(os.environ['TRACE'], 'a') as stream:
    stream.write(json.dumps([Path(sys.argv[0]).name] + args) + '\n')
canary = 'synthetic-sensitive-canary'
if Path(sys.argv[0]).name == 'ssh':
    if scenario == 'ssh-failure':
        print(canary, file=sys.stderr)
        raise SystemExit(255)
    who = 'other-user' if scenario == 'ssh-mismatch' else 'fixture-user'
    print("Hi " + who + "! You've successfully authenticated, but GitHub does not provide shell access.", file=sys.stderr)
    raise SystemExit(1)
if args == ['--version']:
    if scenario == 'hung':
        time.sleep(10)
    if scenario == 'flood':
        sys.stdout.write('x' * 100000)
        sys.stdout.flush()
        time.sleep(10)
    print('gh version 2.100.0 (2026-09-03)')
elif args[:3] == ['config', 'get', 'git_protocol']:
    print('ssh' if scenario.startswith('ssh') else 'https')
elif args[0] == 'api':
    assert args[args.index('--method') + 1] == 'GET'
    assert args[args.index('--hostname') + 1] in ('github.com', 'code.example.test')
    target = args[-1]
    if target == 'user':
        if scenario == 'unauthenticated':
            print(canary + ' (HTTP 401)', file=sys.stderr)
            raise SystemExit(1)
        if scenario == 'malformed':
            print('{broken ' + canary)
        elif scenario == 'secret-identity':
            print(json.dumps({'login': 'ghp_' + 'a' * 30, 'type': 'User'}))
        else:
            print(json.dumps({'login': 'fixture-user', 'type': 'User', 'token': canary, 'email': canary}))
    elif '/hooks?' in target:
        print(json.dumps([{'config': {'secret': canary, 'url': canary}}]) if scenario == 'hook-data' else '[]')
    else:
        if scenario == 'hidden-repo':
            print(canary + ' (HTTP 404)', file=sys.stderr)
            raise SystemExit(1)
        admin = False if scenario == 'nonadmin' else 'true' if scenario == 'string-admin' else True
        print(json.dumps({'full_name': 'example/project', 'permissions': {'admin': admin}, 'secret': canary}))
else:
    raise SystemExit('unexpected command')
'''


class DoctorFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='github-doctor-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.bin = self.directory / 'bin'
        self.bin.mkdir()
        self.home = self.directory / 'home'
        (self.home / '.ssh').mkdir(parents=True)
        (self.home / '.ssh/known_hosts').write_text('existing trust fixture\n')
        self.trace = self.directory / 'trace.jsonl'
        for name in ('gh', 'ssh'):
            file = self.bin / name
            file.write_text('#!' + sys.executable + '\n' + STUB)
            file.chmod(0o755)
        (self.bin / 'python3').symlink_to(sys.executable)
        (self.bin / 'dirname').symlink_to('/usr/bin/dirname')
        self.env = {'HOME': str(self.home), 'PATH': str(self.bin), 'TRACE': str(self.trace),
                    'TMPDIR': str(self.directory), 'PYTHONDONTWRITEBYTECODE': '1'}
        self.before = self.snapshot()

    def snapshot(self):
        return {str(path.relative_to(self.home)): (path.read_bytes(), path.stat().st_mode)
                for path in self.home.rglob('*') if path.is_file()}

    def run_doctor(self, scenario='healthy', args=(), root=ROOT, human=False):
        env = dict(self.env, SCENARIO=scenario)
        command = ['/bin/bash', str(root / 'bin/github-auth-doctor')]
        if not human:
            command += ['--format', 'json']
        result = subprocess.run(command + list(args), capture_output=True, text=True, env=env, timeout=8)
        self.assertNotIn(CANARY, result.stdout + result.stderr)
        self.assertNotIn('ghp_' + 'a' * 30, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), self.before)
        data = None if human or result.returncode == 2 else json.loads(result.stdout)
        return result, data

    def calls(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    @staticmethod
    def capability(data, name):
        return next(row for row in data['capabilities'] if row['capability'] == name)

    def test_https_default_does_not_run_irrelevant_ssh(self):
        result, data = self.run_doctor()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data['transport'], 'https')
        self.assertFalse(any(call[0] == 'ssh' for call in self.calls()))
        self.assertIn('https-git-transport', data['unverified'])
        self.assertEqual(self.capability(data, 'api-identity')['identity']['login'], 'fixture-user')

    def test_legacy_no_argument_human_invocation(self):
        result, _ = self.run_doctor(human=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('selected GitHub checks passed', result.stdout)

    def test_ssh_uses_existing_trust_and_matches_api_identity(self):
        result, data = self.run_doctor('ssh')
        self.assertEqual(result.returncode, 0)
        command = next(call for call in self.calls() if call[0] == 'ssh')
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('UpdateHostKeys=no', command)
        self.assertEqual(command[1:3], ['-F', '/dev/null'])
        self.assertNotIn('StrictHostKeyChecking=accept-new', command)
        self.assertEqual(self.capability(data, 'ssh-identity')['state'], 'ready')

    def test_ssh_mismatch_and_error_are_not_green_or_raw(self):
        for scenario in ('ssh-mismatch', 'ssh-failure'):
            with self.subTest(scenario=scenario):
                result, data = self.run_doctor(scenario)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.capability(data, 'ssh-identity')['state'], 'unknown')

    def test_timeout_and_output_flood_are_bounded(self):
        for scenario in ('hung', 'flood'):
            with self.subTest(scenario=scenario):
                started = time.monotonic()
                result, data = self.run_doctor(scenario, ['--timeout', '0.1'])
                self.assertLess(time.monotonic() - started, 3)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.capability(data, 'cli')['state'], 'unknown')

    def test_absent_tool_never_falls_back_to_host_path(self):
        (self.bin / 'gh').unlink()
        result, data = self.run_doctor()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.capability(data, 'cli')['state'], 'missing-tool')
        self.assertEqual(self.calls(), [])

    def test_invalid_or_sensitive_identity_fails_closed(self):
        for scenario in ('malformed', 'secret-identity'):
            with self.subTest(scenario=scenario):
                result, data = self.run_doctor(scenario)
                self.assertEqual(result.returncode, 1)
                self.assertIsNone(self.capability(data, 'api-identity')['identity'])

    def test_unauthenticated_is_distinct_and_does_not_probe_repository(self):
        result, data = self.run_doctor('unauthenticated', ['--repository', 'example/project'])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.capability(data, 'api-identity')['state'], 'unauthenticated')
        self.assertFalse(any(call[-1].startswith('repos/') for call in self.calls()))

    def test_optional_admin_is_nonblocking_until_selected(self):
        result, data = self.run_doctor('nonadmin', ['--repository', 'example/project'])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.capability(data, 'repository-admin')['state'], 'insufficient-permission')
        result, data = self.run_doctor('nonadmin', ['--repository', 'example/project', '--require-admin'])
        self.assertEqual(result.returncode, 1)
        self.assertTrue(self.capability(data, 'repository-admin')['blocks'])

    def test_admin_requires_boolean_not_truthy_string(self):
        result, data = self.run_doctor('string-admin', ['--repository', 'example/project', '--require-admin'])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.capability(data, 'repository-admin')['state'], 'unknown')

    def test_private_404_is_not_misreported_missing(self):
        result, data = self.run_doctor('hidden-repo', ['--repository', 'example/project'])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.capability(data, 'repository-read')['state'], 'unknown')

    def test_admin_and_webhook_read_never_mutate_or_disclose(self):
        for scenario in ('healthy', 'hook-data'):
            result, data = self.run_doctor(scenario, ['--repository', 'example/project', '--require-admin', '--check-webhooks'])
            self.assertEqual(result.returncode, 0)
            self.assertEqual(self.capability(data, 'webhook-read')['state'], 'ready')
        self.assertTrue(all(call[0] != 'gh' or call[1] in ('--version', 'config', 'api') for call in self.calls()))
        self.assertTrue(all(call[call.index('--method') + 1] == 'GET' for call in self.calls() if '--method' in call))

    def test_enterprise_host_scopes_every_api_command(self):
        result, _ = self.run_doctor(args=['--hostname', 'code.example.test'])
        self.assertEqual(result.returncode, 0)
        for call in self.calls():
            if '--hostname' in call:
                self.assertEqual(call[call.index('--hostname') + 1], 'code.example.test')

    def test_argument_errors_do_not_echo_input_or_run_probes(self):
        for args in (['--repository', '../private'], ['--require-admin'], ['--timeout', 'nan'],
                     ['--hostname', CANARY + '/bad'], ['--unknown', CANARY]):
            result, _ = self.run_doctor(args=args)
            self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_repeat_runs_preserve_home_and_receipt_meaning(self):
        first, a = self.run_doctor()
        second, b = self.run_doctor()
        a.pop('observedAt'); b.pop('observedAt')
        self.assertEqual(a, b)
        self.assertEqual((first.returncode, second.returncode), (0, 0))

    def test_extracted_package_layout_invokes_library_without_network(self):
        # Packaging copies bin and lib together; exercise that layout away from
        # the checkout, including a path with spaces and no host tools on PATH.
        package = self.directory / 'extracted package'
        (package / 'bin').mkdir(parents=True)
        (package / 'lib').mkdir()
        shutil.copy2(ROOT / 'bin/github-auth-doctor', package / 'bin')
        shutil.copy2(ROOT / 'lib/github_auth_doctor.py', package / 'lib')
        result, data = self.run_doctor(root=package)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(data['ready'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
