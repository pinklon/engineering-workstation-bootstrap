"""Adversarial source preflight fixtures; no live credentials or network."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zlib

import source_preflight as p

HISTORICAL = '44a48f20bbef29ff86d728347481a22bcd13a47a'


def args(root):
    return argparse.Namespace(repository=str(root), identity='pinklon/skills',
        sha=HISTORICAL, pr=None, artifact=['scripts/test_design_os_portability.py'],
        required_tool=[], required_skill=[], scratch=str(root), min_scratch_mb=0,
        api_token_env=None, required_model=None, model_timeout=20)


def git(root, *argv):
    return subprocess.run(['git', '-C', str(root), *argv], check=True,
                          capture_output=True, text=True).stdout.strip()


def local_history(root):
    git(root, 'init', '-q')
    git(root, 'config', 'user.name', 'Fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    git(root, 'remote', 'add', 'origin', 'git@github.com:pinklon/skills.git')
    artifact = Path(root) / 'scripts/test_design_os_portability.py'
    artifact.parent.mkdir()
    artifact.write_text('historical source\n')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'historical')
    historical = git(root, 'rev-parse', 'HEAD')
    artifact.write_text('remote tip source\n')
    git(root, 'commit', '-qam', 'tip')
    tip = git(root, 'rev-parse', 'HEAD')
    return historical, tip


def api_fixture(a, content=b'fixture'):
    root_tree, scripts_tree = 'a' * 40, 'b' * 40
    blob_sha = p.hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    responses = [
        {'full_name': a.identity},
        {'sha': a.sha, 'tree': {'sha': root_tree}}]
    if a.pr:
        responses.append({'base': {'repo': {'full_name': a.identity}},
                          'head': {'sha': a.sha}})
    responses.extend([
        {'sha': root_tree, 'truncated': False, 'tree': [
            {'path': 'scripts', 'type': 'tree', 'mode': '040000', 'sha': scripts_tree}]},
        {'sha': scripts_tree, 'truncated': False, 'tree': [
            {'path': 'test_design_os_portability.py', 'type': 'blob',
             'mode': '100644', 'sha': blob_sha, 'size': len(content)}]},
        {'sha': blob_sha, 'encoding': 'base64', 'size': len(content),
         'content': base64.b64encode(content).decode()}])
    return responses


class SourcePreflightTests(unittest.TestCase):
    def test_explicit_invalid_pr_refuses_before_transport_or_source_proof(self):
        for supplied in (0, -1, False, True, '0'):
            with self.subTest(pr=supplied):
                a = args('/tmp')
                a.pr = supplied
                with (mock.patch.object(p, 'git_source', side_effect=AssertionError('git transport reached')) as git_source,
                      mock.patch.object(p, 'api_source', side_effect=AssertionError('API transport reached')) as api_source):
                    with self.assertRaises(p.Failed) as failure:
                        p.preflight(a)
                self.assertEqual(failure.exception.code, 'INVALID_PR_NUMBER')
                git_source.assert_not_called()
                api_source.assert_not_called()

                with mock.patch.object(p.shutil, 'which', side_effect=AssertionError('git transport reached')) as which:
                    with self.assertRaises(p.Failed) as failure:
                        p.git_source(a)
                self.assertEqual(failure.exception.code, 'INVALID_PR_NUMBER')
                which.assert_not_called()

                with mock.patch.object(p, 'api_get', side_effect=AssertionError('API transport reached')) as api_get:
                    with self.assertRaises(p.Failed) as failure:
                        p.api_source(a, True)
                self.assertEqual(failure.exception.code, 'INVALID_PR_NUMBER')
                api_get.assert_not_called()

        with (mock.patch.object(p, 'git_source', side_effect=AssertionError('git transport reached')) as git_source,
              mock.patch('sys.stdout', new_callable=io.StringIO) as stdout):
            self.assertEqual(p.main(['--repository', '/tmp', '--identity', 'pinklon/skills',
                                     '--sha', HISTORICAL, '--pr', '0', '--artifact',
                                     'scripts/test_design_os_portability.py',
                                     '--min-scratch-mb', '0']), 1)
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt['reason'], 'INVALID_PR_NUMBER')
        self.assertFalse(receipt['source_verified'])
        git_source.assert_not_called()

    def test_gh_api_output_is_bounded_before_buffering(self):
        normal = p.bounded_api_command([sys.executable, '-c',
            'import sys; sys.stdout.buffer.write(b"ok")'], 10)
        self.assertEqual(normal, b'ok')
        with self.assertRaises(p.Failed) as failure:
            p.bounded_api_command([sys.executable, '-c',
                'import sys; sys.stdout.buffer.write(b"x" * 100000)'], 10)
        self.assertEqual(failure.exception.code, 'API_RESPONSE_TOO_LARGE')

    def test_gh_api_is_pinned_to_authenticated_github_host(self):
        with (mock.patch.dict(os.environ, {'GH_HOST': 'enterprise.example.invalid'}),
              mock.patch.object(p, 'command', return_value=subprocess.CompletedProcess([], 0, '', '')),
              mock.patch.object(p, 'bounded_api_command', return_value=b'{"full_name":"pinklon/skills"}')
              as bounded):
            result = p.api_get('repos/pinklon/skills', None, True)
        self.assertEqual(result['full_name'], 'pinklon/skills')
        self.assertEqual(bounded.call_args.args[0][:4],
                         ['gh', 'api', '--hostname', 'github.com'])

    def test_maximum_blob_wire_json_fits_bounded_api_read(self):
        encoded = base64.b64encode(b'\xff' * p.MAX_BYTES).decode()
        wrapped = '\n'.join(encoded[i:i + 60] for i in range(0, len(encoded), 60))
        payload = json.dumps({'content': wrapped, 'encoding': 'base64',
                              'size': p.MAX_BYTES, 'sha': 'a' * 40}).encode()
        old_unwrapped_limit = len(encoded) + 4096
        self.assertGreater(len(payload), old_unwrapped_limit)
        self.assertLessEqual(len(payload), p.MAX_BLOB_RESPONSE_BYTES)
        with tempfile.TemporaryDirectory() as root:
            wire = Path(root) / 'blob.json'
            wire.write_bytes(payload)
            actual = p.bounded_api_command([sys.executable, '-c',
                'import pathlib,sys; sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())',
                str(wire)], p.MAX_BLOB_RESPONSE_BYTES)
        self.assertEqual(len(actual), len(payload))

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
        responses = api_fixture(a)
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
            historical, tip = local_history(root)
            a = args(root)
            a.sha = historical
            git(root, 'checkout', '-qb', 'unrelated', historical)
            (Path(root) / a.artifact[0]).write_text('unanchored source\n')
            git(root, 'commit', '-qam', 'unanchored')
            a.sha = git(root, 'rev-parse', 'HEAD')
            real_command = p.command

            def remote_command(argv, **kwargs):
                if argv[:3] == p.GIT + ['ls-remote']:
                    return subprocess.CompletedProcess(argv, 0, tip + '\trefs/heads/main\n', '')
                return real_command(argv, **kwargs)

            with mock.patch.object(p, 'command', side_effect=remote_command):
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
            self.assertEqual(failure.exception.code, 'SOURCE_COMMIT_REMOTE_UNVERIFIED')

    def test_historical_commit_requires_authenticated_advertised_ancestor(self):
        with tempfile.TemporaryDirectory() as root:
            historical, tip = local_history(root)
            a = args(root)
            a.sha = historical
            real_command = p.command

            remote_environments = []

            def remote_command(argv, **kwargs):
                if argv[:4] == p.GIT + ['ls-remote', '--refs']:
                    remote_environments.append(kwargs.get('env'))
                    return subprocess.CompletedProcess(argv, 0, tip + '\trefs/heads/main\n', '')
                if argv[:3] == p.GIT + ['ls-remote']:
                    remote_environments.append(kwargs.get('env'))
                    return subprocess.CompletedProcess(argv, 0, tip + '\trefs/pull/348/head\n', '')
                return real_command(argv, **kwargs)

            with mock.patch.object(p, 'command', side_effect=remote_command):
                result = p.git_source(a)
                self.assertEqual(result['artifact_sha256'][a.artifact[0]],
                                 p.hashlib.sha256(b'historical source\n').hexdigest())
                a.pr = 348
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
            self.assertEqual(failure.exception.code, 'WRONG_HEAD')
            self.assertEqual(len(remote_environments), 3)
            self.assertTrue(all(env['GIT_SSH_COMMAND'] == p.SSH_COMMAND
                                for env in remote_environments))

    def test_corrupt_local_commit_cannot_use_genuine_remote_advertisement(self):
        for corrupt_tip in (False, True):
            with self.subTest(corrupt_tip=corrupt_tip), tempfile.TemporaryDirectory() as root:
                historical, tip = local_history(root)
                a = args(root)
                a.sha = historical if corrupt_tip else tip
                object_sha = tip if corrupt_tip else a.sha
                object_path = Path(root) / '.git/objects' / object_sha[:2] / object_sha[2:]
                original = zlib.decompress(object_path.read_bytes())
                self.assertIn(b'tip\n', original)
                forged = original.replace(b'tip\n', b'forged\n', 1)
                object_path.chmod(0o600)
                object_path.write_bytes(zlib.compress(forged))
                self.assertEqual(git(root, 'cat-file', '-t', object_sha), 'commit')
                real_command = p.command

                def remote_command(argv, **kwargs):
                    if argv[:3] == p.GIT + ['ls-remote']:
                        return subprocess.CompletedProcess(argv, 0,
                            tip + '\trefs/heads/main\n', '')
                    if argv == p.GIT + ['cat-file', '-e', a.sha + '^{commit}']:
                        # Older Git versions may accept this lookup; current Git
                        # can fail earlier. Exercise the explicit hash check.
                        return subprocess.CompletedProcess(argv, 0, '', '')
                    return real_command(argv, **kwargs)

                with mock.patch.object(p, 'command', side_effect=remote_command):
                    with self.assertRaises(p.Failed) as failure:
                        p.git_source(a)
                self.assertEqual(failure.exception.code, 'SOURCE_COMMIT_REMOTE_UNVERIFIED')

    def test_fixed_ssh_command_ignores_host_routing_configuration(self):
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / 'ssh-config'
            config.write_text('Host github.com\n  HostName forged.example.invalid\n'
                              '  ProxyCommand /bin/false\n  StrictHostKeyChecking no\n')
            unsafe = subprocess.run([str(p.SSH_BINARY), '-F', str(config), '-G',
                                     'github.com'], capture_output=True, text=True, check=True)
            self.assertIn('hostname forged.example.invalid', unsafe.stdout)
            safe = subprocess.run(shlex.split(p.SSH_COMMAND) + ['-G', 'github.com'],
                                  capture_output=True, text=True, check=True)
            self.assertIn('hostname github.com\n', safe.stdout)
            self.assertIn('stricthostkeychecking true\n', safe.stdout)
            self.assertIn('hostkeyalias github.com\n', safe.stdout)
            self.assertNotIn('forged.example.invalid', safe.stdout)
            self.assertNotIn('proxycommand /bin/false', safe.stdout)

    def test_absent_remote_tip_object_cannot_anchor_local_commit(self):
        with tempfile.TemporaryDirectory() as root:
            historical, _ = local_history(root)
            a = args(root)
            a.sha = historical
            real_command = p.command

            def remote_command(argv, **kwargs):
                if argv[:3] == p.GIT + ['ls-remote']:
                    return subprocess.CompletedProcess(argv, 0,
                        'b' * 40 + '\trefs/heads/main\n', '')
                return real_command(argv, **kwargs)

            with mock.patch.object(p, 'command', side_effect=remote_command):
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
            self.assertEqual(failure.exception.code, 'SOURCE_COMMIT_REMOTE_UNVERIFIED')

    def test_git_artifact_must_be_blob_and_size_is_checked_before_read(self):
        with tempfile.TemporaryDirectory() as root:
            historical, tip = local_history(root)
            a = args(root)
            a.sha = historical
            real_command = p.command

            def remote_command(argv, **kwargs):
                if argv[:3] == p.GIT + ['ls-remote']:
                    return subprocess.CompletedProcess(argv, 0, tip + '\trefs/heads/main\n', '')
                return real_command(argv, **kwargs)

            with mock.patch.object(p, 'command', side_effect=remote_command):
                a.artifact = ['scripts']
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
                self.assertEqual(failure.exception.code, 'SOURCE_ARTIFACT_UNAVAILABLE')

                a.artifact = ['scripts/test_design_os_portability.py']
                real_run = subprocess.run

                def no_blob_read(argv, **kwargs):
                    if argv[:3] == p.GIT + ['show']:
                        self.fail('oversized blob was read before the size gate')
                    return real_run(argv, **kwargs)

                with (mock.patch.object(p, 'MAX_BYTES', 10),
                      mock.patch.object(p.subprocess, 'run', side_effect=no_blob_read)):
                    with self.assertRaises(p.Failed) as failure:
                        p.git_source(a)
                self.assertEqual(failure.exception.code, 'SOURCE_ARTIFACT_UNAVAILABLE')

    def test_git_replace_refs_cannot_change_authenticated_source_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            historical, tip = local_history(root)
            a = args(root)
            a.sha = historical
            git(root, 'checkout', '-qb', 'forged', historical)
            (Path(root) / a.artifact[0]).write_text('forged source\n')
            git(root, 'commit', '-qam', 'forged')
            forged = git(root, 'rev-parse', 'HEAD')
            git(root, 'replace', historical, forged)
            self.assertEqual(git(root, 'show', f'{historical}:{a.artifact[0]}'), 'forged source')
            real_command = p.command

            def remote_command(argv, **kwargs):
                if argv[:3] == p.GIT + ['ls-remote']:
                    return subprocess.CompletedProcess(argv, 0, tip + '\trefs/heads/main\n', '')
                return real_command(argv, **kwargs)

            with mock.patch.object(p, 'command', side_effect=remote_command):
                result = p.git_source(a)
            self.assertEqual(result['artifact_sha256'][a.artifact[0]],
                             p.hashlib.sha256(b'historical source\n').hexdigest())

    def test_ssh_command_overrides_cannot_forge_remote_advertisement(self):
        with tempfile.TemporaryDirectory() as root:
            historical, _ = local_history(root)
            a = args(root)
            a.sha = historical
            git(root, 'config', 'core.sshCommand', 'sh -c "printf forged"')
            with self.assertRaises(p.Failed) as failure:
                p.git_source(a)
            self.assertEqual(failure.exception.code, 'UNSUPPORTED_GIT_TRANSPORT')
            git(root, 'config', '--unset', 'core.sshCommand')
            for variable in ('GIT_SSH_COMMAND', 'GIT_SSH'):
                with self.subTest(variable=variable), mock.patch.dict(os.environ,
                     {variable: '/tmp/forged-ssh'}):
                    with self.assertRaises(p.Failed) as failure:
                        p.git_source(a)
                self.assertEqual(failure.exception.code, 'UNSUPPORTED_GIT_TRANSPORT')
            git(root, 'config', 'url.file:///tmp/forged.insteadOf', 'git@github.com:')
            with self.assertRaises(p.Failed) as failure:
                p.require_unmodified_ssh_transport(Path(root))
            self.assertEqual(failure.exception.code, 'UNSUPPORTED_GIT_TRANSPORT')

    def test_local_grafts_cannot_prove_remote_ancestry(self):
        with tempfile.TemporaryDirectory() as root:
            historical, tip = local_history(root)
            a = args(root)
            a.sha = historical
            grafts = Path(root) / '.git/info/grafts'
            grafts.write_text(tip + ' ' + historical + '\n')
            real_command = p.command

            def remote_command(argv, **kwargs):
                if argv[:3] == p.GIT + ['ls-remote']:
                    return subprocess.CompletedProcess(argv, 0, tip + '\trefs/heads/main\n', '')
                return real_command(argv, **kwargs)

            with mock.patch.object(p, 'command', side_effect=remote_command):
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
            self.assertEqual(failure.exception.code, 'SOURCE_COMMIT_REMOTE_UNVERIFIED')

    def test_git_and_api_reject_symlink_artifacts(self):
        with tempfile.TemporaryDirectory() as root:
            _, tip = local_history(root)
            a = args(root)
            link = Path(root) / 'scripts/link.py'
            link.symlink_to('test_design_os_portability.py')
            git(root, 'add', '.')
            git(root, 'commit', '-qm', 'symlink')
            a.sha = git(root, 'rev-parse', 'HEAD')
            a.artifact = ['scripts/link.py']
            real_command = p.command

            def remote_command(argv, **kwargs):
                if argv[:3] == p.GIT + ['ls-remote']:
                    return subprocess.CompletedProcess(argv, 0, a.sha + '\trefs/heads/main\n', '')
                return real_command(argv, **kwargs)

            with mock.patch.object(p, 'command', side_effect=remote_command):
                with self.assertRaises(p.Failed) as failure:
                    p.git_source(a)
            self.assertEqual(failure.exception.code, 'SOURCE_ARTIFACT_UNAVAILABLE')

        a = args('/tmp')
        a.api_token_env = 'GH_TOKEN'
        responses = api_fixture(a)
        responses[-2]['tree'][0]['mode'] = '120000'
        with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
              mock.patch.object(p, 'api_get', side_effect=responses)):
            with self.assertRaises(p.Failed) as failure:
                p.api_source(a, False)
        self.assertEqual(failure.exception.code, 'SOURCE_ARTIFACT_UNAVAILABLE')

    def test_api_blob_supports_artifact_above_one_mb_with_bounded_response(self):
        a = args('/tmp')
        a.api_token_env = 'GH_TOKEN'
        content = b'large fixture\n' * 100_000
        self.assertTrue(1_000_000 < len(content) < p.MAX_BYTES)
        responses = api_fixture(a, content)
        with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
              mock.patch.object(p, 'api_get', side_effect=responses) as get):
            result = p.api_source(a, False)
        self.assertEqual(result['artifact_sha256'][a.artifact[0]],
                         p.hashlib.sha256(content).hexdigest())
        self.assertEqual(get.call_args.kwargs['max_bytes'], p.MAX_BLOB_RESPONSE_BYTES)

    def test_api_blob_must_match_tree_sha_and_declared_limit(self):
        a = args('/tmp')
        a.api_token_env = 'GH_TOKEN'
        responses = api_fixture(a)
        responses[-1]['content'] = base64.b64encode(b'changed').decode()
        with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
              mock.patch.object(p, 'api_get', side_effect=responses)):
            with self.assertRaises(p.Failed) as failure:
                p.api_source(a, False)
        self.assertEqual(failure.exception.code, 'TOOL_SCHEMA_MISMATCH')

        responses = api_fixture(a)
        responses[-2]['tree'][0]['size'] = p.MAX_BYTES + 1
        with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
              mock.patch.object(p, 'api_get', side_effect=responses[:-1]) as get):
            with self.assertRaises(p.Failed) as failure:
                p.api_source(a, False)
        self.assertEqual(failure.exception.code, 'SOURCE_ARTIFACT_UNAVAILABLE')
        self.assertEqual(get.call_count, 4)

    def test_api_response_shapes_fail_closed(self):
        a = args('/tmp')
        a.pr = 348
        a.api_token_env = 'GH_TOKEN'
        valid = api_fixture(a)
        malformed = [(0, []), (0, None), (0, {'full_name': 42}),
                     (1, []), (1, {'sha': None}),
                     (2, None), (2, {'base': []}),
                     (2, {'base': {'repo': []}, 'head': {'sha': a.sha}}),
                     (2, {'base': {'repo': {'full_name': a.identity}}, 'head': []}),
                     (3, []), (3, {'sha': 'a' * 40, 'tree': None, 'truncated': False}),
                     (4, {'sha': 'b' * 40, 'tree': [None], 'truncated': False}),
                     (5, []), (5, {'sha': valid[-1]['sha'], 'encoding': 'base64',
                                  'size': 7, 'content': None})]
        for index, bad in malformed:
            with self.subTest(index=index, bad=bad):
                responses = valid.copy()
                responses[index] = bad
                with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
                      mock.patch.object(p, 'api_get', side_effect=responses)):
                    with self.assertRaises(p.Failed) as failure:
                        p.api_source(a, False)
                self.assertEqual(failure.exception.code, 'TOOL_SCHEMA_MISMATCH')

    def test_base64_rejects_corruption_and_accepts_github_line_breaks(self):
        a = args('/tmp')
        a.api_token_env = 'GH_TOKEN'
        valid = api_fixture(a)
        valid[-1]['content'] = 'Zml4\r\ndHVyZQ==\n'
        with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
              mock.patch.object(p, 'api_get', side_effect=valid)):
            result = p.api_source(a, False)
        self.assertEqual(result['artifact_sha256'][a.artifact[0]],
                         p.hashlib.sha256(b'fixture').hexdigest())
        for bad in ('Zml4#dHVyZQ==', 'Zml4dHVyZQ=', 'Zml4dHVyZQ===',
                    'Zml4dHVyZQ==!', 'Zml4dHVyZQ'):
            with self.subTest(bad=bad):
                responses = [dict(x) for x in valid]
                responses[-1]['content'] = bad
                with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
                      mock.patch.object(p, 'api_get', side_effect=responses)):
                    with self.assertRaises(p.Failed) as failure:
                        p.api_source(a, False)
                self.assertEqual(failure.exception.code, 'TOOL_SCHEMA_MISMATCH')

    def test_malformed_api_yields_blocked_receipt_without_source_proof(self):
        with tempfile.TemporaryDirectory() as root:
            argv = ['--repository', root, '--identity', 'pinklon/skills', '--sha',
                    HISTORICAL, '--artifact', 'scripts/test_design_os_portability.py',
                    '--api-token-env', 'GH_TOKEN', '--min-scratch-mb', '0']
            with (mock.patch.dict(os.environ, {'GH_TOKEN': 'fixture-value'}),
                  mock.patch.object(p, 'git_source', side_effect=p.Failed('REMOTE_NOT_CONFIGURED')),
                  mock.patch.object(p.shutil, 'which', return_value=None),
                  mock.patch.object(p, 'api_get', return_value=[]),
                  mock.patch('sys.stdout', new_callable=io.StringIO) as stdout):
                self.assertEqual(p.main(argv), 1)
            receipt = json.loads(stdout.getvalue())
            self.assertFalse(receipt['source_verified'])
            self.assertEqual(receipt['reason'], 'SOURCE_UNAVAILABLE')
            self.assertEqual(receipt['attempts'][-1]['reason'], 'TOOL_SCHEMA_MISMATCH')

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

    def test_receipt_output_does_not_clobber_file_or_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            argv = ['--repository', root, '--identity', 'pinklon/skills', '--sha',
                    HISTORICAL, '--artifact', 'scripts/test_design_os_portability.py',
                    '--output', str(Path(root) / 'receipt.json')]
            source = {'transport': 'fixture', 'artifact_sha256': {}}
            output = Path(root) / 'receipt.json'
            output.write_text('existing data')
            with (mock.patch.object(p, 'preflight', return_value=(source, [], 1)),
                  mock.patch('sys.stdout', new_callable=io.StringIO) as stdout):
                self.assertEqual(p.main(argv), 1)
            self.assertEqual(output.read_text(), 'existing data')
            self.assertEqual(json.loads(stdout.getvalue())['reason'], 'OUTPUT_EXISTS')
            output.unlink()
            target = Path(root) / 'target.json'
            target.write_text('symlink target')
            output.symlink_to(target)
            with (mock.patch.object(p, 'preflight', return_value=(source, [], 1)),
                  mock.patch('sys.stdout', new_callable=io.StringIO) as stdout):
                self.assertEqual(p.main(argv), 1)
            self.assertEqual(target.read_text(), 'symlink target')
            self.assertEqual(json.loads(stdout.getvalue())['reason'], 'OUTPUT_SYMLINK_REFUSED')

    def test_receipt_output_race_cannot_replace_new_file(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'receipt.json'
            argv = ['--repository', root, '--identity', 'pinklon/skills', '--sha',
                    HISTORICAL, '--artifact', 'scripts/test_design_os_portability.py',
                    '--output', str(output)]

            def raced_link(_source, destination):
                Path(destination).write_text('concurrent writer')
                raise FileExistsError(destination)

            with (mock.patch.object(p, 'preflight', return_value=({'transport': 'fixture'}, [], 1)),
                  mock.patch.object(p.os, 'link', side_effect=raced_link),
                  mock.patch('sys.stdout', new_callable=io.StringIO) as stdout):
                self.assertEqual(p.main(argv), 1)
            self.assertEqual(output.read_text(), 'concurrent writer')
            self.assertEqual(json.loads(stdout.getvalue())['reason'], 'OUTPUT_EXISTS')
            self.assertEqual(sorted(x.name for x in Path(root).iterdir()), ['receipt.json'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
