"""Adversarial source preflight fixtures; no live credentials or network."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import urllib.error

import source_preflight as p

HISTORICAL = '44a48f20bbef29ff86d728347481a22bcd13a47a'


def args(root):
    return argparse.Namespace(repository=str(root), identity='pinklon/skills',
        sha=HISTORICAL, pr=None, artifact=['scripts/test_design_os_portability.py'],
        required_tool=[], required_skill=[], scratch=str(root), min_scratch_mb=0,
        api_token_env=None, required_model=None, model_timeout=20)


class SourcePreflightTests(unittest.TestCase):
    def test_historical_missing_commit_no_remote_no_gh_and_no_alternate(self):
        with tempfile.TemporaryDirectory() as root:
            a = args(root)
            with (mock.patch.object(p, 'git_source', side_effect=p.Failed('REMOTE_NOT_CONFIGURED')),
                  mock.patch.object(p.shutil, 'which', return_value=None)):
                with self.assertRaises(p.Failed) as failure:
                    p.preflight(a)
            self.assertEqual(failure.exception.code, 'SOURCE_UNAVAILABLE')
            self.assertEqual([x['reason'] for x in failure.exception.attempts],
                             ['REMOTE_NOT_CONFIGURED', 'TOOL_UNAVAILABLE', 'AUTH_MISSING'])

    def test_historical_approved_api_fallback_without_gh(self):
        with tempfile.TemporaryDirectory() as root:
            a = args(root)
            a.api_token_env = 'GH_TOKEN'
            with (mock.patch.object(p, 'git_source', side_effect=p.Failed('SOURCE_COMMIT_MISSING')),
                  mock.patch.object(p.shutil, 'which', return_value=None),
                  mock.patch.object(p, 'api_source', return_value={
                     'transport': 'authenticated-github-api',
                     'artifact_sha256': {a.artifact[0]: 'a' * 64}}) as api):
                source, attempts, _ = p.preflight(a)
            self.assertEqual(source['transport'], 'authenticated-github-api')
            self.assertEqual(attempts[0]['reason'], 'SOURCE_COMMIT_MISSING')
            api.assert_called_once_with(a, False)

    def test_wrong_repository_and_wrong_head_never_fall_back(self):
        for reason in ('WRONG_REPOSITORY', 'WRONG_HEAD'):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as root:
                a = args(root)
                with (mock.patch.object(p, 'git_source', side_effect=p.Failed(reason)),
                      mock.patch.object(p, 'api_source') as api):
                    with self.assertRaises(p.Failed) as failure:
                        p.preflight(a)
                self.assertEqual(failure.exception.code, reason)
                api.assert_not_called()

    def test_missing_skill_and_failed_scratch(self):
        with tempfile.TemporaryDirectory() as root:
            a = args(root)
            a.required_skill = [str(Path(root) / 'missing-skill')]
            with self.assertRaises(p.Failed) as failure:
                p.preflight(a)
            self.assertEqual(failure.exception.code, 'SKILL_MISSING')
            a.required_skill = []
            a.min_scratch_mb = 999999999
            with self.assertRaises(p.Failed) as failure:
                p.preflight(a)
            self.assertEqual(failure.exception.code, 'SCRATCH_EXHAUSTED')

    def test_401_403_and_network_denial(self):
        a = args('/tmp')
        a.api_token_env = 'GH_TOKEN'
        for status, expected in ((401, 'AUTH_MISSING'), (403, 'ACCESS_DENIED'),
                                 (503, 'NETWORK_DENIED')):
            with (self.subTest(status=status), mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
                  mock.patch.object(p.urllib.request, 'build_opener') as opener):
                error = urllib.error.HTTPError(
                    'https://api.github.com/', status, 'fixture', {}, io.BytesIO())
                opener.return_value.open.side_effect = error
                with self.assertRaises(p.Failed) as failure:
                    p.api_source(a, False)
                error.close()
            self.assertEqual(failure.exception.code, expected)

    def test_api_identity_commit_pr_and_artifact_must_match(self):
        a = args('/tmp')
        a.pr = 348
        a.api_token_env = 'GH_TOKEN'
        content = 'Zml4dHVyZQ=='
        responses = [
            {'full_name': a.identity}, {'sha': a.sha},
            {'base': {'repo': {'full_name': a.identity}}, 'head': {'sha': a.sha}},
            {'type': 'file', 'path': a.artifact[0], 'encoding': 'base64', 'content': content}]
        with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
              mock.patch.object(p, 'api_get', side_effect=responses)):
            result = p.api_source(a, False)
        self.assertEqual(result['artifact_sha256'][a.artifact[0]], p.hashlib.sha256(b'fixture').hexdigest())
        responses[2]['head']['sha'] = 'b' * 40
        with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
              mock.patch.object(p, 'api_get', side_effect=responses)):
            with self.assertRaises(p.Failed) as failure:
                p.api_source(a, False)
        self.assertEqual(failure.exception.code, 'WRONG_HEAD')

    def test_remote_identity_and_path_boundaries(self):
        self.assertEqual(p.remote_identity('git@github.com:pinklon/skills.git'), 'pinklon/skills')
        self.assertIsNone(p.remote_identity('https://elsewhere/pinklon/skills.git'))
        for value in ('../private', '/absolute', '-option'):
            with self.assertRaises(p.Failed):
                p.artifact_path(value)

    def test_local_commit_is_not_proof_of_remote_exact_sha(self):
        with tempfile.TemporaryDirectory() as root:
            a = args(root)
            commands = [
                subprocess.CompletedProcess([], 0, root + '\n', ''),
                subprocess.CompletedProcess([], 0, 'git@github.com:pinklon/skills.git\n', ''),
                subprocess.CompletedProcess([], 0, 'b' * 40 + '\trefs/heads/main\n', '')]
            with (mock.patch.object(p.shutil, 'which', return_value='/usr/bin/git'),
                  mock.patch.object(p, 'command', side_effect=commands)):
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
            self.assertEqual(failure.exception.code, 'SOURCE_COMMIT_REMOTE_UNVERIFIED')

    def test_https_git_transport_is_explicitly_unqualified(self):
        with tempfile.TemporaryDirectory() as root:
            a = args(root)
            commands = [
                subprocess.CompletedProcess([], 0, root + '\n', ''),
                subprocess.CompletedProcess([], 0, 'https://github.com/pinklon/skills.git\n', '')]
            with (mock.patch.object(p.shutil, 'which', return_value='/usr/bin/git'),
                  mock.patch.object(p, 'command', side_effect=commands)):
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
            self.assertEqual(failure.exception.code, 'UNSUPPORTED_GIT_TRANSPORT')

    def test_unavailable_model_and_bounded_timeout(self):
        with (mock.patch.object(p.shutil, 'which', return_value='/usr/bin/codex'),
              mock.patch.object(p.subprocess, 'run') as run):
            run.return_value = subprocess.CompletedProcess([], 1, '', 'unknown model fixture')
            with self.assertRaises(p.Failed) as failure:
                p.model_probe('fixture-model', '/tmp', 5)
            self.assertEqual(failure.exception.code, 'MODEL_UNAVAILABLE')
            self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs['timeout'], 5)
            run.side_effect = subprocess.TimeoutExpired([], 5)
            with self.assertRaises(p.Failed) as failure:
                p.model_probe('fixture-model', '/tmp', 5)
            self.assertEqual(failure.exception.code, 'TIMEOUT_OR_STDIN_WAIT')

    def test_receipt_binds_checked_prerequisites_without_secret_or_path_leak(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'receipt.json'
            argv = ['--repository', root, '--identity', 'pinklon/skills', '--sha',
                    HISTORICAL, '--artifact', 'scripts/test_design_os_portability.py',
                    '--required-tool', 'python3', '--required-skill',
                    str(Path(root) / 'managed-skill'), '--min-scratch-mb', '5',
                    '--output', str(output)]
            source = {'transport': 'authenticated-github-api', 'artifact_sha256':
                      {'scripts/test_design_os_portability.py': 'a' * 64}}
            with (mock.patch.object(p, 'preflight', return_value=(source, [], 99_000_000)),
                  mock.patch('sys.stdout', new_callable=io.StringIO)):
                self.assertEqual(p.main(argv), 0)
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt['required_tools'], ['python3'])
            self.assertEqual(receipt['required_skill_names'], ['managed-skill'])
            self.assertTrue(receipt['checks']['scratch_headroom'])
            self.assertTrue(receipt['checks']['tool_presence'])
            self.assertTrue(receipt['checks']['skill_wrapper_presence'])
            self.assertEqual(receipt['checks']['model_probe'], 'NOT_REQUESTED')
            self.assertNotIn(root, output.read_text())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main(verbosity=2)
