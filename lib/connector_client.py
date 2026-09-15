"""Bounded native Codex MCP adapter; credentials stay in the installed client.

No model turn, credential export, auth enrollment, or provider write is requested.
Two independent client processes establish read persistence, never GUI restart.
"""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

from connector_fabric import CHECKS, MCP, Refusal, RPCRefusal, now, secrets_present

APP_PREFIX = {'supabase': 'supabase', 'google-drive': 'google_drive',
              'gmail': 'gmail', 'google-contacts': 'google_contacts',
              'higgsfield': 'higgsfield', 'figma': 'figma', 'canva': 'canva',
              'github-app': 'github', 'dropbox': 'dropbox'}


class CodexClient:
    def __init__(self, cwd):
        executable = shutil.which('codex')
        if not executable:
            raise Refusal('installed Codex client unavailable')
        self.process = subprocess.Popen([executable, 'app-server', '--stdio'],
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
                raise RPCRefusal(message['error'].get('code'))
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
        checks['write_capability'] = not writes or set(writes).issubset(names)
        checks['write_canary'] = not writes
        forbidden = connector.get('forbidden_tools', [])
        if forbidden and not set(forbidden).intersection(names):
            checks['fail_closed'] = reader.rejects_unconfigured_write(forbidden[0])
        checks['secret_exclusion'] = not secrets_present(json.dumps(row))
        row['reason'] = 'read observed; waiting for independent process restart and remaining checks'
    except (Refusal, OSError, ValueError, KeyError) as exc:
        row['reason'] = str(exc) if isinstance(exc, Refusal) else type(exc).__name__
        row['health'] = 'DEGRADED'
    return row


def probe_clients(manifest, surface, repository):
    if surface not in ['local-shell', 'codex-cli', 'fresh-repository']:
        raise Refusal('native local client cannot assert Desktop or hosted execution')
    if surface == 'fresh-repository' and not repository:
        raise Refusal('fresh repository qualification requires its directory')
    cwd = Path(repository or Path.cwd()).resolve()
    runs, inventories = [], []
    for _ in range(2):
        client = CodexClient(cwd)
        try:
            runs.append([observe(client, c, surface) for c in manifest['connectors']])
            inventories.append({'execution': client.identity,
                'servers': [{'name': n, 'runtime_status': s.get('runtimeStatus'),
                             'auth_status': s.get('authStatus'),
                             'tool_names': sorted(s.get('tools', {}))}
                            for n, s in client.servers.items()]})
        finally:
            client.close()
    rows = runs[1]
    for before, after in zip(runs[0], rows):
        after['prior_execution'] = before['execution']
        after['checks']['restart'] = (
            before['checks']['read_canary'] and after['checks']['read_canary']
            and before.get('authentication_identity') == after.get('authentication_identity')
            and before.get('server_identity') == after.get('server_identity')
            and before.get('tool_names') == after.get('tool_names')
            and before['execution']['thread_id'] != after['execution']['thread_id'])
        after['qualified'] = all(after['checks'].values())
        if after['qualified']:
            after['health'] = 'RESTART_PERSISTENT'
            after['reason'] = 'independent native client processes passed all checks'
        elif after['checks']['read_canary']:
            after['reason'] = 'missing checks: ' + ', '.join(k for k,v in after['checks'].items() if not v)
    return rows, inventories
