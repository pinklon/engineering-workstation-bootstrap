"""Bounded native Codex MCP adapter; credentials stay in the installed client.

No model turn, credential export, auth enrollment, or provider write is requested.
Two independent client processes establish read persistence, never GUI restart.
"""
import json
import datetime as dt
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

from connector_fabric import (CHECKS, MCP, Refusal, RPCRefusal, now, secrets_present,
                              check_applicability, required_checks_pass)

APP_PREFIX = {'supabase': 'supabase', 'google-drive': 'google_drive',
              'gmail': 'gmail', 'google-contacts': 'google_contacts',
              'higgsfield': 'higgsfield', 'figma': 'figma', 'canva': 'canva',
              'github-app': 'github', 'dropbox': 'dropbox'}


class CodexClient:
    def __init__(self, cwd, overrides=None):
        executable = shutil.which('codex')
        if not executable:
            raise Refusal('installed Codex client unavailable')
        command = [executable]
        for override in overrides or []:
            command.extend(['-c', override])
        self.process = subprocess.Popen(command + ['app-server', '--stdio'],
                                        cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b''
        self.seq = 0
        try:
            result = self.rpc('initialize', {
                'clientInfo': {'name': 'connector-doctor', 'version': '1'},
                'capabilities': {'experimentalApi': True}})
            self.identity = {'executable': str(Path(executable).resolve()),
                             'user_agent': result.get('userAgent'),
                             'pid': self.process.pid}
            self.send({'method': 'initialized'})
            thread = self.rpc('thread/start', {'cwd': str(cwd), 'ephemeral': True})
            self.thread_id = thread['thread']['id']
            self.identity['thread_id'] = self.thread_id
            self.servers = {}
            cursor, seen = None, set()
            for _ in range(100):
                page = self.rpc('mcpServerStatus/list', {
                    'threadId': self.thread_id, 'cursor': cursor, 'limit': 100})
                self.servers.update((s['name'], s) for s in page['data'])
                cursor = page.get('nextCursor')
                if not cursor:
                    break
                if cursor in seen:
                    raise Refusal('repeated client inventory cursor')
                seen.add(cursor)
            else:
                raise Refusal('client inventory exceeds bound')
        except BaseException:
            self.close()
            raise

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + '\n').encode())
        self.process.stdin.flush()

    def rpc(self, method, params):
        self.seq += 1
        request_id = self.seq
        self.send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if b'\n' not in self.buffer:
                if not self.selector.select(min(1, max(0, deadline - time.monotonic()))):
                    continue
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise Refusal('Codex client exited before response')
                self.buffer += chunk
                if len(self.buffer) > 10_000_000:
                    raise Refusal('Codex client response exceeds bound')
                continue
            line, self.buffer = self.buffer.split(b'\n', 1)
            message = json.loads(line)
            if 'method' in message and 'id' in message:
                # Never approve auth, mutations, shell commands, or elicitation.
                self.send({'id': message['id'], 'error': {
                    'code': -32601, 'message': 'qualification adapter denies server requests'}})
                continue
            if message.get('id') != request_id:
                continue
            if 'error' in message:
                raise RPCRefusal(message['error'].get('code'), message['error'].get('message', ''))
            return message['result']
        raise Refusal('Codex client response timeout')

    def call(self, server, tool, arguments):
        return self.rpc('mcpServer/tool/call', {'threadId': self.thread_id,
                        'server': server, 'tool': tool, 'arguments': arguments})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.selector.close()
        self.process.stdin.close()
        self.process.stdout.close()


class ClientRead(MCP):
    """Reuse canonical response validation without accessing client credentials."""
    def __init__(self, client, server, prefix):
        self.client, self.server, self.prefix = client, server, prefix
        self.read_identity = {}

    def rpc(self, method, params=None, notification=False):
        if method != 'tools/call':
            raise Refusal('client adapter permits only canonical canaries')
        return self.client.call(self.server, self.prefix + params['name'], params['arguments'])


def observe(client, connector, surface):
    checks = dict.fromkeys(CHECKS, False)
    row = {'connector': connector['id'], 'surface': surface, 'checks': checks,
           'check_applicability': check_applicability(connector),
           'observed_at': now(), 'health': 'UNAVAILABLE', 'qualified': False,
           'execution': client.identity, 'reason': 'connector not exposed by this client'}
    name = connector.get('mcp_server', connector['id'])
    prefix = ''
    if name not in client.servers and connector['id'] in APP_PREFIX:
        name, prefix = 'codex_apps', APP_PREFIX[connector['id']] + '.'
    server = client.servers.get(name, {})
    names = {n[len(prefix):] for n in server.get('tools', {}) if n.startswith(prefix)}
    if not names:
        return row
    checks['configured'] = True
    checks['handshake'] = server.get('runtimeStatus') == 'connected'
    row['health'] = 'HANDSHAKE_PROVEN' if checks['handshake'] else 'CONFIGURED'
    row['server_identity'] = server.get('serverInfo')
    row['tool_names'] = sorted(names)
    canary = connector.get('read_canary')
    if not canary:
        row['reason'] = 'canonical read canary missing'
        return row
    canary = dict(canary)
    if connector['id'] in ['google-drive', 'gmail', 'google-contacts']:
        canary['json_keys'] = ['id', 'email']
        canary['identity_keys'] = ['id', 'email']
    elif connector['id'] == 'supabase':
        canary['json_keys'] = ['organizations']
    elif connector['id'] == 'higgsfield':
        canary['json_keys'] = ['credits', 'subscription_plan_type']
    try:
        checks['tool_inventory'] = set(connector['read_capabilities']).issubset(names)
        if not checks['handshake'] or not checks['tool_inventory']:
            raise Refusal('client handshake or required tool inventory missing')
        reader = ClientRead(client, name, prefix)
        reader.read(canary)
        checks['authentication'] = True
        checks['read_canary'] = True
        row['health'] = 'READ_PROVEN'
        row['authentication_identity'] = reader.read_identity
        writes = connector['governed_write_capabilities']
        checks['write_capability'] = bool(writes) and set(writes).issubset(names)
        forbidden = connector.get('forbidden_tools', [])
        if forbidden and not set(forbidden).intersection(names):
            checks['fail_closed'] = all(reader.rejects_unconfigured_write(name) for name in forbidden)
        checks['secret_exclusion'] = not secrets_present(json.dumps(row))
        row['reason'] = 'read observed; waiting for independent process restart and remaining checks'
    except (Refusal, OSError, ValueError, KeyError) as exc:
        row['reason'] = str(exc) if isinstance(exc, Refusal) else type(exc).__name__
        row['health'] = 'DEGRADED'
    return row


def github_app_overrides(connector):
    """Use the existing launcher only; never inherit an unrelated GH credential."""
    repo = connector['read_canary']['arguments']['owner'] + '/' + connector['read_canary']['arguments']['repo']
    if os.environ.get('TONY_AGENT_REPOSITORY') != repo or not os.environ.get('GH_TOKEN'):
        raise Refusal('GitHub read-only requires the existing repository-scoped App launcher')
    try:
        expiry = dt.datetime.fromisoformat(os.environ['TONY_AGENT_TOKEN_EXPIRES_AT'].replace('Z', '+00:00'))
        remaining = (expiry - dt.datetime.now(dt.timezone.utc)).total_seconds()
    except (KeyError, ValueError, TypeError):
        raise Refusal('GitHub App expiry unavailable') from None
    if not 0 < remaining <= 3700:
        raise Refusal('GitHub App expiry outside short-lived boundary')
    result = subprocess.run(['gh', 'api', '/installation/repositories'], capture_output=True, text=True, timeout=30)
    if result.returncode or secrets_present(result.stdout):
        raise Refusal('GitHub App repository scope could not be verified')
    scope = json.loads(result.stdout)
    if scope.get('total_count') != 1 or [r['full_name'] for r in scope['repositories']] != [repo]:
        raise Refusal('GitHub App token is not scoped to exactly the canary repository')
    # Command-line config contains only canonical endpoint and auth reference.
    return ['mcp_servers.github-readonly.url=' + json.dumps(connector['endpoint']),
            'mcp_servers.github-readonly.bearer_token_env_var="GH_TOKEN"',
            'mcp_servers.github-readonly.enabled=true']


def probe_clients(manifest, surface, repository, connector_id=None):
    if surface not in ['local-shell', 'codex-cli', 'fresh-repository']:
        raise Refusal('native local client cannot assert Desktop or hosted execution')
    if surface == 'fresh-repository' and not repository:
        raise Refusal('fresh repository qualification requires its directory')
    cwd = Path(repository or Path.cwd()).resolve()
    connectors = [c for c in manifest['connectors'] if not connector_id or c['id'] == connector_id]
    if not connectors:
        raise Refusal('unknown connector')
    overrides = github_app_overrides(connectors[0]) if connector_id == 'github-readonly' else []
    runs, inventories = [], []
    for _ in range(2):
        client = CodexClient(cwd, overrides=overrides)
        try:
            runs.append([observe(client, c, surface) for c in connectors])
            inventories.append({'execution': client.identity,
                'servers': [{'name': n, 'runtime_status': s.get('runtimeStatus'),
                             'auth_status': s.get('authStatus'),
                             'tool_names': sorted(s.get('tools', {}))}
                            for n, s in client.servers.items()]})
        finally:
            client.close()
    rows = runs[1]
    for connector, before, after in zip(connectors, runs[0], rows):
        after['prior_execution'] = before['execution']
        after['checks']['restart'] = (
            before['checks']['read_canary'] and after['checks']['read_canary']
            and before.get('authentication_identity') == after.get('authentication_identity')
            and before.get('server_identity') == after.get('server_identity')
            and before.get('tool_names') == after.get('tool_names')
            and before['execution']['thread_id'] != after['execution']['thread_id'])
        after['qualified'] = required_checks_pass(connector, after['checks'])
        if after['qualified']:
            after['health'] = 'RESTART_PERSISTENT'
            after['reason'] = 'independent native client processes passed all checks'
        elif after['checks']['read_canary']:
            after['reason'] = 'missing checks: ' + ', '.join(k for k,v in after['checks'].items() if not v and after['check_applicability'][k])
    return rows, inventories
