#!/usr/bin/env python3
"""Bind a disposable stage's complete managed file contents to its receipt."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

LEGACY_RECEIPT = b'{"schema_version":1,"mode":"staged","status":"ready","secret_values":false}\n'
DIRECT_FILES = {
    'AGENTS.md',
    'config/codex/AGENTS.md',
    'docs/CAPABILITY-MAP.md',
    'docs/CONNECTOR-FABRIC.md',
    'docs/AGENT-OPERATING-CONTRACT.md',
    'manifests/skills.yaml',
    'manifests/mcp.yaml',
    'manifests/environment.yaml',
    'manifests/connector-capabilities.json',
    'manifests/connector-hosted-template.json',
}
FIXED_DIRECTORIES = {
    'config', 'config/codex', 'docs', 'manifests', 'skills',
    'skills/workstation-operations',
}


def refuse(message):
    raise ValueError(message)


def inventory(source):
    files = set(DIRECT_FILES) | {'config/codex/config.toml'}
    directories = set(FIXED_DIRECTORIES)
    skill_source = source / 'skills/workstation-operations'
    for item in skill_source.rglob('*'):
        relative = str(Path('skills/workstation-operations') / item.relative_to(skill_source))
        (directories if item.is_dir() else files).add(relative)
    return files, directories


def inspect_stage(stage, files, directories, *, receipt_required):
    if not stage.is_dir() or stage.is_symlink():
        refuse('stage is not an owned directory')
    items = list(stage.rglob('*'))
    if any(item.is_symlink() for item in items):
        refuse('managed stage contains a symlink')
    actual = {str(item.relative_to(stage)) for item in items}
    expected = files | directories
    if receipt_required or (stage / 'receipt.json').exists():
        expected.add('receipt.json')
    if actual != expected:
        refuse('managed stage file inventory changed')
    if any(not (stage / name).is_dir() for name in directories):
        refuse('managed stage directory type changed')
    if any(not (stage / name).is_file() for name in files):
        refuse('managed stage file type changed')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rendered_config(stage, source):
    template = (source / 'config/codex/config.toml.template').read_bytes()
    return template.replace(b'{{STAGE_ROOT}}', str(stage).encode())


def expected_legacy_bytes(name, stage, source):
    if name == 'config/codex/config.toml':
        return rendered_config(stage, source)
    return (source / name).read_bytes()


def verify(stage, source):
    files, directories = inventory(source)
    inspect_stage(stage, files, directories, receipt_required=True)
    receipt_path = stage / 'receipt.json'
    raw = receipt_path.read_bytes()
    if raw == LEGACY_RECEIPT:
        # A v1 stage has no hashes. Accept it only if every file still matches
        # the current source, including the path-rendered config.
        for name in files:
            if (stage / name).read_bytes() != expected_legacy_bytes(name, stage, source):
                refuse('legacy managed stage contents changed')
        return
    try:
        receipt = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError('managed stage receipt is unreadable') from exc
    if (set(receipt) != {'schema_version', 'mode', 'status', 'secret_values',
                         'stage_root', 'managed_sha256'} or
        receipt['schema_version'] != 2 or receipt['mode'] != 'staged' or
        receipt['status'] != 'ready' or receipt['secret_values'] is not False or
        receipt['stage_root'] != str(stage)):
        refuse('managed stage receipt identity changed')
    hashes = receipt['managed_sha256']
    if not isinstance(hashes, dict) or set(hashes) != files:
        refuse('managed stage receipt file inventory changed')
    for name, expected in hashes.items():
        if not isinstance(expected, str) or digest(stage / name) != expected:
            refuse('managed stage contents changed: ' + name)


def seal(stage, source):
    files, directories = inventory(source)
    inspect_stage(stage, files, directories, receipt_required=False)
    receipt = {
        'schema_version': 2,
        'mode': 'staged',
        'status': 'ready',
        'secret_values': False,
        'stage_root': str(stage),
        'managed_sha256': {name: digest(stage / name) for name in sorted(files)},
    }
    data = (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode()
    fd, temporary = tempfile.mkstemp(prefix='.receipt-', dir=stage)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, stage / 'receipt.json')
        parent_fd = os.open(stage, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    if len(sys.argv) != 4:
        refuse('usage: staged_workstation_receipt.py {verify|seal|render-config} STAGE SOURCE')
    mode, stage, source = sys.argv[1], Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
    if mode == 'verify':
        verify(stage, source)
    elif mode == 'seal':
        seal(stage, source)
    elif mode == 'render-config':
        (stage / 'config/codex/config.toml').write_bytes(rendered_config(stage, source))
    else:
        refuse('unsupported stage receipt operation')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError) as error:
        print('REFUSE: ' + str(error), file=sys.stderr)
        raise SystemExit(64)
