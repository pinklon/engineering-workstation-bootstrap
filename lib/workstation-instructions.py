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


def real_directory_identity(path):
    """Bind managed directories without following a replacement symlink."""
    try:
        value = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None
    if not stat.S_ISDIR(value.st_mode):
        raise ManagedPathDrift('managed directory is not real: ' + str(path))
    return value.st_dev, value.st_ino


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


ROLLBACK_TOOLS = ('bin/workstation-instructions', 'lib/workstation-instructions.py',
                  'lib/workstation-recovery.py')


def stage_rollback_tools(bundle, parent_identities):
    staged = {}
    for relative in ROLLBACK_TOOLS:
        source_path, target_path = ROOT / relative, bundle / relative
        parent_identity = parent_identities[target_path.parent]
        identity = recovery.copy_regular_exclusive(source_path, target_path, parent_identity)
        digest = recovery.require_regular_identity(target_path, identity,
                                                   recovery.digest(source_path), parent_identity)
        staged[relative] = identity, digest, parent_identity
    return staged


def verify_rollback_tools(bundle, staged):
    for relative, (identity, digest, parent_identity) in staged.items():
        recovery.require_regular_identity(bundle / relative, identity, digest, parent_identity)


def first_install_inputs(args):
    """Qualify an empty managed footprint before creating any host state."""
    home = Path(args.home).resolve(strict=True)
    contract = recovery.read_json(args.contract)
    required = {'schemaVersion', 'linuxFirstInstallAuthorized', 'allowLiveHome',
                'authorityReference', 'targetHome', 'version', 'workstationCommit',
                'workstationInstructionSha256', 'catalogCommit', 'catalogBlobSha1'}
    require(set(contract) == required and contract['schemaVersion'] == 1
            and contract['linuxFirstInstallAuthorized'] is True,
            'invalid Linux first-install contract')
    require(type(contract['allowLiveHome']) is bool and bool(contract['authorityReference']),
            'first-install authority is incomplete')
    require(contract['targetHome'] == str(home), 'contract targetHome does not match --home')
    require(home != Path.home().resolve() or contract['allowLiveHome'] is True,
            'contract does not authorize a live home')
    require(home != Path.home().resolve() or sys.platform.startswith('linux'),
            'live first-install is limited to Linux homes')
    require(isinstance(contract['version'], str) and SAFE_ID.fullmatch(contract['version']),
            'unsafe first-install release version')
    require(isinstance(contract['workstationInstructionSha256'], str)
            and SHA256.fullmatch(contract['workstationInstructionSha256']),
            'invalid instruction SHA-256 pin')
    source = pinned_file(args.workstation_repo, contract['workstationCommit'], str(INSTRUCTIONS))
    require(sha256(source) == contract['workstationInstructionSha256'],
            'Workstation source hash mismatch')
    catalog_proof(contract, args.catalog_repo)
    first_install_empty(home)
    return home, contract, source


def first_install_empty(home):
    """Existing Codex profile is allowed; any managed footprint is a hold."""
    codex = home / '.codex'
    require(codex.is_dir() and not codex.is_symlink(),
            'Codex profile directory must be an existing real directory')
    for parent in (home / '.local', home / '.local/share', home / '.local/state'):
        if parent.exists() or parent.is_symlink():
            require(parent.is_dir() and not parent.is_symlink(),
                    'managed parent is not a real directory: ' + str(parent))
    managed = (codex / 'AGENTS.md',
               home / '.local/share/engineering-workstation-bootstrap',
               home / '.local/state/engineering-workstation-bootstrap')
    require(all(recovery.fingerprint(path)['type'] == 'absent' for path in managed),
            'partial, damaged, or occupied managed state; first-install held')


def first_install_preflight(args):
    home, contract, source = first_install_inputs(args)
    print(json.dumps({'status': 'FIRST_INSTALL_READY', 'targetHome': str(home),
                      'authorityReference': contract['authorityReference'],
                      'workstationCommit': contract['workstationCommit'],
                      'instructionSha256': sha256(source),
                      'catalogCommit': contract['catalogCommit'],
                      'catalogBlobSha1': contract['catalogBlobSha1'],
                      'managedState': 'absent'}, sort_keys=True))


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
        def ignore_instruction_leaf(directory, names):
            return {INSTRUCTIONS.name} if Path(directory) == active / INSTRUCTIONS.parent \
                and INSTRUCTIONS.name in names else set()

        shutil.copytree(active, release, symlinks=True, copy_function=shutil.copy2,
                        ignore=ignore_instruction_leaf)
        candidate = release / INSTRUCTIONS
        candidate_parent = real_directory_identity(candidate.parent)
        candidate_identity = recovery.write_regular_exclusive(
            candidate, source, stat.S_IMODE((active / INSTRUCTIONS).stat().st_mode),
            candidate_parent)
        recovery.require_regular_identity(candidate, candidate_identity,
                                          contract['workstationInstructionSha256'], candidate_parent)
        require(tree_without_instructions(release) == prior_hash,
                'non-instruction release content changed during staging')
        backup_file = backup / 'files/.codex/AGENTS.md'
        backup_owned = True
        backup_file.parent.mkdir(parents=True)
        backup_file.symlink_to(os.readlink(live))
        bundle = backup / 'recovery'
        (bundle / 'bin').mkdir(parents=True)
        (bundle / 'lib').mkdir()
        bundle_parents = {path: real_directory_identity(path)
                          for path in (bundle / 'bin', bundle / 'lib')}
        rollback_tools = stage_rollback_tools(bundle, bundle_parents)
        manifest = backup / 'manifest.json'
        recovery.write_json(manifest, {'schemaVersion': 1, 'transactionId': transaction,
                                       'targetHome': str(home), 'createdAt': datetime.now(timezone.utc).isoformat(),
                                       'paths': [{'relativePath': '.codex/AGENTS.md', 'originalType': 'symlink',
                                                  'backupRelative': 'files/.codex/AGENTS.md',
                                                  'sha256': None, 'linkTarget': os.readlink(live)}]})
        install_map = backup / 'install-map.tsv'
        install_map.write_text('.codex/AGENTS.md\tlink\tconfig/codex/AGENTS.md\n')
        recovery.seal(home, release, manifest, install_map)
        recovery.require_regular_identity(candidate, candidate_identity,
                                          contract['workstationInstructionSha256'], candidate_parent)
        verify_rollback_tools(bundle, rollback_tools)
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
                   'rollbackWrapperSha256': rollback_tools['bin/workstation-instructions'][1],
                   'rollbackModuleSha256': rollback_tools['lib/workstation-instructions.py'][1],
                   'rollbackHelperSha256': rollback_tools['lib/workstation-recovery.py'][1],
                   'startedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   'secretValues': False, 'liveHomeActivated': False}
        recovery.write_json(receipt_path, receipt)
        intent_owned = True
        recovery.require_regular_identity(candidate, candidate_identity,
                                          contract['workstationInstructionSha256'], candidate_parent)
        verify_rollback_tools(bundle, rollback_tools)
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


def first_install(args):
    home, contract, source = first_install_inputs(args)
    transaction = os.environ.get('WORKSTATION_TRANSACTION_ID') or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + str(os.getpid())
    require(SAFE_ID.fullmatch(transaction), 'unsafe first-install transaction ID')
    state = home / '.local/state/engineering-workstation-bootstrap'
    share = home / '.local/share/engineering-workstation-bootstrap'
    release = share / 'versions' / (contract['version'] + '-' + transaction)
    backup = state / 'backups' / transaction
    receipt_path = state / 'receipts' / ('activation-' + transaction + '.json')
    lock = None
    intent_owned = False
    committed = False
    state_owned = False
    owned_dirs = {}
    parents = [home, home / '.codex', home / '.local', home / '.local/state',
               home / '.local/share', state, share, state / 'receipts',
               state / 'backups', share / 'versions', release, backup]
    identities = {path: real_directory_identity(path) for path in parents}

    def guard():
        for path, expected in identities.items():
            if real_directory_identity(path) != expected:
                raise ManagedPathDrift('managed directory changed during first-install: ' + str(path))

    def matches_owned_path(path):
        try:
            return all(real_directory_identity(parent) == identities[parent]
                       for parent in identities if parent == path or parent in path.parents)
        except ManagedPathDrift:
            return False

    def mkdir_owned(path):
        guard()
        path.mkdir()
        identity = real_directory_identity(path)
        if identity is None:
            raise ManagedPathDrift('created directory changed during first-install: ' + str(path))
        identities[path] = identity
        owned_dirs[path] = identity
        guard()

    def cleanup_owned():
        # Never descend through a replaced parent or remove a directory with
        # contents another writer may have added after our last check.
        for path in sorted(owned_dirs, key=lambda item: len(item.parts), reverse=True):
            if matches_owned_path(path):
                try:
                    path.rmdir()
                except OSError:
                    pass
    try:
        # Both roots must be absent. mkdir with exist_ok=False also rejects a
        # competing first installer before its release can be selected.
        if identities[home / '.local'] is None:
            mkdir_owned(home / '.local')
        if identities[home / '.local/state'] is None:
            mkdir_owned(home / '.local/state')
        if identities[home / '.local/share'] is None:
            mkdir_owned(home / '.local/share')
        mkdir_owned(state)
        state_owned = True
        mkdir_owned(share)
        mkdir_owned(state / 'receipts')
        mkdir_owned(state / 'backups')
        mkdir_owned(share / 'versions')
        guard()
        lock = lock_state(state, transaction)
        identities[lock] = real_directory_identity(lock)
        guard()
        first_install_empty_except_owned(home, state, share, lock)
        candidate = release / INSTRUCTIONS
        mkdir_owned(release)
        mkdir_owned(release / 'config')
        mkdir_owned(release / 'config/codex')
        guard()
        candidate_parent = identities[candidate.parent]
        candidate_identity = recovery.write_regular_exclusive(candidate, source, 0o644,
                                                               candidate_parent)
        recovery.require_regular_identity(candidate, candidate_identity,
                                          contract['workstationInstructionSha256'], candidate_parent)
        mkdir_owned(backup)
        bundle = backup / 'recovery'
        mkdir_owned(bundle)
        mkdir_owned(bundle / 'bin')
        mkdir_owned(bundle / 'lib')
        guard()
        rollback_tools = stage_rollback_tools(bundle, identities)
        manifest = backup / 'manifest.json'
        recovery.write_json(manifest, {'schemaVersion': 1, 'transactionId': transaction,
                                       'targetHome': str(home), 'createdAt': datetime.now(timezone.utc).isoformat(),
                                       'paths': [{'relativePath': '.codex/AGENTS.md', 'originalType': 'absent',
                                                  'backupRelative': 'files/.codex/AGENTS.md',
                                                  'sha256': None, 'linkTarget': None}]})
        install_map = backup / 'install-map.tsv'
        install_map.write_text('.codex/AGENTS.md\tlink\tconfig/codex/AGENTS.md\n')
        guard()
        recovery.seal(home, release, manifest, install_map)
        recovery.require_regular_identity(candidate, candidate_identity,
                                          contract['workstationInstructionSha256'], candidate_parent)
        verify_rollback_tools(bundle, rollback_tools)
        receipt = {'schemaVersion': 1, 'transactionId': transaction, 'version': contract['version'],
                   'targetHome': str(home), 'authorityReference': contract['authorityReference'],
                   'releaseDir': str(release), 'backupManifest': str(manifest),
                   'backupManifestSha256': recovery.digest(manifest), 'previousCurrent': '',
                   'previousTransaction': '', 'status': 'applying', 'phase': 'prepared',
                   'recoveryProtocol': 1, 'instructionOnly': True, 'linuxFirstInstall': True,
                   'preimageType': 'absent', 'instructionSha256': contract['workstationInstructionSha256'],
                   'workstationCommit': contract['workstationCommit'],
                   'catalogCommit': contract['catalogCommit'], 'catalogBlobSha1': contract['catalogBlobSha1'],
                   'rollbackEntryPoint': str(bundle / 'bin/workstation-instructions'),
                   'rollbackWrapperSha256': rollback_tools['bin/workstation-instructions'][1],
                   'rollbackModuleSha256': rollback_tools['lib/workstation-instructions.py'][1],
                   'rollbackHelperSha256': rollback_tools['lib/workstation-recovery.py'][1],
                   'startedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   'secretValues': False, 'liveHomeActivated': False}
        guard()
        recovery.write_json(receipt_path, receipt)
        intent_owned = True
        guard()
        recovery.require_regular_identity(candidate, candidate_identity,
                                          contract['workstationInstructionSha256'], candidate_parent)
        verify_rollback_tools(bundle, rollback_tools)
        first_install_empty_except_owned(home, state, share, lock)
        recovery.load_transaction(receipt_path, home)
        checkpoint('after-intent')
        guard()
        recovery.patch(receipt_path, {'phase': 'publishing-pointer'})
        recovery.atomic_link(str(release), share / 'current')
        checkpoint('after-pointer')
        guard()
        recovery.patch(receipt_path, {'phase': 'publishing-marker'})
        recovery.atomic_bytes(state / 'current-transaction', (transaction + '\n').encode())
        checkpoint('after-marker')
        live = home / '.codex/AGENTS.md'
        guard()
        if not live.parent.is_dir() or live.parent.is_symlink():
            raise ManagedPathDrift('Codex profile directory changed before publication')
        require(recovery.fingerprint(live)['type'] == 'absent',
                'Codex instruction path changed before publication')
        guard()
        recovery.patch(receipt_path, {'phase': 'publishing-instructions',
                                      'pendingPath': '.codex/AGENTS.md'})
        guard()
        live.symlink_to(share / 'current' / INSTRUCTIONS)
        recovery.sync_dir(live.parent)
        guard()
        recovery.patch(receipt_path, {'pendingPath': None, 'phase': 'checking'})
        checkpoint('after-link')
        guard()
        check, manifest_check, state_check, share_check, release_check = recovery.load_transaction(receipt_path, home)
        recovery.custody(check, state_check, share_check, release_check)
        recovery.live_paths(check, manifest_check, home)
        require(sha256(live.read_bytes()) == contract['workstationInstructionSha256'],
                'live instruction bytes differ from source')
        require((share / 'current').is_symlink() and os.readlink(share / 'current') == str(release)
                and (state / 'current-transaction').read_text().strip() == transaction,
                'first-install pointer or marker changed')
        checkpoint('before-active')
        guard()
        recovery.patch(receipt_path, {'status': 'active', 'phase': 'active',
                                      'completedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                      'liveHomeActivated': home == Path.home().resolve()})
        committed = True
        print('PASS: Linux instruction first-install ' + transaction)
        print('Receipt: ' + str(receipt_path))
    except ManagedPathDrift as error:
        if intent_owned and not committed:
            if matches_owned_path(state):
                recovery.patch(receipt_path, {'status': 'recovery-required', 'phase': 'managed-parent-drift',
                                              'recoveryError': str(error)})
            print('REQUIRES_OWNER: managed directory drift blocks automatic rollback', file=sys.stderr)
        raise
    except Exception:
        if intent_owned and not committed:
            try:
                guard()
                recovery.recover(receipt_path, home)
            except Exception as error:
                if matches_owned_path(state):
                    recovery.patch(receipt_path, {'status': 'recovery-required', 'recoveryError': str(error)})
                print('REQUIRES_OWNER: first-install rollback incomplete; retain receipt', file=sys.stderr)
        raise
    finally:
        if lock and matches_owned_path(lock):
            unlock_state(lock)
        if state_owned and not intent_owned:
            cleanup_owned()


def first_install_empty_except_owned(home, state, share, lock):
    if not (home / '.codex').is_dir() or (home / '.codex').is_symlink():
        raise ManagedPathDrift('Codex profile directory changed during first-install')
    require(recovery.fingerprint(home / '.codex/AGENTS.md')['type'] == 'absent',
            'Codex instruction path changed during first-install')
    require(not (share / 'current').exists() and not (share / 'current').is_symlink()
            and not (state / 'current-transaction').exists()
            and not (state / 'current-transaction').is_symlink(),
            'managed pointer or marker appeared during first-install')
    require(lock.is_dir() and not lock.is_symlink(), 'first-install lock was lost')


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
        if receipt.get('linuxFirstInstall') is True:
            require(receipt.get('previousCurrent') == '' and receipt.get('previousTransaction') == ''
                    and receipt.get('preimageType') == 'absent',
                    'first-install receipt has a predecessor')
            _, manifest, _, _, _ = recovery.load_transaction(receipt_path, home)
            require(len(manifest['paths']) == 1 and
                    manifest['paths'][0]['originalFingerprint'] == {'type': 'absent'},
                    'first-install preimage was not absent')
        else:
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
    for name in ('first-install-preflight', 'first-install'):
        first = commands.add_parser(name)
        first.add_argument('--contract', required=True, type=Path)
        first.add_argument('--home', required=True)
        first.add_argument('--workstation-repo', required=True, type=Path)
        first.add_argument('--catalog-repo', required=True, type=Path)
    restore = commands.add_parser('rollback')
    restore.add_argument('--receipt', required=True)
    restore.add_argument('--home', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'install':
            install(args)
        elif args.command == 'first-install-preflight':
            first_install_preflight(args)
        elif args.command == 'first-install':
            first_install(args)
        else:
            rollback(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('REFUSE: ' + str(error), file=sys.stderr)
        raise SystemExit(64)


if __name__ == '__main__':
    main()
