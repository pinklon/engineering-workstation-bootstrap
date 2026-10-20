#!/usr/bin/env python3
"""Install one pinned Codex instruction file through the managed release pointer."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workstation_recovery', ROOT / 'lib/workstation-recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
INSTRUCTIONS = Path('config/codex/AGENTS.md')
CATALOG = 'architecture/mesh-presentation-aliases.v1.json'
EXPECTED_ALIASES = [
    {'alias': 'segfault', 'target': 'ChatGPT architecture/reasoning partner', 'kind': 'agent'},
    {'alias': 'syscall', 'target': 'Codex engineering agent', 'kind': 'agent'},
    {'alias': 'phorse', 'target': 'existing Pale Horse coordinator', 'kind': 'agent'},
    {'alias': 'GhostMesh', 'target': 'overall system', 'kind': 'system'},
]
SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')
SHA = re.compile(r'[a-f0-9]{40}\Z')
SHA256 = re.compile(r'[a-f0-9]{64}\Z')


class ManagedPathDrift(ValueError):
    """A live managed path changed outside this pointer-only transaction."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL)


def pinned_file(repo, commit, path):
    require(isinstance(commit, str) and SHA.fullmatch(commit), 'invalid source commit pin')
    resolved = git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip()
    require(resolved == commit, 'source commit pin did not resolve exactly')
    return git(repo, 'show', commit + ':' + path)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def catalog_proof(contract, repo):
    raw = pinned_file(repo, contract['catalogCommit'], CATALOG)
    blob = git(repo, 'rev-parse', contract['catalogCommit'] + ':' + CATALOG).decode().strip()
    require(blob == contract['catalogBlobSha1'], 'catalog blob differs from accepted pin')
    value = json.loads(raw)
    require(value == {
        'schemaVersion': 'ghostmesh-presentation-aliases.v1',
        'sourceIssue': 'pinklon/shareplane-control-tower#1056',
        'authorityRegistry': 'architecture/mesh-identity-registry.v1.json',
        'presentationOnly': True,
        'aliases': EXPECTED_ALIASES,
    }, 'catalog is not the accepted presentation-only contract')
    return blob


def tree_without_instructions(root):
    """Seal entry bytes, links and modes without following release symlinks."""
    entries = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(parent) / name
            relative = str(path.relative_to(root))
            if relative == str(INSTRUCTIONS):
                continue
            if path.is_symlink():
                entries[relative] = {'type': 'symlink', 'target': os.readlink(path)}
            elif path.is_file():
                entries[relative] = {'type': 'file', 'sha256': sha256(path.read_bytes()),
                                     'mode': stat.S_IMODE(path.stat().st_mode)}
            elif path.is_dir():
                entries[relative] = {'type': 'directory', 'mode': stat.S_IMODE(path.stat().st_mode)}
            else:
                raise ValueError('unsupported release entry: ' + relative)
    return sha256(json.dumps(entries, sort_keys=True).encode())


def managed_paths_snapshot(home, manifest_path):
    manifest = recovery.read_json(manifest_path)
    paths = manifest.get('paths')
    require(isinstance(paths, list) and paths, 'predecessor managed path inventory is missing')
    require(all(isinstance(item, dict) and isinstance(item.get('relativePath'), str)
                for item in paths), 'predecessor managed path inventory is malformed')
    names = [item['relativePath'] for item in paths]
    require(len(set(names)) == len(names) and '.codex/AGENTS.md' in names,
            'predecessor managed path inventory is invalid')
    return {name: recovery.fingerprint(home / recovery.relative(name)) for name in names}


def verify_managed_paths(home, manifest_path, expected):
    try:
        actual = managed_paths_snapshot(home, manifest_path)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ManagedPathDrift('a managed live path cannot be safely fingerprinted') from error
    if actual != expected:
        raise ManagedPathDrift('a managed live path changed outside the instruction-only transaction')


def snapshot_hash(value):
    return sha256(json.dumps(value, sort_keys=True).encode())


def current_state(home, contract):
    state = home / '.local/state/engineering-workstation-bootstrap'
    share = home / '.local/share/engineering-workstation-bootstrap'
    versions = share / 'versions'
    pointer = share / 'current'
    marker = state / 'current-transaction'
    live = home / '.codex/AGENTS.md'
    require(pointer.is_symlink(), 'managed current pointer is missing')
    target = Path(os.readlink(pointer))
    require(target.is_absolute() and target.parent == versions and target.is_dir()
            and not target.is_symlink(), 'current does not select a direct managed release')
    require(marker.is_file() and not marker.is_symlink(), 'active transaction marker is missing')
    previous_txn = marker.read_text().strip()
    require(previous_txn == contract['expectedTransaction'], 'active transaction changed')
    require(str(target) == contract['expectedCurrent'], 'managed release changed')
    prior_receipt = state / 'receipts' / ('activation-' + previous_txn + '.json')
    prior = recovery.read_json(prior_receipt)
    require(prior.get('status') == 'active' and prior.get('transactionId') == previous_txn
            and prior.get('releaseDir') == str(target) and prior.get('targetHome') == str(home)
            and prior.get('backupManifest') == str(state / 'backups' / previous_txn / 'manifest.json'),
            'active release receipt is inconsistent')
    require(live.is_symlink() and os.readlink(live) == str(pointer / INSTRUCTIONS),
            'Codex instructions do not use the managed current link')
    source = target / INSTRUCTIONS
    require(source.is_file() and not source.is_symlink(), 'active instructions are not a regular release file')
    require(sha256(source.read_bytes()) == contract['expectedPreimageSha256'],
            'active instruction preimage changed')
    return state, share, target, pointer, marker, live, prior_receipt


def checkpoint(name):
    if os.environ.get('WORKSTATION_INSTRUCTIONS_FAIL_POINT') == name:
        if os.environ.get('WORKSTATION_INSTRUCTIONS_FAIL_MODE') == 'exit':
            raise SystemExit(75)
        raise OSError('controlled instruction transition: ' + name)


def lock_state(state, transaction):
    lock = state / 'activation.lock'
    lock.mkdir()
    try:
        recovery.write_json(lock / 'owner.json', {'pid': os.getpid(), 'transactionId': transaction})
    except Exception:
        lock.rmdir()
        raise
    return lock


def unlock_state(lock):
    if lock:
        (lock / 'owner.json').unlink(missing_ok=True)
        lock.rmdir()


def install(args):
    home = Path(args.home).resolve(strict=True)
    contract = recovery.read_json(args.contract)
    required = {'schemaVersion', 'instructionOnlyAuthorized', 'allowLiveHome', 'authorityReference',
                'targetHome', 'version', 'workstationCommit', 'workstationInstructionSha256',
                'catalogCommit', 'catalogBlobSha1', 'expectedCurrent', 'expectedTransaction',
                'expectedPreimageSha256'}
    require(set(contract) == required and contract['schemaVersion'] == 1
            and contract['instructionOnlyAuthorized'] is True, 'invalid instruction-only contract')
    require(type(contract['allowLiveHome']) is bool, 'invalid live-home setting')
    require(contract['targetHome'] == str(home) and bool(contract['authorityReference']),
            'contract home or authority does not match')
    require(home != Path.home().resolve() or contract['allowLiveHome'] is True,
            'contract does not authorize a live home')
    require(isinstance(contract['version'], str) and SAFE_ID.fullmatch(contract['version']),
            'unsafe instruction release version')
    require(isinstance(contract['expectedTransaction'], str)
            and SAFE_ID.fullmatch(contract['expectedTransaction']), 'unsafe predecessor transaction')
    for field in ('workstationInstructionSha256', 'expectedPreimageSha256'):
        require(isinstance(contract[field], str) and SHA256.fullmatch(contract[field]), 'invalid SHA-256 pin')
    source = pinned_file(args.workstation_repo, contract['workstationCommit'], str(INSTRUCTIONS))
    require(sha256(source) == contract['workstationInstructionSha256'], 'Workstation source hash mismatch')
    catalog_proof(contract, args.catalog_repo)
    transaction = os.environ.get('WORKSTATION_TRANSACTION_ID') or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + str(os.getpid())
    require(SAFE_ID.fullmatch(transaction), 'unsafe instruction transaction ID')
    state = home / '.local/state/engineering-workstation-bootstrap'
    lock = None
    receipt_path = state / 'receipts' / ('activation-' + transaction + '.json')
    release = None
    backup = None
    release_owned = False
    backup_owned = False
    intent_owned = False
    committed = False
    try:
        lock = lock_state(state, transaction)
        state, share, active, pointer, marker, live, prior_receipt = current_state(home, contract)
        prior_receipt_sha = recovery.digest(prior_receipt)
        prior_manifest = Path(recovery.read_json(prior_receipt)['backupManifest'])
        prior_manifest_sha = recovery.digest(prior_manifest)
        managed_before = managed_paths_snapshot(home, prior_manifest)
        release = share / 'versions' / (contract['version'] + '-' + transaction)
        backup = state / 'backups' / transaction
        require(not release.exists() and not release.is_symlink() and not backup.exists()
                and not receipt_path.exists(), 'instruction transaction already exists')
        prior_hash = tree_without_instructions(active)
        release_owned = True
        shutil.copytree(active, release, symlinks=True, copy_function=shutil.copy2)
        candidate = release / INSTRUCTIONS
        candidate.write_bytes(source)
        os.chmod(candidate, stat.S_IMODE((active / INSTRUCTIONS).stat().st_mode))
        require(sha256(candidate.read_bytes()) == contract['workstationInstructionSha256'],
                'staged instruction hash changed')
        require(tree_without_instructions(release) == prior_hash,
                'non-instruction release content changed during staging')
        backup_file = backup / 'files/.codex/AGENTS.md'
        backup_owned = True
        backup_file.parent.mkdir(parents=True)
        backup_file.symlink_to(os.readlink(live))
        bundle = backup / 'recovery'
        (bundle / 'bin').mkdir(parents=True)
        (bundle / 'lib').mkdir()
        for source_path, target_path in (
            (ROOT / 'bin/workstation-instructions', bundle / 'bin/workstation-instructions'),
            (ROOT / 'lib/workstation-instructions.py', bundle / 'lib/workstation-instructions.py'),
            (ROOT / 'lib/workstation-recovery.py', bundle / 'lib/workstation-recovery.py'),
        ):
            shutil.copy2(source_path, target_path)
            require(recovery.digest(source_path) == recovery.digest(target_path),
                    'rollback tool changed during staging')
        manifest = backup / 'manifest.json'
        recovery.write_json(manifest, {'schemaVersion': 1, 'transactionId': transaction,
                                       'targetHome': str(home), 'createdAt': datetime.now(timezone.utc).isoformat(),
                                       'paths': [{'relativePath': '.codex/AGENTS.md', 'originalType': 'symlink',
                                                  'backupRelative': 'files/.codex/AGENTS.md',
                                                  'sha256': None, 'linkTarget': os.readlink(live)}]})
        install_map = backup / 'install-map.tsv'
        install_map.write_text('.codex/AGENTS.md\tlink\tconfig/codex/AGENTS.md\n')
        recovery.seal(home, release, manifest, install_map)
        require(tree_without_instructions(release) == prior_hash, 'staged release changed after sealing')
        receipt = {'schemaVersion': 1, 'transactionId': transaction, 'version': contract['version'],
                   'targetHome': str(home), 'authorityReference': contract['authorityReference'],
                   'releaseDir': str(release), 'backupManifest': str(manifest),
                   'backupManifestSha256': recovery.digest(manifest), 'previousCurrent': str(active),
                   'previousTransaction': contract['expectedTransaction'], 'status': 'applying',
                   'phase': 'prepared', 'recoveryProtocol': 1, 'instructionOnly': True,
                   'preimageSha256': contract['expectedPreimageSha256'],
                   'instructionSha256': contract['workstationInstructionSha256'],
                   'nonInstructionTreeSha256': prior_hash,
                   'managedPathsSha256': snapshot_hash(managed_before),
                   'workstationCommit': contract['workstationCommit'],
                   'catalogCommit': contract['catalogCommit'], 'catalogBlobSha1': contract['catalogBlobSha1'],
                   'previousActivationReceipt': str(prior_receipt),
                   'previousActivationReceiptSha256': prior_receipt_sha,
                   'previousBackupManifestSha256': prior_manifest_sha,
                   'rollbackEntryPoint': str(bundle / 'bin/workstation-instructions'),
                   'rollbackWrapperSha256': recovery.digest(bundle / 'bin/workstation-instructions'),
                   'rollbackModuleSha256': recovery.digest(bundle / 'lib/workstation-instructions.py'),
                   'rollbackHelperSha256': recovery.digest(bundle / 'lib/workstation-recovery.py'),
                   'startedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   'secretValues': False, 'liveHomeActivated': False}
        recovery.write_json(receipt_path, receipt)
        intent_owned = True
        require(current_state(home, contract)[2] == active, 'predecessor changed before publication')
        verify_managed_paths(home, prior_manifest, managed_before)
        checkpoint('after-intent')
        recovery.patch(receipt_path, {'phase': 'publishing-pointer'})
        recovery.atomic_link(str(release), pointer)
        checkpoint('after-pointer')
        recovery.patch(receipt_path, {'phase': 'publishing-marker'})
        recovery.atomic_bytes(marker, (transaction + '\n').encode())
        checkpoint('after-marker')
        require(sha256(live.read_bytes()) == contract['workstationInstructionSha256'],
                'live instruction bytes differ from staged source')
        require(tree_without_instructions(release) == prior_hash,
                'non-instruction release content changed after publication')
        verify_managed_paths(home, prior_manifest, managed_before)
        require(pointer.is_symlink() and os.readlink(pointer) == str(release)
                and marker.read_text().strip() == transaction,
                'managed pointer or transaction changed before receipt')
        require(live.is_symlink() and os.readlink(live) == str(pointer / INSTRUCTIONS)
                and sha256(live.read_bytes()) == contract['workstationInstructionSha256'],
                'live instructions changed before receipt')
        require(tree_without_instructions(release) == prior_hash,
                'unrelated staged release content changed before receipt')
        require(recovery.digest(prior_receipt) == prior_receipt_sha
                and recovery.digest(prior_manifest) == prior_manifest_sha,
                'predecessor rollback evidence changed before receipt')
        checkpoint('before-active')
        recovery.patch(receipt_path, {'status': 'active', 'phase': 'active',
                                      'completedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                      'liveHomeActivated': home == Path.home().resolve()})
        committed = True
        print('PASS: instruction-only transaction ' + transaction)
        print('Receipt: ' + str(receipt_path))
    except ManagedPathDrift as error:
        if intent_owned and not committed:
            recovery.patch(receipt_path, {'status': 'recovery-required', 'phase': 'managed-path-drift',
                                          'recoveryError': str(error)})
            print('REQUIRES_OWNER: managed path drift blocks automatic rollback', file=sys.stderr)
        elif not intent_owned:
            if release_owned and release is not None and release.is_dir() and not release.is_symlink():
                shutil.rmtree(release)
            if backup_owned and backup is not None and backup.is_dir() and not backup.is_symlink():
                shutil.rmtree(backup)
        raise
    except Exception:
        if intent_owned and not committed:
            try:
                recovery.recover(receipt_path, home)
            except Exception as error:
                recovery.patch(receipt_path, {'status': 'recovery-required', 'recoveryError': str(error)})
                print('REQUIRES_OWNER: instruction rollback incomplete; retain receipt and release', file=sys.stderr)
        elif not intent_owned:
            if release_owned and release is not None and release.is_dir() and not release.is_symlink():
                shutil.rmtree(release)
            if backup_owned and backup is not None and backup.is_dir() and not backup.is_symlink():
                shutil.rmtree(backup)
        raise
    finally:
        unlock_state(lock)


def rollback(args):
    home = Path(args.home).resolve(strict=True)
    receipt_path = Path(args.receipt)
    receipt = recovery.read_json(receipt_path)
    require(receipt.get('instructionOnly') is True, 'receipt is not instruction-only')
    require(receipt.get('targetHome') == str(home), 'receipt target home mismatch')
    require(isinstance(receipt.get('transactionId'), str) and SAFE_ID.fullmatch(receipt['transactionId']),
            'invalid rollback transaction')
    state = home / '.local/state/engineering-workstation-bootstrap'
    bundle = state / 'backups' / receipt['transactionId'] / 'recovery'
    require(receipt.get('rollbackEntryPoint') == str(bundle / 'bin/workstation-instructions'),
            'receipt rollback entry point differs')
    for relative, field in (
        ('bin/workstation-instructions', 'rollbackWrapperSha256'),
        ('lib/workstation-instructions.py', 'rollbackModuleSha256'),
        ('lib/workstation-recovery.py', 'rollbackHelperSha256'),
    ):
        require(recovery.digest(bundle / relative) == receipt.get(field), 'stored rollback tool changed')
    require(recovery.digest(ROOT / 'lib/workstation-instructions.py') == receipt['rollbackModuleSha256']
            and recovery.digest(ROOT / 'lib/workstation-recovery.py') == receipt['rollbackHelperSha256'],
            'use the exact receipt-bound rollback tool')
    lock = None
    try:
        lock = lock_state(state, receipt['transactionId'])
        prior_receipt = Path(receipt['previousActivationReceipt'])
        require(recovery.digest(prior_receipt) == receipt['previousActivationReceiptSha256'],
                'predecessor activation receipt changed')
        prior_manifest = Path(recovery.read_json(prior_receipt)['backupManifest'])
        require(recovery.digest(prior_manifest) == receipt['previousBackupManifestSha256'],
                'predecessor backup manifest changed')
        require(snapshot_hash(managed_paths_snapshot(home, prior_manifest)) == receipt['managedPathsSha256'],
                'managed live path drift blocks instruction-only rollback')
        recovery.recover(receipt_path, home)
        print('PASS: instruction-only rollback ' + receipt['transactionId'])
        print('Receipt: ' + recovery.read_json(receipt_path)['rollbackReceipt'])
    finally:
        unlock_state(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    activate = commands.add_parser('install')
    activate.add_argument('--contract', required=True, type=Path)
    activate.add_argument('--home', required=True)
    activate.add_argument('--workstation-repo', required=True, type=Path)
    activate.add_argument('--catalog-repo', required=True, type=Path)
    restore = commands.add_parser('rollback')
    restore.add_argument('--receipt', required=True)
    restore.add_argument('--home', required=True)
    args = parser.parse_args()
    try:
        install(args) if args.command == 'install' else rollback(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('REFUSE: ' + str(error), file=sys.stderr)
        raise SystemExit(64)


if __name__ == '__main__':
    main()
