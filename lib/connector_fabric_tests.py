"""Deterministic protocol fixtures; never evidence of a live provider."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import connector_fabric as fabric
import connector_client as native


class Headers(dict):
    def get_content_type(self):
        return 'application/json'


class Response:
    def __init__(self, data):
        self.data = json.dumps(data).encode()
        self.headers = Headers({'Mcp-Session-Id': 'fixture-session'})

    def read(self, limit):
        return self.data[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class ProtocolFixture:
    def __init__(self, mode='healthy'):
        self.calls = []
        self.mode = mode

    def open(self, request, timeout):
        data = json.loads(request.data)
        self.calls.append(data)
        method = data['method']
        if self.mode == 'offline':
            raise OSError('untrusted error containing private provider payload')
        if method == 'initialize':
            result = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'fixture', 'version': '1'}}
        elif method == 'notifications/initialized':
            return Response({})
        elif method == 'tools/list':
            result = {'tools': [{'name': 'read'}]}
            if self.mode == 'missing-tool':
                result = {'tools': []}
            if self.mode == 'pagination':
                result = {'tools': [{'name': 'other'}], 'nextCursor': 'page2'} if not data['params'] else result
            if self.mode == 'cursor-loop':
                result['nextCursor'] = 'same'
            if self.mode == 'write-exposed':
                result['tools'].append({'name': 'create_issue'})
        else:
            if data['params']['name'] == 'create_issue':
                return Response({'jsonrpc': '2.0', 'id': data['id'],
                                 'error': {'code': -32601, 'message': 'absent'}})
            result = {'content': [{'type': 'text', 'text': 'canary'}]}
            if self.mode == 'read-error':
                result = {'isError': True, 'content': [{'type': 'text', 'text': 'provider error'}]}
        return Response({'jsonrpc': '2.0', 'id': data.get('id'), 'result': result})


class FabricTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.connector = {'id': 'fixture', 'read_capabilities': ['read'],
                          'read_canary': {'tool': 'read', 'arguments': {}},
                          'governed_write_capabilities': [], 'forbidden_tools': ['create_issue']}
        self.config = {'url': 'https://fixture.invalid/mcp'}

    def tearDown(self):
        self.temp.cleanup()

    def probe(self, mode='healthy', surface='local-shell', restart=True):
        fixture = ProtocolFixture(mode)
        with patch('urllib.request.build_opener', return_value=fixture), \
                patch.object(fabric, 'restart_read', return_value=restart):
            result = fabric.probe(self.connector, self.config, surface, self.home)
        return result, fixture

    def test_real_protocol_sequence_and_negative_call(self):
        row, fixture = self.probe()
        self.assertTrue(row['qualified'])
        self.assertEqual(row['health'], 'RESTART_PERSISTENT')
        self.assertEqual(fixture.calls[0]['method'], 'initialize')
        self.assertEqual(fixture.calls[1]['method'], 'notifications/initialized')
        self.assertTrue(any(c.get('params', {}).get('name') == 'create_issue' for c in fixture.calls))

    def test_protocol_inventory_paginates(self):
        self.assertTrue(self.probe('pagination')[0]['qualified'])
        self.assertFalse(self.probe('cursor-loop')[0]['qualified'])

    def test_failures_never_qualify(self):
        for mode in ['offline', 'missing-tool', 'read-error', 'write-exposed']:
            with self.subTest(mode=mode):
                row, _ = self.probe(mode)
                self.assertFalse(row['qualified'])
                self.assertNotIn('private provider payload', json.dumps(row))

    def test_transport_restart_cannot_replace_shell_restart(self):
        row, _ = self.probe(restart=False)
        self.assertTrue(row['new_transport_session_read'])
        self.assertFalse(row['checks']['restart'])
        self.assertFalse(row['qualified'])

    def test_shell_cannot_assert_other_surfaces(self):
        for surface in fabric.SURFACES[1:]:
            row, fixture = self.probe(surface=surface)
            self.assertFalse(row['qualified'])
            self.assertEqual(row['health'], 'UNAVAILABLE')
            self.assertEqual(fixture.calls, [])

    def test_write_inventory_without_canary_fails(self):
        self.connector['governed_write_capabilities'] = ['read']
        row, _ = self.probe()
        self.assertTrue(row['checks']['write_capability'])
        self.assertFalse(row['checks']['write_canary'])
        self.assertFalse(row['qualified'])

    def test_auth_reference_is_required(self):
        self.config['bearer_token_env_var'] = 'CONNECTOR_FIXTURE_MISSING_AUTH'
        with patch.dict(os.environ, {}, clear=True):
            row, _ = self.probe()
        self.assertFalse(row['qualified'])
        self.assertIn('reference unavailable', row['reason'])

    def test_no_secrets_in_output(self):
        target = self.home / 'receipt.json'
        sentinel = 'fixture-secret-material-12345'
        with patch.dict(os.environ, {'CONNECTOR_TEST_SECRET': sentinel}):
            with self.assertRaises(fabric.Refusal):
                fabric.emit({'accidental': sentinel}, target)
        self.assertFalse(target.exists())

    def test_endpoint_and_literal_header_boundaries(self):
        for config in [{'url': 'http://external.invalid/mcp'},
                       {'url': 'https://user:pass@external.invalid/mcp'},
                       {'url': 'https://external.invalid/mcp?token=value'},
                       {'url': 'https://external.invalid/mcp', 'http_headers': {'Authorization': 'literal'}}]:
            with self.assertRaises(fabric.Refusal):
                fabric.MCP(config)

    def test_canary_expiry_metadata_is_not_a_secret(self):
        with patch.dict(os.environ, {'TONY_AGENT_TOKEN_EXPIRES_AT': '2099-01-01T00:00:00Z',
                                     'GH_TOKEN': 'fixture-private-token-123456'}):
            self.assertFalse(fabric.secrets_present('2099-01-01T00:00:00Z'))
            self.assertTrue(fabric.secrets_present('fixture-private-token-123456'))
        with patch.dict(os.environ, {'TONY_AGENT_TOKEN_EXPIRES_AT': 'not-a-time-but-sensitive'}):
            self.assertTrue(fabric.secrets_present('not-a-time-but-sensitive'))

    def test_native_client_does_not_claim_desktop_or_cloud(self):
        for surface in ['codex-desktop', 'codex-cloud', 'codex-cli-to-cloud']:
            with self.assertRaises(fabric.Refusal), patch.object(native, 'CodexClient') as client:
                native.probe_clients(fabric.load_manifest(), surface, None)
            client.assert_not_called()

    def test_native_client_read_and_forbidden_call_are_distinct(self):
        class Client:
            identity = {'thread_id': 'fixture-native-thread', 'pid': 1}
            servers = {'fixture': {'runtimeStatus': 'connected', 'tools': {'read': {}}}}
            def call(self, server, tool, arguments):
                if tool == 'create_issue':
                    raise fabric.Refusal('Codex MCP operation rejected')
                return {'content': [{'type': 'text', 'text': 'bounded fixture read'}]}
        row = native.observe(Client(), self.connector, 'codex-cli')
        self.assertTrue(row['checks']['read_canary'])
        self.assertTrue(row['checks']['fail_closed'])
        self.assertFalse(row['checks']['restart'])
        self.assertFalse(row['qualified'])

    def test_native_client_rejects_provider_error(self):
        class Client:
            identity = {'thread_id': 'fixture-native-thread', 'pid': 1}
            servers = {'fixture': {'runtimeStatus': 'connected', 'tools': {'read': {}}}}
            def call(self, *args):
                return {'isError': True, 'content': [{'type': 'text', 'text': 'private-error'}]}
        row = native.observe(Client(), self.connector, 'codex-cli')
        self.assertFalse(row['checks']['read_canary'])
        self.assertNotIn('private-error', json.dumps(row))

    def test_complete_matrix_and_required_admission(self):
        m = fabric.load_manifest()
        rows = fabric.matrix(m, [])
        self.assertEqual(len(rows), len(m['connectors']) * len(fabric.SURFACES))
        self.assertFalse(fabric.admission(m, rows, 'ghostmesh-core', 'local-shell'))
        for row in rows:
            row['qualified'] = True
        self.assertFalse(fabric.admission(m, rows, 'ghostmesh-core', 'local-shell'))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(fabric.ROOT / 'lib/connector_fabric.py'), *args],
                              text=True, capture_output=True)

    def test_fresh_repository_only_gets_profile_and_admission_denies(self):
        repo = self.home / 'new-repo'
        repo.mkdir()
        run = self.cli('init-repository', '--repository', str(repo))
        self.assertEqual(run.returncode, 0, run.stderr)
        files = list(repo.iterdir())
        self.assertEqual([f.name for f in files], ['.mesh-profile.json'])
        binding = json.loads(files[0].read_text())
        self.assertEqual(set(binding), {'schema_version', 'profile', 'capability_contract', 'manifest_sha256'})
        result = self.cli('admit', '--repository', str(repo), '--home', str(self.home))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['admitted'])
        binding['manifest_sha256'] = 'stale'
        files[0].write_text(json.dumps(binding))
        self.assertEqual(self.cli('admit', '--repository', str(repo)).returncode, 64)

    def test_render_preserves_unrelated_settings_and_is_idempotent(self):
        source = self.home / 'config.toml'
        source.write_text('[plugins.example]\nenabled = true\n')
        args = ['render', '--source', str(source), '--output', str(source)]
        run = self.cli(*args)
        self.assertEqual(run.returncode, 0, run.stderr)
        first = source.read_text()
        self.assertIn('[plugins.example]', first)
        self.assertIn('mcp/x/all/readonly', first)
        self.assertEqual(self.cli(*args).returncode, 0)
        self.assertEqual(source.read_text(), first)

    def test_inventory_records_disabled_and_cached_entries(self):
        p = self.home / '.codex/config.toml'
        p.parent.mkdir()
        p.write_text('[mcp_servers.example]\nenabled = false\nurl = "https://example.invalid/mcp"\n')
        result = fabric.inventory(self.home)
        self.assertFalse(result['servers'][0]['enabled'])
        self.assertEqual(result['servers'][0]['endpoint_host'], 'example.invalid')

    def test_governed_canary_refuses_default_branch_before_network(self):
        with self.assertRaises(fabric.Refusal), patch.object(subprocess, 'run') as call:
            fabric.github_canary({'repository': 'example/repo', 'branch': 'main',
                                  'authority': 'https://github.com/example/repo/issues/18',
                                  'environment': 'development'})
        call.assert_not_called()

    def test_governed_canary_scope_readback_and_cleanup(self):
        contract = {'repository': 'example/repo', 'branch': 'codex/issue-18-canary-fixture',
                    'authority': 'https://github.com/example/repo/issues/18', 'environment': 'development'}
        calls = []

        def gh(command, **kwargs):
            path = command[2]
            calls.append((command, kwargs.get('input')))
            if path == '/installation/repositories':
                value = {'total_count': 1, 'repositories': [{'full_name': 'example/repo'}]}
            elif path == '/repos/example/repo':
                value = {'default_branch': 'main'}
            elif path.endswith('/git/ref/heads/main'):
                value = {'object': {'sha': 'base-sha'}}
            elif '/contents/' in path and command[4] == 'PUT':
                value = {'content': {'sha': 'blob-sha'}}
            elif '/contents/' in path:
                value = {'sha': 'blob-sha', 'content': fabric.base64.b64encode(
                    b'Connector fabric development canary; no credentials.\n').decode()}
            elif '/git/matching-refs/' in path:
                value = []
            else:
                value = {}
            return subprocess.CompletedProcess(command, 0, json.dumps(value), '')

        with patch.dict(os.environ, {'TONY_AGENT_REPOSITORY': 'example/repo',
                                     'TONY_AGENT_TOKEN_EXPIRES_AT': '2099-01-01T00:00:00Z'}), \
                patch.object(subprocess, 'run', side_effect=gh):
            result = fabric.github_canary(contract)
        self.assertTrue(result['cleanup'])
        self.assertTrue(result['write_canary'])
        self.assertEqual(calls[-2][0][4], 'DELETE')
        self.assertEqual(calls[-1][0][4], 'GET')
        self.assertTrue(result['cleanup_readback'])
        self.assertTrue(calls[-1][0][2].endswith(contract['branch']))
        payload = json.loads(next(body for cmd, body in calls if cmd[4] == 'PUT'))
        self.assertEqual(payload['branch'], contract['branch'])

    def test_governed_canary_wide_token_stops_before_mutation(self):
        contract = {'repository': 'example/repo', 'branch': 'codex/issue-18-canary-fixture',
                    'authority': 'https://github.com/example/repo/issues/18', 'environment': 'development'}
        wide = subprocess.CompletedProcess([], 0, json.dumps({'total_count': 2, 'repositories': []}), '')
        with patch.dict(os.environ, {'TONY_AGENT_REPOSITORY': 'example/repo',
                                     'TONY_AGENT_TOKEN_EXPIRES_AT': '2099-01-01T00:00:00Z'}), \
                patch.object(subprocess, 'run', return_value=wide) as call:
            with self.assertRaises(fabric.Refusal):
                fabric.github_canary(contract)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[0][4], 'GET')


if __name__ == '__main__':
    unittest.main()
