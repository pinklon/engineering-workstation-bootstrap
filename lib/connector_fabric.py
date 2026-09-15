"""Secret-free connector inventory and fail-closed MCP conformance.

This is part of the existing bootstrap, not an authentication store. OAuth
custody stays with the client. Never read its credential database or log RPC
payloads. Session observations cannot be promoted to surface qualification.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifests/connector-capabilities.json'
SURFACES = ['local-shell', 'codex-cli', 'codex-desktop', 'codex-cloud',
            'codex-cli-to-cloud', 'fresh-repository']
CHECKS = ['configured', 'handshake', 'authentication', 'tool_inventory',
          'read_canary', 'write_capability', 'write_canary', 'fail_closed',
          'restart', 'secret_exclusion']
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}'
                    r'|sk-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)')


class Refusal(Exception):
    pass


class RPCRefusal(Refusal):
    def __init__(self, code, message=''):
        super().__init__('MCP operation rejected')
        self.code = code
        match = re.fullmatch(r'unknown tool "([A-Za-z0-9_.-]+)"', message)
        self.unknown_tool = match.group(1) if match else None


def digest(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def check_applicability(connector):
    """Tier is admission policy; write checks depend on declared capabilities."""
    applies = dict.fromkeys(CHECKS, True)
    if not connector['governed_write_capabilities']:
        applies['write_capability'] = False
        applies['write_canary'] = False
        # A read-only security boundary may still require inventory exclusion.
        applies['fail_closed'] = bool(connector.get('forbidden_tools'))
    return applies


def required_checks_pass(connector, checks):
    return all(checks.get(k) is True for k, applies in check_applicability(connector).items() if applies)


def source_identity():
    result = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, timeout=10)
    head = result.stdout.strip() if result.returncode == 0 else None
    return {'root': str(ROOT), 'head': head,
            'implementation_sha256': digest(Path(__file__).read_bytes()),
            'client_adapter_sha256': digest((ROOT / 'lib/connector_client.py').read_bytes())}


def secrets_present(data):
    text = data.decode('utf-8', errors='replace') if isinstance(data, bytes) else data
    if SECRET.search(text):
        return True
    # Match actual inherited secret values, not only familiar token prefixes.
    return any(len(v) >= 8 and v in text for k, v in os.environ.items()
               if re.search(r'(TOKEN|SECRET|PASSWORD|API_KEY)', k)
               and not (k == 'TONY_AGENT_TOKEN_EXPIRES_AT'
                        and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', v)))


def emit(data, output):
    payload = json.dumps(data, indent=2, sort_keys=True) + '\n'
    if secrets_present(payload):
        raise Refusal('secret-exclusion: output suppressed')
    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        # No partially written receipts and no following destination symlinks.
        tmp = p.with_name(p.name + '.' + uuid.uuid4().hex)
        try:
            with tmp.open('x') as f:
                os.chmod(tmp, 0o600)
                f.write(payload)
            os.replace(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        print(payload, end='')


def load_manifest():
    m = json.loads(MANIFEST.read_text())
    ids = [c['id'] for c in m['connectors']]
    if m['schema_version'] != 1 or len(ids) != len(set(ids)):
        raise Refusal('invalid capability manifest')
    for c in m['connectors']:
        if set(c['surfaces']) != set(SURFACES):
            raise Refusal('incomplete surface declaration')
        if c['tier'] not in ['REQUIRED', 'OPTIONAL', 'DEPRECATED']:
            raise Refusal('invalid tier')
    for p in m['profiles'].values():
        if not set(p['required']).issubset(ids):
            raise Refusal('unknown profile capability')
    return m


def server_metadata(name, value, origin):
    url = urllib.parse.urlsplit(value.get('url', ''))
    return {'id': name, 'origin': origin, 'enabled': value.get('enabled', True),
            'transport': 'http' if url.hostname else 'stdio',
            'endpoint_host': url.hostname, 'command_present': bool(value.get('command')),
            'auth_reference': value.get('bearer_token_env_var'),
            'environment_names': sorted(value.get('env', {})),
            'literal_headers_present': bool(value.get('http_headers'))}


def inventory(home, session_tools=None):
    h = Path(home)
    config = h / '.codex/config.toml'
    c = tomllib.loads(config.read_text()) if config.exists() else {}
    result = {'schema_version': 1, 'generated_at': now(), 'secret_values': False,
              'config_identity': str(config.resolve()), 'servers': [], 'plugins': [],
              'apps': sorted(c.get('apps', {})), 'session_tools': session_tools or {},
              'uninspected_surfaces': ['codex-cloud', 'codex-cli-to-cloud'],
              'coverage': 'user config, cached plugin metadata, supplied session tool catalog'}
    for name, value in c.get('mcp_servers', {}).items():
        result['servers'].append(server_metadata(name, value, 'user-config'))
    for p in sorted((h / '.codex/plugins/cache').rglob('.codex-plugin/plugin.json')):
        v = json.loads(p.read_text())
        plugin = p.parent.parent
        result['plugins'].append({'id': v['name'], 'version': v.get('version'),
                                  'display_name': v.get('interface', {}).get('displayName'),
                                  'path': str(plugin),
                                  'configured': any(k.startswith(v['name'] + '@')
                                                    for k in c.get('plugins', {})),
                                  'sha256': digest(p.read_bytes())})
        for filename, kind in [('.mcp.json', 'mcp'), ('.app.json', 'app')]:
            f = plugin / filename
            if not f.exists():
                continue
            data = json.loads(f.read_text())
            if kind == 'mcp':
                for name, value in data.get('mcpServers', {}).items():
                    result['servers'].append(server_metadata(name, value, str(f)))
            else:
                result['apps'].extend(v['id'] for v in data.get('apps', {}).values())
    result['apps'] = sorted(set(result['apps']))
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Refusal('redirect refused')


class MCP:
    """Bounded streamable HTTP JSON-RPC client; no persistent auth storage."""
    def __init__(self, config):
        self.url = config['url']
        url = urllib.parse.urlsplit(self.url)
        if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ['127.0.0.1', 'localhost']):
            raise Refusal('insecure MCP endpoint')
        if url.username or url.password or url.query or url.fragment:
            raise Refusal('credential-bearing or parameterized endpoint refused')
        if config.get('http_headers'):
            raise Refusal('literal headers require an auth-reference realization')
        self.headers = {'Content-Type': 'application/json',
                        'Accept': 'application/json, text/event-stream'}
        ref = config.get('bearer_token_env_var')
        if ref:
            if not os.environ.get(ref):
                raise Refusal('authentication reference unavailable')
            self.headers['Authorization'] = 'Bearer ' + os.environ[ref]
        for name, ref in config.get('env_http_headers', {}).items():
            if not os.environ.get(ref):
                raise Refusal('authentication reference unavailable')
            self.headers[name] = os.environ[ref]
        self.opener = urllib.request.build_opener(NoRedirect)
        self.seq = 0
        self.read_identity = {}

    def rpc(self, method, params=None, notification=False):
        self.seq += 1
        body = {'jsonrpc': '2.0', 'method': method, 'params': params or {}}
        if not notification:
            body['id'] = self.seq
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers=self.headers, method='POST')
        with self.opener.open(req, timeout=15) as response:
            session = response.headers.get('Mcp-Session-Id')
            if session:
                self.headers['Mcp-Session-Id'] = session
            if notification:
                return {}
            if response.headers.get_content_type() == 'text/event-stream':
                total, lines, data = 0, [], {}
                while total <= 2_000_000:
                    line = response.readline(2_000_001 - total)
                    total += len(line)
                    if not line:
                        break
                    if line.strip() == b'':
                        if lines:
                            candidate = json.loads(b'\n'.join(lines))
                            if candidate.get('id') == self.seq:
                                data = candidate
                                break
                        lines = []
                    elif line.startswith(b'data:'):
                        lines.append(line[5:].strip())
                if total > 2_000_000:
                    raise Refusal('MCP response exceeds bound')
            else:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise Refusal('MCP response exceeds bound')
                data = json.loads(raw)
            if data.get('id') != self.seq or data.get('jsonrpc') != '2.0':
                raise Refusal('MCP response identity mismatch')
            if 'error' in data:
                raise RPCRefusal(data['error'].get('code'), data['error'].get('message', ''))
            return data['result']

    def start(self):
        result = self.rpc('initialize', {'protocolVersion': '2025-03-26',
                         'capabilities': {}, 'clientInfo': {'name': 'connector-doctor', 'version': '1'}})
        if not result.get('serverInfo') or 'tools' not in result.get('capabilities', {}):
            raise Refusal('MCP handshake lacks tool capability')
        self.headers['MCP-Protocol-Version'] = result['protocolVersion']
        self.rpc('notifications/initialized', notification=True)
        return result['serverInfo']

    def tool_names(self):
        names, cursor, seen = set(), None, set()
        for _ in range(100):
            page = self.rpc('tools/list', {'cursor': cursor} if cursor else {})
            names.update(t['name'] for t in page['tools'])
            cursor = page.get('nextCursor')
            if not cursor:
                return names
            if cursor in seen:
                raise Refusal('repeated tool inventory cursor')
            seen.add(cursor)
        raise Refusal('tool inventory pagination exceeds bound')

    def read(self, canary):
        result = self.rpc('tools/call', {'name': canary['tool'], 'arguments': canary['arguments']})
        if result.get('isError') or not (result.get('content') or result.get('structuredContent')):
            raise Refusal('read canary failed')
        if secrets_present(json.dumps(result)):
            raise Refusal('secret-exclusion: provider response suppressed')
        text = '\n'.join(c.get('text', '') for c in result.get('content', []) if c.get('type') == 'text')
        value = result.get('structuredContent')
        if value is None:
            try:
                value = json.loads(text)
            except ValueError:
                value = {}
        if isinstance(value, dict) and (value.get('error') or value.get('success') is False):
            raise Refusal('provider read returned an application error')
        if canary.get('json_keys') and (not isinstance(value, dict) or not set(canary['json_keys']).issubset(value)):
            raise Refusal('read canary identity/schema mismatch')
        if canary.get('contains') and canary['contains'] not in json.dumps(result):
            raise Refusal('read canary content mismatch')
        if canary.get('expected_values') and (not isinstance(value, dict) or
                any(value.get(k) != v for k, v in canary['expected_values'].items())):
            raise Refusal('read canary resource mismatch')
        self.read_identity = {k: value[k] for k in canary.get('identity_keys', []) if k in value}
        if len(self.read_identity) != len(canary.get('identity_keys', [])):
            raise Refusal('read canary authentication identity missing')
        return True

    def rejects_unconfigured_write(self, name):
        # Empty arguments designate no resource and cannot create an issue/file.
        # This is only used after proving the named mutation tool is absent.
        try:
            result = self.rpc('tools/call', {'name': name, 'arguments': {}})
            return result.get('isError') is True and result.get('error', {}).get('code') == -32601
        except RPCRefusal as exc:
            return exc.code == -32601 or (exc.code == -32602 and exc.unknown_tool == name)


def restart_read(connector_id, home, expected):
    # Re-open canonical config in a fresh login shell. Pass only paths/identity;
    # no tokens, serialized config, or credential files are copied to the child.
    run = subprocess.run(
        ['bash', '-lc', 'exec "$1" "$2" _restart --home "$3" --connector "$4"',
         'connector-restart', sys.executable, str(Path(__file__).resolve()), str(home), connector_id],
        capture_output=True, timeout=45)
    if run.returncode or secrets_present(run.stdout) or secrets_present(run.stderr):
        return False
    try:
        proof = json.loads(run.stdout)
        return proof == expected
    except ValueError:
        return False


def probe(connector, config, surface, home=None):
    checks = {k: False for k in CHECKS}
    row = {'connector': connector['id'], 'surface': surface, 'health': 'UNAVAILABLE',
           'checks': checks, 'check_applicability': check_applicability(connector),
           'qualified': False, 'observed_at': now(), 'reason': 'not configured'}
    if surface != 'local-shell':
        row['reason'] = 'requires independent execution on this surface'
        return row
    if not config or not config.get('enabled', True):
        return row
    checks['configured'] = True
    row['health'] = 'CONFIGURED'
    if not config.get('url') or not connector.get('read_canary'):
        row['reason'] = 'surface adapter not implemented; configuration is not proof'
        return row
    try:
        client = MCP(config)
        info = client.start()
        checks['handshake'] = True
        row['health'] = 'HANDSHAKE_PROVEN'
        row['server_identity'] = {k: info[k] for k in ['name', 'version'] if k in info}
        names = client.tool_names()
        checks['tool_inventory'] = set(connector['read_capabilities']).issubset(names)
        if not checks['tool_inventory']:
            raise Refusal('required read tools absent')
        client.read(connector['read_canary'])
        row['authentication_identity'] = client.read_identity
        # For public docs, authentication is explicitly not applicable.
        checks['authentication'] = True
        checks['read_canary'] = True
        row['health'] = 'READ_PROVEN'
        write = connector['governed_write_capabilities']
        checks['write_capability'] = bool(write) and set(write).issubset(names)
        forbidden = connector.get('forbidden_tools', [])
        checks['fail_closed'] = (bool(forbidden) and not set(forbidden).intersection(names)
                                 and all(client.rejects_unconfigured_write(name) for name in forbidden))
        # Transport reconnect and login shell are separate facts. Neither proves
        # a new CLI/Desktop or hosted session.
        restarted = MCP(config)
        restarted.start()
        row['new_transport_session_read'] = restarted.read(connector['read_canary'])
        expected = {'connector': connector['id'], 'read_canary': True,
                    'server_identity': row['server_identity'],
                    'authentication_identity': client.read_identity,
                    'config_sha256': digest(json.dumps(config, sort_keys=True).encode())}
        checks['restart'] = restart_read(connector['id'], home, expected) if home else False
        checks['secret_exclusion'] = not secrets_present(json.dumps(config))
        row['qualified'] = required_checks_pass(connector, checks)
        if row['qualified']:
            row['health'] = 'RESTART_PERSISTENT'
            row['reason'] = 'local shell conformance checks passed'
        else:
            row['reason'] = 'missing checks: ' + ', '.join(k for k, v in checks.items() if not v and row['check_applicability'][k])
    except (Refusal, OSError, ValueError, KeyError, StopIteration, subprocess.TimeoutExpired) as exc:
        row['health'] = 'DEGRADED'
        # Never return provider errors, command output, URLs, or credential data.
        row['reason'] = str(exc) if isinstance(exc, Refusal) else type(exc).__name__
        if isinstance(exc, urllib.error.HTTPError):
            row['http_status'] = exc.code
    return row


def matrix(m, rows):
    result = []
    for c in m['connectors']:
        for s in SURFACES:
            found = [r for r in rows if r['connector'] == c['id'] and r['surface'] == s]
            row = dict(found[-1]) if found else {
                'connector': c['id'], 'surface': s, 'health': 'UNAVAILABLE',
                'qualified': False, 'reason': 'no independent surface evidence'}
            row['tier'] = c['tier']
            row['check_applicability'] = check_applicability(c)
            result.append(row)
    return result


def admission(m, rows, profile, surface):
    required = set(m['profiles'][profile]['required'])
    found = {r['connector']: r for r in rows if r['surface'] == surface}
    # Caller-supplied qualified=true is insufficient. Evidence must come from a
    # live doctor run, and every applicable check is required, including restart.
    connectors = {c['id']: c for c in m['connectors']}
    return all(found.get(c, {}).get('qualified') is True and
               required_checks_pass(connectors[c], found[c].get('checks', {}))
               for c in required)


def github_canary(contract):
    """Called only within the existing repository-scoped App launcher."""
    repo = contract['repository']
    branch = contract['branch']
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
            or not re.fullmatch(r'codex/issue-18-canary-[a-z0-9-]+', branch)
            or contract.get('environment') != 'development'
            or contract.get('authority') != 'https://github.com/' + repo + '/issues/18'
            or os.environ.get('TONY_AGENT_REPOSITORY') != repo
            or not os.environ.get('TONY_AGENT_TOKEN_EXPIRES_AT')):
        raise Refusal('canary contract or App launch boundary mismatch')

    def api(path, method='GET', payload=None):
        command = ['gh', 'api', path, '--method', method]
        if payload is not None:
            command.extend(['--input', '-'])
        result = subprocess.run(command, input=json.dumps(payload) if payload else None,
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise Refusal('governed GitHub API request failed')
        if secrets_present(result.stdout):
            raise Refusal('secret-exclusion: GitHub response suppressed')
        return json.loads(result.stdout) if result.stdout.strip() else {}

    scope = api('/installation/repositories')
    if scope.get('total_count') != 1 or [r['full_name'] for r in scope['repositories']] != [repo]:
        raise Refusal('GitHub App token is not scoped to exactly the canary repository')
    info = api('/repos/' + repo)
    base = api('/repos/' + repo + '/git/ref/heads/' + info['default_branch'])['object']['sha']
    prefix = '/repos/' + repo
    created = False
    cleaned = False
    blob_sha = None
    try:
        api(prefix + '/git/refs', 'POST', {'ref': 'refs/heads/' + branch, 'sha': base})
        created = True
        content = b'Connector fabric development canary; no credentials.\n'
        written = api(prefix + '/contents/connector-fabric-canary.txt', 'PUT', {
            'message': 'test: bounded connector fabric canary', 'branch': branch,
            'content': base64.b64encode(content).decode()})
        blob_sha = written['content']['sha']
        verified = api(prefix + '/contents/connector-fabric-canary.txt?ref=' + branch)
        if base64.b64decode(verified['content']) != content or verified['sha'] != blob_sha:
            raise Refusal('governed write read-back mismatch')
    finally:
        if created:
            api(prefix + '/git/refs/heads/' + branch, 'DELETE')
            cleaned = True
    # A successful DELETE alone is not independent cleanup readback.
    remaining = api(prefix + '/git/matching-refs/heads/' + branch)
    if any(ref.get('ref') == 'refs/heads/' + branch for ref in remaining):
        raise Refusal('canary branch remains after cleanup')
    return {'repository': repo, 'branch': branch, 'blob_sha': blob_sha,
            'cleanup': cleaned, 'write_canary': bool(blob_sha),
            'cleanup_readback': True, 'observed_at': now(),
            'repository_scope_proven': True,
            'token_expires_at': os.environ['TONY_AGENT_TOKEN_EXPIRES_AT']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inventory', 'probe', 'client-probe', 'matrix', 'init-repository', 'admit', 'render', 'github-canary', '_github-canary', '_restart'])
    parser.add_argument('--home', default=str(Path.home()))
    parser.add_argument('--surface', choices=SURFACES, default='local-shell')
    parser.add_argument('--profile', default='ghostmesh-core')
    parser.add_argument('--output')
    parser.add_argument('--session-tools')
    parser.add_argument('--repository')
    parser.add_argument('--source')
    parser.add_argument('--connector')
    parser.add_argument('--write-contract')
    args = parser.parse_args()
    m = load_manifest()
    if args.command in ['github-canary', '_github-canary']:
        if not args.write_contract:
            raise Refusal('an explicit development write-canary contract is required')
        contract = json.loads(Path(args.write_contract).read_text())
        if args.command == '_github-canary':
            emit(github_canary(contract), None)
            return 0
        launcher = shutil.which('agent-codex')
        if not launcher:
            raise Refusal('existing governed GitHub transport unavailable')
        result = subprocess.run([launcher, contract['repository'], sys.executable,
                                 str(Path(__file__).resolve()), '_github-canary',
                                 '--write-contract', str(Path(args.write_contract).resolve())],
                                capture_output=True, timeout=180)
        if result.returncode:
            if args.output:
                emit({'schema_version': 1, 'health': 'DEGRADED', 'write_canary': False,
                      'repository': contract['repository'], 'branch': contract['branch'],
                      'transport': 'existing-agent-codex', 'exit_code': result.returncode,
                      'reason': 'governed transport failed; no fallback credential used',
                      'secret_values': False}, args.output)
            raise Refusal('existing governed GitHub transport failed; no fallback credential used')
        data = json.loads(result.stdout)
        emit(data, args.output)
        return 0
    if args.command == '_restart':
        c = next((c for c in m['connectors'] if c['id'] == args.connector), None)
        if not c or not c['read_canary']:
            raise Refusal('no restart canary')
        config = tomllib.loads((Path(args.home) / '.codex/config.toml').read_text())['mcp_servers'][c['id']]
        client = MCP(config)
        info = client.start()
        if not set(c['read_capabilities']).issubset(client.tool_names()):
            raise Refusal('restart tool inventory mismatch')
        client.read(c['read_canary'])
        emit({'connector': c['id'], 'read_canary': True,
              'server_identity': {k: info[k] for k in ['name', 'version'] if k in info},
              'authentication_identity': client.read_identity,
              'config_sha256': digest(json.dumps(config, sort_keys=True).encode())}, None)
        return 0
    if args.profile not in m['profiles']:
        raise Refusal('unknown connector profile')
    if args.command == 'render':
        if not args.output:
            raise Refusal('render requires output')
        source = Path(args.source).read_text() if args.source else ''
        if secrets_present(source):
            raise Refusal('source contains credential material')
        existing = tomllib.loads(source).get('mcp_servers', {})
        additions = []
        for c in m['connectors']:
            endpoint = c.get('endpoint')
            if not endpoint or c['id'] not in m['profiles'][args.profile]['required']:
                continue
            name = c['id']
            if name in existing:
                if existing[name].get('url') != endpoint:
                    raise Refusal('existing endpoint contradicts canonical identity')
                if not existing[name].get('enabled', True):
                    raise Refusal('required connector is disabled in existing configuration')
                expected_auth = c.get('bearer_token_env_var')
                if expected_auth and existing[name].get('bearer_token_env_var') != expected_auth:
                    raise Refusal('required connector authentication reference mismatch')
                if existing[name].get('http_headers'):
                    raise Refusal('required connector literal headers refused')
                continue
            additions.extend(['', '[mcp_servers.' + json.dumps(name) + ']',
                              'url = ' + json.dumps(endpoint), 'enabled = true'])
            if c.get('bearer_token_env_var'):
                additions.append('bearer_token_env_var = ' + json.dumps(c['bearer_token_env_var']))
        output = (source.rstrip() + '\n' + '\n'.join(additions)).rstrip() + '\n'
        tomllib.loads(output)
        dest = Path(args.output)
        if dest.is_symlink():
            raise Refusal('render target must not be a live symlink')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(output)
        return 0
    if args.command == 'inventory':
        session = json.loads(Path(args.session_tools).read_text()) if args.session_tools else None
        emit(inventory(args.home, session), args.output)
        return 0
    if args.command == 'init-repository':
        if not args.repository:
            raise Refusal('repository directory required')
        dest = Path(args.repository) / '.mesh-profile.json'
        if dest.exists():
            raise Refusal('repository profile already exists')
        emit({'schema_version': 1, 'profile': args.profile,
              'capability_contract': m['contract'], 'manifest_sha256': digest(MANIFEST.read_bytes())}, str(dest))
        return 0
    config_path = Path(args.home) / '.codex/config.toml'
    if args.repository:
        binding = json.loads((Path(args.repository) / '.mesh-profile.json').read_text())
        if set(binding) != {'schema_version', 'profile', 'capability_contract', 'manifest_sha256'}:
            raise Refusal('repository may declare only a profile and contract identity')
        if binding['capability_contract'] != m['contract'] or binding['manifest_sha256'] != digest(MANIFEST.read_bytes()):
            raise Refusal('repository capability contract drift')
        args.profile = binding['profile']
        if args.profile not in m['profiles']:
            raise Refusal('unknown repository capability profile')
    config = tomllib.loads(config_path.read_text()).get('mcp_servers', {}) if config_path.exists() else {}
    rows = []
    client_inventories = []
    if args.command == 'client-probe':
        from connector_client import probe_clients
        rows, client_inventories = probe_clients(m, args.surface, args.repository, args.connector)
    if args.command in ['probe', 'admit']:
        for c in m['connectors']:
            rows.append(probe(c, config.get(c.get('mcp_server', c['id'])), args.surface, args.home))
    rows = matrix(m, rows)
    admitted = admission(m, rows, args.profile, args.surface)
    emit({'schema_version': 1, 'contract': m['contract'], 'generated_at': now(),
          'bootstrap_source': source_identity(),
          'manifest_sha256': digest(MANIFEST.read_bytes()), 'profile': args.profile,
          'surface': args.surface, 'admitted': admitted, 'target_active': False,
          'secret_values': False, 'client_inventories': client_inventories,
          'matrix': rows}, args.output)
    return 0 if args.command == 'matrix' or admitted else 1


if __name__ == '__main__':
    sys.modules.setdefault('connector_fabric', sys.modules[__name__])
    try:
        sys.exit(main())
    except (Refusal, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print('REFUSE: ' + (str(error) if isinstance(error, Refusal) else type(error).__name__), file=sys.stderr)
        sys.exit(64)
