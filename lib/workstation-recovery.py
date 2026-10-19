#!/usr/bin/env python3
"""Durable metadata and bounded recovery for the existing managed transaction."""
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_bytes(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('metadata destination is a symlink')
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_dir(path.parent)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path, value):
    atomic_bytes(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('metadata must be a regular file')
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(path):
    path = Path(path)
    if path.is_symlink():
        return {'type': 'symlink', 'target': os.readlink(path)}
    if not path.exists():
        return {'type': 'absent'}
    mode = stat.S_IMODE(path.stat().st_mode)
    if path.is_file():
        return {'type': 'file', 'sha256': digest(path), 'mode': mode}
    if not path.is_dir():
        raise ValueError('unsupported managed path type')
    entries = {}
    for parent, directories, files in os.walk(path, followlinks=False):
        for name in sorted(directories + files):
            child = Path(parent) / name
            if child.is_symlink() or child.is_file():
                value = fingerprint(child)
            elif child.is_dir():
                value = {'type': 'directory', 'mode': stat.S_IMODE(child.stat().st_mode)}
            else:
                raise ValueError('unsupported backup entry type')
            entries[str(child.relative_to(path))] = value
    raw = json.dumps(entries, sort_keys=True).encode()
    return {'type': 'directory', 'sha256': hashlib.sha256(raw).hexdigest(), 'mode': mode}


# The activation contract is already the owner-authorized, version-bound
# transaction input. Classify the reserved Codex subtree there, per entry;
# the pathname alone is not evidence that an entry is an OpenAI built-in.
RETIRED_SYSTEM_SKILLS = {
    'governed-edit-protocol', 'llmstack-installer-discipline',
    'vsok-diff-churn-guard', 'vsok-html-singlefile-modularization',
    'vsok-invariants-snapshot', 'vsok-persistence-schema-guard',
    'vsok-preflight-regression-harness', 'vsok-refactor-protocol',
    'vsok-release-and-tag', 'vsok-skill-authoring-guardrails',
    'vsok-spec-contract-guard', 'vsok-ticket-runner',
}


def system_skill_plan(contract_path, home):
    contract = read_json(contract_path)
    root = Path(home) / '.codex/skills/.system'
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError('Codex .system root must be a real directory')
    actual = {p.name: p for p in root.iterdir()} if root.exists() else {}
    records = contract.get('codexSystemSkills')
    if not isinstance(records, list):
        raise ValueError('Codex .system classification is required in activation contract')
    plan = {}
    for item in records:
        if not isinstance(item, dict):
            raise ValueError('invalid Codex .system classification')
        name = item.get('name')
        if not isinstance(name, str) or name in ('.', '..') or not re.fullmatch(r'[A-Za-z0-9._-]+', name):
            raise ValueError('unsafe Codex .system entry name')
        if name in plan:
            raise ValueError('duplicate Codex .system classification: ' + name)
        category = item.get('classification')
        action = item.get('action')
        if category not in ('openai-builtin', 'owner-managed', 'retired-legacy'):
            raise ValueError('unknown Codex .system classification: ' + name)
        if action != ('exclude' if category == 'retired-legacy' else 'preserve'):
            raise ValueError('invalid Codex .system action: ' + name)
        if (name in RETIRED_SYSTEM_SKILLS or name.startswith('vsok-')) and category != 'retired-legacy':
            raise ValueError('retired legacy Codex .system skill cannot be preserved: ' + name)
        if category == 'retired-legacy' and name not in RETIRED_SYSTEM_SKILLS:
            raise ValueError('legacy exclusion lacks repository retirement authority: ' + name)
        for field in ('evidenceReference', 'authorityReference'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError('Codex .system classification lacks ' + field + ': ' + name)
        if name not in actual or actual[name].is_symlink() or not (actual[name].is_dir() or actual[name].is_file()):
            raise ValueError('Codex .system entry is missing or not a regular file/directory: ' + name)
        observed = fingerprint(actual[name])
        if item.get('fingerprint') != observed:
            raise ValueError('Codex .system classification is stale: ' + name)
        plan[name] = item
    if set(plan) != set(actual):
        raise ValueError('Codex .system has unclassified entries: ' + ', '.join(sorted(set(actual) - set(plan))))
    return root, plan


def stage_system_skills(contract_path, home, destination):
    root, plan = system_skill_plan(contract_path, home)
    destination = Path(destination)
    for name, item in plan.items():
        if item['action'] == 'preserve':
            if (root / name).is_dir():
                shutil.copytree(root / name, destination / name, symlinks=True, copy_function=shutil.copy2)
            else:
                shutil.copy2(root / name, destination / name)
            if fingerprint(destination / name) != item['fingerprint']:
                raise ValueError('Codex .system staged bytes differ: ' + name)
    # Recheck excluded entries too: they must not change between classification
    # and staging even though they are intentionally absent from the new release.
    system_skill_plan(contract_path, home)


def sync_tree(path):
    path = Path(path)
    if path.is_symlink():
        return
    if path.is_file():
        with path.open('rb') as stream:
            os.fsync(stream.fileno())
        return
    for child in path.iterdir():
        sync_tree(child)
    sync_dir(path)


def relative(value):
    if not isinstance(value, str) or not value or '\t' in value or '\n' in value:
        raise ValueError('invalid managed relative path')
    p = Path(value)
    if p.is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError('managed path escapes its scope')
    return p


def safe_parent(path, root):
    if not Path(path).parent.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('managed parent escapes target home')


def seal(home, release, manifest_path, map_path):
    home, release, manifest_path = Path(home), Path(release), Path(manifest_path)
    manifest = read_json(manifest_path)
    entries = {x['relativePath']: x for x in manifest['paths']}
    rows = Path(map_path).read_text().splitlines()
    if len(rows) != len(entries):
        raise ValueError('install map and backup manifest disagree')
    seen = set()
    for row in rows:
        name, kind, source = row.split('\t')
        rel = relative(name)
        if name in seen or name not in entries:
            raise ValueError('duplicate or missing managed path')
        seen.add(name)
        entry = entries[name]
        live, backup = home / rel, manifest_path.parent / relative(entry['backupRelative'])
        safe_parent(live, home)
        original = fingerprint(live)
        if original['type'] != entry['originalType']:
            raise ValueError('pre-state changed while staging')
        if original['type'] != 'absent' and fingerprint(backup) != original:
            raise ValueError('backup differs from its preimage')
        entry['originalFingerprint'] = original
        if kind == 'link':
            src = relative(source)
            material = release / src
            candidate = {'type': 'symlink', 'target': str(home / '.local/share/engineering-workstation-bootstrap/current' / src)}
            # File referents include mutable settings and command links. A
            # changed candidate file is never silently discarded by recovery.
            if material.is_file() and not material.is_symlink():
                entry['candidateReferent'] = {'path': str(material), 'fingerprint': fingerprint(material)}
        elif kind == 'file':
            candidate = fingerprint(source)
            if candidate['type'] != 'file':
                raise ValueError('candidate file is unavailable')
        else:
            raise ValueError('unsupported install map kind')
        entry['candidateFingerprint'] = candidate
    write_json(manifest_path, manifest)
    sync_tree(release)
    sync_tree(manifest_path.parent)
    sync_dir(manifest_path.parent.parent)


def load_transaction(receipt_path, home):
    receipt_path, home = Path(receipt_path), Path(home).resolve()
    receipt = read_json(receipt_path)
    txn, version = receipt.get('transactionId'), receipt.get('version')
    if not all(isinstance(x, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', x) for x in (txn, version)):
        raise ValueError('invalid transaction identity')
    state = home / '.local/state/engineering-workstation-bootstrap'
    share = home / '.local/share/engineering-workstation-bootstrap'
    manifest_path = state / 'backups' / txn / 'manifest.json'
    release = share / 'versions' / (version + '-' + txn)
    for path in (receipt_path, manifest_path, release):
        safe_parent(path, home)
    if receipt_path != state / 'receipts' / ('activation-' + txn + '.json') or receipt.get('targetHome') != str(home):
        raise ValueError('receipt identity or target mismatch')
    if receipt.get('releaseDir') != str(release) or receipt.get('backupManifest') != str(manifest_path):
        raise ValueError('receipt source paths do not match transaction')
    manifest = read_json(manifest_path)
    if receipt.get('recoveryProtocol') != 1 or digest(manifest_path) != receipt.get('backupManifestSha256'):
        raise ValueError('backup manifest binding mismatch')
    if release.is_symlink() or not release.is_dir():
        raise ValueError('candidate release is not an immutable managed directory')
    previous = receipt.get('previousCurrent', '')
    if previous and (not Path(previous).is_absolute() or not Path(previous).resolve().is_relative_to((share / 'versions').resolve()) or Path(previous).is_symlink() or not Path(previous).is_dir()):
        raise ValueError('predecessor release is outside the managed versions')
    if manifest.get('transactionId') != txn or manifest.get('targetHome') != str(home):
        raise ValueError('backup manifest identity mismatch')
    names = set()
    for entry in manifest['paths']:
        rel = relative(entry['relativePath'])
        if str(rel) in names:
            raise ValueError('duplicate managed path')
        names.add(str(rel))
        expected_backup = str(Path('files') / rel)
        if entry['backupRelative'] != expected_backup:
            raise ValueError('backup path does not match managed preimage')
        backup = manifest_path.parent / relative(entry['backupRelative'])
        safe_parent(backup, manifest_path.parent)
        safe_parent(home / rel, home)
        original = entry['originalFingerprint']
        if original['type'] != entry['originalType']:
            raise ValueError('preimage type mismatch')
        if original['type'] != 'absent' and fingerprint(backup) != original:
            raise ValueError('backup preimage is unavailable or changed')
        ref = entry.get('candidateReferent')
        if ref and (not Path(ref['path']).is_relative_to(release) or fingerprint(ref['path']) != ref['fingerprint']):
            raise ValueError('candidate managed material changed')
    return receipt, manifest, state, share, release


def custody(receipt, state, share, release):
    pointer = share / 'current'
    if pointer.is_symlink():
        selected = os.readlink(pointer)
    elif pointer.exists():
        raise ValueError('current pointer is not a symlink')
    else:
        selected = ''
    marker = state / 'current-transaction'
    if marker.is_symlink():
        raise ValueError('transaction marker is a symlink')
    current_txn = marker.read_text().strip() if marker.exists() else ''
    prior = (receipt.get('previousCurrent', ''), receipt.get('previousTransaction', ''))
    candidate = (str(release), receipt['transactionId'])
    status = receipt.get('status')
    if status == 'active':
        allowed = {candidate}
    elif status == 'rolled-back':
        allowed = {prior}
    elif status == 'applying' or (status == 'recovery-required' and not receipt.get('rollbackStarted')):
        allowed = {prior, (str(release), prior[1]), candidate}
    elif status == 'rolling-back' or (status == 'recovery-required' and receipt.get('rollbackStarted')):
        allowed = {prior, (str(release), prior[1]), candidate, (prior[0], candidate[1])}
    else:
        raise ValueError('receipt is not in a recoverable phase')
    if (selected, current_txn) not in allowed:
        raise ValueError('current pointer or marker belongs to another transaction')


def live_paths(receipt, manifest, home):
    pending = receipt.get('pendingPath')
    for entry in manifest['paths']:
        actual = fingerprint(Path(home) / relative(entry['relativePath']))
        choices = [entry['originalFingerprint'], entry['candidateFingerprint']]
        if pending == entry['relativePath']:
            choices.append({'type': 'absent'})
        if actual not in choices:
            raise ValueError('managed path has unrelated content: ' + entry['relativePath'])


def patch(path, delta):
    data = read_json(path)
    data.update(delta)
    write_json(path, data)
    return data


def checkpoint(name):
    if os.environ.get('WORKSTATION_ROLLBACK_FAIL_POINT') == name:
        if os.environ.get('WORKSTATION_ROLLBACK_FAIL_MODE') == 'exit':
            raise SystemExit(75)
        raise OSError('controlled rollback boundary: ' + name)


def atomic_link(target, path):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.recovery-' + str(os.getpid()))
    try:
        temporary.symlink_to(target)
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def recover(receipt_path, home):
    receipt_path, home = Path(receipt_path), Path(home).resolve()
    receipt, manifest, state, share, release = load_transaction(receipt_path, home)
    custody(receipt, state, share, release)
    live_paths(receipt, manifest, home)
    if receipt['status'] == 'rolled-back':
        if any(fingerprint(home / relative(e['relativePath'])) != e['originalFingerprint'] for e in manifest['paths']):
            raise ValueError('completed rollback preimage changed')
        return
    try:
        receipt = patch(receipt_path, {'status': 'rolling-back', 'rollbackStarted': True})
        checkpoint('before-paths')
        # Restore the interrupted path before advancing pendingPath. Otherwise
        # its intentional gap would lose the only receipt-bound allowance.
        pending = receipt.get('pendingPath')
        ordered = list(reversed(manifest['paths']))
        if pending:
            ordered.sort(key=lambda entry: entry['relativePath'] != pending)
        for entry in ordered:
            name = entry['relativePath']
            live = home / relative(name)
            original = entry['originalFingerprint']
            receipt = patch(receipt_path, {'pendingPath': name, 'phase': 'restoring-paths'})
            custody(receipt, state, share, release)
            live_paths(receipt, manifest, home)
            checkpoint('before-path:' + name)
            staging = None
            try:
                if original['type'] != 'absent':
                    backup = Path(receipt['backupManifest']).parent / relative(entry['backupRelative'])
                    live.parent.mkdir(parents=True, exist_ok=True)
                    staging = Path(tempfile.mkdtemp(prefix='.recovery-', dir=live.parent)) / 'payload'
                    if backup.is_symlink():
                        staging.symlink_to(os.readlink(backup))
                    elif backup.is_dir():
                        shutil.copytree(backup, staging, symlinks=True, copy_function=shutil.copy2)
                    else:
                        shutil.copy2(backup, staging)
                    if fingerprint(staging) != original:
                        raise ValueError('staged restore differs from sealed backup')
                    sync_tree(staging)
                    sync_dir(staging.parent)
                # Recheck the actual destination immediately before replacing it.
                live_paths(receipt, manifest, home)
                if live.is_symlink() or live.is_file():
                    live.unlink()
                elif live.exists():
                    shutil.rmtree(live)
                if live.parent.exists():
                    sync_dir(live.parent)
                checkpoint('after-remove:' + name)
                if staging:
                    os.replace(staging, live)
                    sync_dir(live.parent)
                    staging.parent.rmdir()
            finally:
                # Clean only this invocation's owned staging copy. Sealed
                # backups remain intact for every retry.
                if staging and staging.parent.exists():
                    shutil.rmtree(staging.parent)
                    sync_dir(live.parent)
            if fingerprint(live) != original:
                raise ValueError('restored path does not match preimage')
            receipt = patch(receipt_path, {'pendingPath': None})
            checkpoint('after-path:' + name)
        receipt = patch(receipt_path, {'phase': 'restoring-pointer'})
        checkpoint('before-pointer')
        custody(receipt, state, share, release)
        previous = receipt.get('previousCurrent', '')
        if previous:
            atomic_link(previous, share / 'current')
        elif (share / 'current').is_symlink():
            (share / 'current').unlink()
            sync_dir(share)
        checkpoint('after-pointer')
        receipt = patch(receipt_path, {'phase': 'restoring-marker'})
        prior_txn = receipt.get('previousTransaction', '')
        if prior_txn:
            atomic_bytes(state / 'current-transaction', (prior_txn + '\n').encode())
        elif (state / 'current-transaction').exists():
            (state / 'current-transaction').unlink()
            sync_dir(state)
        checkpoint('after-marker')
        custody(receipt, state, share, release)
        rollback_path = state / 'receipts' / ('rollback-' + receipt['transactionId'] + '.json')
        completed_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        write_json(rollback_path, {'schemaVersion': 1, 'transactionId': receipt['transactionId'],
                                 'targetHome': str(home), 'activationReceipt': str(receipt_path),
                                 'status': 'rolled-back', 'completedAt': completed_at,
                                 'restoredAllManagedPaths': True, 'secretValues': False})
        checkpoint('before-completion')
        patch(receipt_path, {'status': 'rolled-back', 'phase': 'rolled-back',
                             'rollbackReceipt': str(rollback_path), 'rolledBackAt': completed_at, 'pendingPath': None,
                             'recoveryError': None})
    except Exception as error:
        patch(receipt_path, {'status': 'recovery-required', 'recoveryError': str(error)})
        raise


def main():
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == 'write-json':
        write_json(args[0], json.load(sys.stdin))
    elif mode == 'write-text':
        atomic_bytes(args[0], (args[1] + '\n').encode())
    elif mode == 'patch':
        patch(args[0], json.loads(args[1]))
    elif mode == 'seal':
        seal(*args)
    elif mode == 'system-skills-check':
        system_skill_plan(*args)
    elif mode == 'system-skills-stage':
        stage_system_skills(*args)
    elif mode == 'fingerprint':
        print(json.dumps(fingerprint(args[0]), sort_keys=True))
    elif mode == 'sync-parent':
        sync_dir(Path(args[0]).parent)
    elif mode == 'validate-current':
        receipt, manifest, state, share, release = load_transaction(*args)
        custody(receipt, state, share, release)
        live_paths(receipt, manifest, args[1])
    elif mode == 'validate-start':
        receipt, manifest, state, share, release = load_transaction(*args)
        custody(receipt, state, share, release)
        pointer = share / 'current'
        selected = os.readlink(pointer) if pointer.is_symlink() else ''
        marker = state / 'current-transaction'
        current_txn = marker.read_text().strip() if marker.exists() else ''
        if (selected, current_txn) != (receipt.get('previousCurrent', ''), receipt.get('previousTransaction', '')):
            raise ValueError('predecessor custody changed before publication')
        if any(fingerprint(Path(args[1]) / relative(e['relativePath'])) != e['originalFingerprint'] for e in manifest['paths']):
            raise ValueError('managed pre-state changed before publication')
    elif mode == 'recover':
        recover(*args)
    else:
        raise ValueError('unsupported recovery operation')


if __name__ == '__main__':
    try:
        main()
    except Exception as failure:
        print('REFUSE: ' + str(failure), file=sys.stderr)
        raise SystemExit(64)
