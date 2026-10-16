"""Bounded, read-only exact-source preflight for an admitted review task.

This extends the existing connector doctor. It neither obtains credentials nor
turns a local fixture into hosted or skill-consumption evidence.
"""
import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import uuid
import urllib.error
import urllib.request

SCHEMA = 1
SHA = re.compile(r'^[0-9a-f]{40}$')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
MAX_BYTES = 2_000_000
ENCODED_BLOB_BYTES = 4 * ((MAX_BYTES + 2) // 3)
# Bound the JSON wire form, including wrapped newlines and possible slash escapes.
MAX_BLOB_RESPONSE_BYTES = (2 * ENCODED_BLOB_BYTES
                           + 4 * ((ENCODED_BLOB_BYTES + 59) // 60) + 4096)
GIT = ['git', '--no-replace-objects']
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifests/connector-capabilities.json'


class Failed(Exception):
    def __init__(self, code, attempts=None):
        super().__init__(code)
        self.code = code
        self.attempts = attempts or []


def command(argv, cwd=None, timeout=12):
    try:
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Failed('TIMEOUT_OR_TOOL_UNAVAILABLE' if isinstance(exc, subprocess.TimeoutExpired)
                     else 'TOOL_UNAVAILABLE') from None


def bounded_api_command(argv, max_bytes, timeout=15):
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        raise Failed('TOOL_UNAVAILABLE') from None
    expired = threading.Event()

    def stop():
        expired.set()
        if process.poll() is None:
            process.kill()

    timer = threading.Timer(timeout, stop)
    timer.start()
    try:
        payload = process.stdout.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise Failed('API_RESPONSE_TOO_LARGE')
        status = process.wait()
    except OSError:
        raise Failed('AUTH_OR_API_UNAVAILABLE') from None
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
    if expired.is_set() or status:
        raise Failed('AUTH_OR_API_UNAVAILABLE')
    return payload


def remote_identity(url):
    match = re.fullmatch(r'(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?', url)
    return match.group(1) if match else None


def artifact_path(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not value or value.startswith('-'):
        raise Failed('INVALID_ARTIFACT_PATH')
    return value


def git_source(args):
    if not shutil.which('git'):
        raise Failed('TOOL_UNAVAILABLE')
    root = Path(args.repository).resolve()
    inside = command(GIT + ['rev-parse', '--show-toplevel'], cwd=root)
    if inside.returncode or Path(inside.stdout.strip()).resolve() != root:
        raise Failed('REPOSITORY_NOT_CONFIGURED')
    origin = command(GIT + ['remote', 'get-url', 'origin'], cwd=root)
    if origin.returncode or not origin.stdout.strip():
        raise Failed('REMOTE_NOT_CONFIGURED')
    if remote_identity(origin.stdout.strip()) != args.identity:
        raise Failed('WRONG_REPOSITORY')
    if not origin.stdout.strip().startswith(('git@github.com:', 'ssh://git@github.com/')):
        raise Failed('UNSUPPORTED_GIT_TRANSPORT')
    reachable = command(GIT + ['ls-remote', '--refs', 'origin'], cwd=root)
    if reachable.returncode:
        raise Failed('NETWORK_OR_AUTH_UNAVAILABLE')
    remote_refs = {fields[0] for line in reachable.stdout.splitlines()
                   if len(fields := line.split()) == 2 and SHA.fullmatch(fields[0])}
    has_commit = command(GIT + ['cat-file', '-e', args.sha + '^{commit}'], cwd=root)
    if has_commit.returncode:
        raise Failed('SOURCE_COMMIT_MISSING')
    if args.pr:
        head = command(GIT + ['ls-remote', 'origin', f'refs/pull/{args.pr}/head'], cwd=root)
        if head.returncode or not head.stdout.strip():
            raise Failed('PR_HEAD_UNAVAILABLE')
        if head.stdout.split()[0] != args.sha:
            raise Failed('WRONG_HEAD')
    if args.sha not in remote_refs:
        grafts = command(GIT + ['rev-parse', '--git-path', 'info/grafts'], cwd=root)
        graft_path = Path(grafts.stdout.strip())
        if not graft_path.is_absolute():
            graft_path = root / graft_path
        if grafts.returncode or graft_path.is_file():
            raise Failed('SOURCE_COMMIT_REMOTE_UNVERIFIED')
        anchored = False
        for tip in remote_refs:
            if command(GIT + ['cat-file', '-e', tip + '^{commit}'], cwd=root).returncode:
                continue
            ancestry = command(GIT + ['merge-base', '--is-ancestor', args.sha, tip], cwd=root)
            if ancestry.returncode == 0:
                anchored = True
                break
        if not anchored:
            raise Failed('SOURCE_COMMIT_REMOTE_UNVERIFIED')
    hashes = {}
    for name in args.artifact:
        object_name = f'{args.sha}:{name}'
        listed = command(GIT + ['ls-tree', '-r', '-z', args.sha, '--', name], cwd=root)
        if listed.returncode:
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        entries = [line.split('\t', 1) for line in listed.stdout.split('\0') if line]
        matching = [metadata.split() for metadata, path in entries if path == name]
        if len(matching) != 1 or len(matching[0]) != 3 or matching[0][:2] not in (
                ['100644', 'blob'], ['100755', 'blob']):
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        kind = command(GIT + ['cat-file', '-t', object_name], cwd=root)
        if kind.returncode or kind.stdout.strip() != 'blob':
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        size = command(GIT + ['cat-file', '-s', object_name], cwd=root)
        if size.returncode or not size.stdout.strip().isdigit() or int(size.stdout.strip()) > MAX_BYTES:
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        try:
            result = subprocess.run(GIT + ['show', object_name], cwd=root,
                                    capture_output=True, timeout=12, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE') from None
        if result.returncode or len(result.stdout) > MAX_BYTES:
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        git_digest = hashlib.sha1(b'blob ' + str(len(result.stdout)).encode()
                                  + b'\0' + result.stdout).hexdigest()
        if git_digest != matching[0][2]:
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        hashes[name] = hashlib.sha256(result.stdout).hexdigest()
    return {'transport': 'git-remote', 'artifact_sha256': hashes,
            'remote': 'github.com/' + args.identity}


def api_get(path, token, via_gh, max_bytes=MAX_BYTES):
    if via_gh:
        if command(['gh', 'auth', 'status', '--hostname', 'github.com']).returncode:
            raise Failed('AUTH_MISSING')
        payload = bounded_api_command(['gh', 'api', '--method', 'GET', path], max_bytes)
    else:
        request = urllib.request.Request('https://api.github.com/' + path.lstrip('/'),
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                     'User-Agent': 'workstation-source-preflight/1'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(),
                                             type('NoRedirect', (urllib.request.HTTPRedirectHandler,),
                                                  {'redirect_request': lambda self, *unused: None})())
        try:
            with opener.open(request, timeout=12) as response:
                payload = response.read(max_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise Failed('AUTH_MISSING' if exc.code == 401 else
                         'ACCESS_DENIED' if exc.code == 403 else
                         ('SOURCE_COMMIT_MISSING' if '/git/commits/' in path else
                         'SOURCE_ARTIFACT_UNAVAILABLE' if '/git/trees/' in path or '/git/blobs/' in path else
                          'REPOSITORY_OR_AUTH_UNAVAILABLE') if exc.code == 404 else
                         'NETWORK_DENIED') from None
        except (OSError, TimeoutError):
            raise Failed('NETWORK_DENIED') from None
    if len(payload) > max_bytes:
        raise Failed('API_RESPONSE_TOO_LARGE')
    try:
        return json.loads(payload)
    except (ValueError, UnicodeError):
        raise Failed('TOOL_SCHEMA_MISMATCH') from None


def api_artifact(prefix, name, root_tree, token, via_gh):
    tree_sha = root_tree
    parts = Path(name).parts
    for index, part in enumerate(parts):
        tree = api_get(prefix + '/git/trees/' + tree_sha, token, via_gh)
        if (not isinstance(tree, dict) or tree.get('sha') != tree_sha
                or not isinstance(tree.get('tree'), list)
                or not isinstance(tree.get('truncated'), bool)):
            raise Failed('TOOL_SCHEMA_MISMATCH')
        if tree['truncated']:
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        entries = tree['tree']
        if any(not isinstance(entry, dict) or not isinstance(entry.get('path'), str)
               for entry in entries):
            raise Failed('TOOL_SCHEMA_MISMATCH')
        matching = [entry for entry in entries if entry['path'] == part]
        if len(matching) != 1:
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        entry = matching[0]
        if (not isinstance(entry.get('sha'), str) or not SHA.fullmatch(entry['sha'])
                or not isinstance(entry.get('type'), str)
                or not isinstance(entry.get('mode'), str)):
            raise Failed('TOOL_SCHEMA_MISMATCH')
        if index < len(parts) - 1:
            if entry['type'] != 'tree' or entry['mode'] != '040000':
                raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
            tree_sha = entry['sha']
            continue
        if entry['type'] != 'blob' or entry['mode'] not in ('100644', '100755'):
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        size = entry.get('size')
        if type(size) is not int or size < 0:
            raise Failed('TOOL_SCHEMA_MISMATCH')
        if size > MAX_BYTES:
            raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')
        blob = api_get(prefix + '/git/blobs/' + entry['sha'], token, via_gh,
                       max_bytes=MAX_BLOB_RESPONSE_BYTES)
        if (not isinstance(blob, dict) or blob.get('sha') != entry['sha']
                or blob.get('encoding') != 'base64'
                or not isinstance(blob.get('content'), str)
                or type(blob.get('size')) is not int or blob['size'] != size):
            raise Failed('TOOL_SCHEMA_MISMATCH')
        try:
            encoded = re.sub(r'[\t\n\r ]', '', blob['content'])
            data = base64.b64decode(encoded, validate=True)
            if base64.b64encode(data).decode('ascii') != encoded:
                raise Failed('TOOL_SCHEMA_MISMATCH')
        except (ValueError, binascii.Error):
            raise Failed('TOOL_SCHEMA_MISMATCH') from None
        if len(data) != size:
            raise Failed('TOOL_SCHEMA_MISMATCH')
        git_digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if git_digest != entry['sha']:
            raise Failed('TOOL_SCHEMA_MISMATCH')
        return hashlib.sha256(data).hexdigest()
    raise Failed('SOURCE_ARTIFACT_UNAVAILABLE')


def api_source(args, via_gh):
    token = None
    if not via_gh:
        if args.api_token_env not in ('GH_TOKEN', 'GITHUB_TOKEN'):
            raise Failed('AUTH_MISSING')
        token = os.environ.get(args.api_token_env)
        if not token:
            raise Failed('AUTH_MISSING')
    prefix = 'repos/' + args.identity
    repo = api_get(prefix, token, via_gh)
    if not isinstance(repo, dict) or not isinstance(repo.get('full_name'), str):
        raise Failed('TOOL_SCHEMA_MISMATCH')
    if repo.get('full_name') != args.identity:
        raise Failed('WRONG_REPOSITORY')
    commit = api_get(prefix + '/git/commits/' + args.sha, token, via_gh)
    if not isinstance(commit, dict) or not isinstance(commit.get('sha'), str):
        raise Failed('TOOL_SCHEMA_MISMATCH')
    if commit.get('sha') != args.sha:
        raise Failed('WRONG_HEAD')
    if (not isinstance(commit.get('tree'), dict)
            or not isinstance(commit['tree'].get('sha'), str)
            or not SHA.fullmatch(commit['tree']['sha'])):
        raise Failed('TOOL_SCHEMA_MISMATCH')
    if args.pr:
        pull = api_get(prefix + '/pulls/' + str(args.pr), token, via_gh)
        if (not isinstance(pull, dict) or not isinstance(pull.get('base'), dict)
                or not isinstance(pull['base'].get('repo'), dict)
                or not isinstance(pull['base']['repo'].get('full_name'), str)
                or not isinstance(pull.get('head'), dict)
                or not isinstance(pull['head'].get('sha'), str)):
            raise Failed('TOOL_SCHEMA_MISMATCH')
        if pull['base']['repo']['full_name'] != args.identity:
            raise Failed('WRONG_REPOSITORY')
        if pull['head']['sha'] != args.sha:
            raise Failed('WRONG_HEAD')
    hashes = {}
    for name in args.artifact:
        hashes[name] = api_artifact(prefix, name, commit['tree']['sha'], token, via_gh)
    return {'transport': 'gh-api' if via_gh else 'authenticated-github-api',
            'artifact_sha256': hashes, 'remote': 'api.github.com/' + args.identity}


def model_probe(model, repository, timeout):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', model) or timeout < 1 or timeout > 30:
        raise Failed('INVALID_MODEL_PROBE')
    if not shutil.which('codex'):
        raise Failed('MODEL_UNAVAILABLE')
    try:
        result = subprocess.run(['codex', 'exec', '--ephemeral', '--sandbox', 'read-only',
            '--skip-git-repo-check', '--model', model, '-C', repository,
            'Reply only PREFLIGHT_OK'], stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Failed('TIMEOUT_OR_STDIN_WAIT') from None
    except OSError:
        raise Failed('MODEL_UNAVAILABLE') from None
    if result.returncode == 0 and 'PREFLIGHT_OK' in result.stdout:
        return
    if re.search(r'(unknown model|model.{0,40}(unavailable|not supported|not found))',
                 result.stderr, re.IGNORECASE):
        raise Failed('MODEL_UNAVAILABLE')
    raise Failed('MODEL_PROBE_FAILED')


def preflight(args):
    if not REPO.fullmatch(args.identity) or not SHA.fullmatch(args.sha):
        raise Failed('INVALID_SOURCE_IDENTITY')
    if not args.artifact:
        raise Failed('SOURCE_ARTIFACT_REQUIRED')
    args.artifact = [artifact_path(x) for x in args.artifact]
    if args.min_scratch_mb < 0:
        raise Failed('INVALID_SCRATCH_REQUIREMENT')
    for tool in args.required_tool:
        if not re.fullmatch(r'[A-Za-z0-9_.+-]+', tool) or not shutil.which(tool):
            raise Failed('TOOL_UNAVAILABLE')
    for skill in args.required_skill:
        if not (Path(skill) / 'SKILL.md').is_file():
            raise Failed('SKILL_MISSING')
    try:
        free = shutil.disk_usage(args.scratch).free
    except OSError:
        raise Failed('SCRATCH_EXHAUSTED') from None
    if free < args.min_scratch_mb * 1024 * 1024:
        raise Failed('SCRATCH_EXHAUSTED')
    attempts = []
    source = None
    for label, fn in [('git-remote', lambda: git_source(args)),
                      ('gh-api', lambda: api_source(args, True)),
                      ('authenticated-github-api', lambda: api_source(args, False))]:
        if label == 'gh-api' and not shutil.which('gh'):
            attempts.append({'transport': label, 'reason': 'TOOL_UNAVAILABLE'})
            continue
        if label == 'authenticated-github-api' and not args.api_token_env:
            attempts.append({'transport': label, 'reason': 'AUTH_MISSING'})
            continue
        try:
            source = fn()
            break
        except Failed as exc:
            attempts.append({'transport': label, 'reason': exc.code})
            if exc.code in ('WRONG_REPOSITORY', 'WRONG_HEAD'):
                raise Failed(exc.code, attempts) from None
    if source is None:
        raise Failed('SOURCE_UNAVAILABLE', attempts)
    if args.required_model:
        model_probe(args.required_model, args.repository, args.model_timeout)
    return source, attempts, free


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--identity', required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--pr', type=int)
    parser.add_argument('--artifact', action='append', default=[])
    parser.add_argument('--required-tool', action='append', default=[])
    parser.add_argument('--required-skill', action='append', default=[])
    parser.add_argument('--required-model')
    parser.add_argument('--model-timeout', type=int, default=20)
    parser.add_argument('--scratch', default='/tmp')
    parser.add_argument('--min-scratch-mb', type=int, default=128)
    parser.add_argument('--api-token-env')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    contract = json.loads(MANIFEST.read_text())['source_preflight']
    if contract.get('schema_version') != SCHEMA or not contract.get('fail_closed'):
        raise Failed('PREFLIGHT_CONTRACT_INVALID')
    receipt = {'schema_version': SCHEMA, 'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
               'identity': args.identity, 'sha': args.sha, 'pr': args.pr,
               'artifacts': args.artifact, 'source_verified': False,
               'required_tools': args.required_tool,
               'required_skill_names': [Path(value).name for value in args.required_skill],
               'required_model': args.required_model,
               'minimum_scratch_mb': args.min_scratch_mb,
               'skill_consumption': 'UNOBSERVED', 'runtime_activation': False,
               'secret_values': False,
               'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
               'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        source, attempts, free = preflight(args)
        receipt.update(source_verified=True, source=source, attempts=attempts,
                       checks={'tool_presence': True if args.required_tool else 'NOT_REQUESTED',
                               'skill_wrapper_presence': True if args.required_skill else 'NOT_REQUESTED',
                               'scratch_headroom': True,
                               'model_probe': True if args.required_model else 'NOT_REQUESTED'},
                       scratch_free_bytes=free, reason='READY_FOR_SCOPED_READ')
        exit_code = 0
    except Failed as exc:
        receipt.update(reason=exc.code, attempts=exc.attempts)
        exit_code = 1
    payload = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
    if args.output:
        dest = Path(args.output)
        try:
            if dest.is_symlink():
                raise Failed('OUTPUT_SYMLINK_REFUSED')
            dest.parent.mkdir(parents=True, exist_ok=True)
            temporary = dest.with_name(dest.name + '.' + uuid.uuid4().hex)
            try:
                fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    stream.write(payload)
                os.link(temporary, dest)
            finally:
                temporary.unlink(missing_ok=True)
        except FileExistsError:
            receipt.update(source_verified=False, reason='OUTPUT_EXISTS')
            exit_code = 1
            payload = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
        except Failed as exc:
            receipt.update(source_verified=False, reason=exc.code)
            exit_code = 1
            payload = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
        except OSError:
            receipt.update(source_verified=False, reason='OUTPUT_UNAVAILABLE')
            exit_code = 1
            payload = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
    print(payload, end='')
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
