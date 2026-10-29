"""Bounded, nonmutating GitHub observations; never forward command output."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import time

MAX_OUTPUT = 65536
LOGIN = r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?'
SECRET_PREFIXES = ('ghp_', 'gho_', 'ghu_', 'ghs_', 'ghr_', 'github_pat_')


def public_name(value, pattern):
    return (isinstance(value, str) and not value.startswith(SECRET_PREFIXES)
            and re.fullmatch(pattern, value) is not None)


def probe(command, timeout):
    """Keep output in bounded memory; kill our process group on timeout/overflow."""
    def failed(reason):
        return {'reason': reason, 'code': None, 'out': '', 'err': ''}
    if shutil.which(command[0]) is None:
        return failed('missing-tool')
    if os.name != 'posix':
        return failed('unsupported-platform')
    env = dict(os.environ)
    env.update(GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1',
               GH_NO_EXTENSION_UPDATE_NOTIFIER='1', GH_PAGER='cat',
               GIT_TERMINAL_PROMPT='0', SSH_ASKPASS_REQUIRE='never')
    env.pop('GH_DEBUG', None)
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env=env, start_new_session=True)
    except OSError:
        return failed('launch-failed')
    buffers = {'out': bytearray(), 'err': bytearray()}
    reason = 'completed'
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ, 'out')
            selector.register(child.stderr, selectors.EVENT_READ, 'err')
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    reason = 'timeout'
                    break
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffers[key.data].extend(chunk)
                    if sum(map(len, buffers.values())) > MAX_OUTPUT:
                        reason = 'output-limit'
                        break
                if reason != 'completed':
                    break
            if reason == 'completed':
                try:
                    child.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    reason = 'timeout'
    finally:
        if reason != 'completed' or child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        child.wait()
        child.stdout.close()
        child.stderr.close()
    if reason != 'completed':
        return failed(reason)
    return {'reason': reason, 'code': child.returncode,
            **{name: data.decode('utf-8', errors='replace') for name, data in buffers.items()}}


def failure_state(result):
    if result['reason'] == 'missing-tool':
        return 'missing-tool'
    if result['reason'] != 'completed':
        return 'unknown'
    if result['code'] == 4 or re.search(r'\(HTTP 401\)', result['err']):
        return 'unauthenticated'
    # A 403 may be rate limiting/SSO; a 404 can hide a private repository.
    return 'unknown'


def json_body(result):
    if result['reason'] != 'completed' or result['code'] != 0:
        return None
    try:
        return json.loads(result['out'])
    except (ValueError, RecursionError):
        return None


def evaluate(args):
    rows, version, identity = [], None, None
    token_vars = ('GH_TOKEN', 'GITHUB_TOKEN') if args.hostname == 'github.com' else (
        'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN')
    custody = 'environment' if any(os.environ.get(key) for key in token_vars) else 'unknown'
    skipped = {'reason': 'not-run', 'code': None, 'out': '', 'err': ''}

    def row(capability, state, command, remediation, *, requested=True, evidence=None):
        rows.append({'provider': 'github', 'capability': capability, 'tool': 'gh',
                     'version': version, 'identity': identity, 'custodyLocationType': custody,
                     'state': state, 'requested': requested,
                     'evidenceCommand': command, 'evidence': evidence,
                     'remediation': remediation if state != 'ready' and requested else None,
                     'humanInteractionRequired': None if state == 'unknown' else state in
                     ('unauthenticated', 'insufficient-permission'),
                     'blocks': ['selected-github-checks'] if requested and state != 'ready' else []})

    result = probe(['gh', '--version'], args.timeout)
    match = re.match(r'gh version ([0-9]+\.[0-9]+\.[0-9]+)(?:[\s+-]|$)', result['out'])
    if result['code'] == 0 and match:
        version = match.group(1)
    row('cli', 'ready' if version else failure_state(result), 'gh --version',
        'Install or repair the declared GitHub CLI; no package is downloaded by this doctor.')

    command = ['gh', 'api', '--hostname', args.hostname, '--method', 'GET', 'user']
    result = probe(command, args.timeout) if version else skipped
    body = json_body(result)
    if (isinstance(body, dict) and public_name(body.get('login'), LOGIN)
            and body.get('type') in ('User', 'Bot')):
        identity = {'login': body['login'], 'kind': body['type']}
    row('api-identity', 'ready' if identity else failure_state(result), ' '.join(command),
        'Check this host account with the owner. The doctor does not log in or refresh credentials.')

    transport = args.transport
    if transport == 'auto':
        command = ['gh', 'config', 'get', 'git_protocol', '--host', args.hostname]
        result = probe(command, args.timeout) if version else skipped
        transport = result['out'].strip() if result['code'] == 0 else 'unknown'
        if transport not in ('https', 'ssh'):
            transport = 'unknown'
        evidence_command = ' '.join(command)
    else:
        evidence_command = 'explicit --transport selection'
    row('transport-selection', 'ready' if transport in ('https', 'ssh') else 'unknown',
        evidence_command, 'Select --transport https or ssh, or verify the host Git protocol configuration.',
        evidence={'transport': transport})

    if transport == 'ssh':
        # Ignore user config: ProxyCommand/LocalCommand/ControlPath can have side
        # effects. Use existing known_hosts and agent/default keys only.
        command = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o',
                   'StrictHostKeyChecking=yes', '-o', 'UpdateHostKeys=no', '-o',
                   'ConnectionAttempts=1', '-o', 'ConnectTimeout=5', '-o',
                   'ControlMaster=no', '-o', 'ControlPath=none', '-T', 'git@' + args.hostname]
        result = probe(command, args.timeout)
        text = result['out'] + result['err']
        greeting = re.search(r"Hi (" + LOGIN + r")! You've successfully authenticated, but GitHub does not provide shell access\.", text)
        state = 'unknown'
        if result['reason'] == 'missing-tool':
            state = 'missing-tool'
        elif result['reason'] == 'completed' and result['code'] == 1 and greeting and identity:
            state = 'ready' if greeting.group(1) == identity['login'] else 'unknown'
        row('ssh-identity', state, ' '.join(command),
            'Verify existing host trust and matching identity separately; no trust is enrolled.',
            evidence={'identityMatchesApi': state == 'ready'})
        rows[-1]['tool'], rows[-1]['version'] = 'ssh', None

    if args.repository:
        command = ['gh', 'api', '--hostname', args.hostname, '--method', 'GET',
                   'repos/' + args.repository]
        result = probe(command, args.timeout) if identity else skipped
        body = json_body(result)
        permissions = body.get('permissions') if isinstance(body, dict) else None
        matched = (isinstance(body, dict) and isinstance(body.get('full_name'), str)
                   and body['full_name'].lower() == args.repository.lower())
        row('repository-read', 'ready' if matched else failure_state(result), ' '.join(command),
            'Verify repository identity and access; a hidden repository may also return 404.')
        admin = permissions.get('admin') if isinstance(permissions, dict) else None
        admin_state = ('ready' if admin is True else 'insufficient-permission'
                       if admin is False else 'unknown') if matched else 'unknown'
        row('repository-admin', admin_state, ' '.join(command),
            'Repository administration needs its separate existing grant; do not widen access automatically.',
            requested=args.require_admin)
        if args.check_webhooks:
            command = ['gh', 'api', '--hostname', args.hostname, '--method', 'GET',
                       'repos/' + args.repository + '/hooks?per_page=1']
            result = probe(command, args.timeout) if identity else skipped
            body = json_body(result)
            row('webhook-read', 'ready' if isinstance(body, list) else failure_state(result),
                ' '.join(command), 'Check existing webhook read access; this does not prove write authority.')

    return {'schemaVersion': 1, 'observedAt': datetime.now(timezone.utc).isoformat(),
            'host': args.hostname, 'profile': 'github-selected-checks', 'transport': transport,
            'ready': all(not item['blocks'] for item in rows), 'capabilities': rows,
            'unverified': ['https-git-transport', 'github-app-operator-authority',
                           'token-scope-summary', 'keyring-custody', 'provider-write-authority']}


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, 'Invalid GitHub doctor arguments; use --help.\n')


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument('--hostname', default='github.com')
    parser.add_argument('--transport', choices=('auto', 'https', 'ssh'), default='auto')
    parser.add_argument('--format', choices=('human', 'json'), default='human')
    parser.add_argument('--repository', help='Optional owner/repository for read-only permission observations')
    parser.add_argument('--require-admin', action='store_true')
    parser.add_argument('--check-webhooks', action='store_true')
    parser.add_argument('--timeout', type=float, default=5.0, help='Per-command deadline in seconds (0.1 to 30)')
    args = parser.parse_args()
    if (not public_name(args.hostname, r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?')
            or '..' in args.hostname or not 0.1 <= args.timeout <= 30):
        parser.error('invalid host or timeout')
    if args.repository:
        parts = args.repository.split('/')
        if (len(parts) != 2 or not public_name(parts[0], LOGIN)
                or not public_name(parts[1], r'[A-Za-z0-9_.-]{1,100}')
                or parts[1] in ('.', '..')):
            parser.error('invalid repository')
    if (args.require_admin or args.check_webhooks) and not args.repository:
        parser.error('repository required')
    receipt = evaluate(args)
    if args.format == 'json':
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        for item in receipt['capabilities']:
            label = 'SKIP' if not item['requested'] else 'PASS' if item['state'] == 'ready' else 'FAIL'
            print(f"{label}  {item['capability']}: {item['state']}")
            if item['remediation']:
                print('      ' + item['remediation'])
        print('RESULT: selected GitHub checks ' + ('passed' if receipt['ready'] else 'not ready'))
        print('Unverified: ' + ', '.join(receipt['unverified']))
    return 0 if receipt['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
