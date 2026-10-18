"""Read-only route projection of the existing connector capability manifest.

The projection is descriptive. A caller must independently establish task
authority and refresh runtime evidence before acting on a selected candidate.
"""
import datetime as dt
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifests/connector-capabilities.json'
VIEW = ROOT / 'docs/CAPABILITY-MAP.md'
OBSERVATIONS = {'tested', 'discovered', 'unknown'}
SCOPES = {'tested', 'parent_verified', 'runtime_observed',
          'tested_local_scratch_only', 'tested_metadata_only',
          'historical_parent_verified', 'unknown'}
DIRECT_EVIDENCE = {'direct_execution', 'direct_connector_read'}


class InvalidMap(ValueError):
    pass


def timestamp(value):
    if not isinstance(value, str):
        raise InvalidMap('missing timestamp')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise InvalidMap('invalid timestamp') from exc
    if parsed.tzinfo is None:
        raise InvalidMap('timestamp needs timezone')
    return parsed.astimezone(dt.timezone.utc)


def load(path=MANIFEST):
    contract = json.loads(Path(path).read_text())
    validate(contract)
    return contract


def validate(contract):
    if contract.get('schema_version') != 1 or contract.get('contract') != 'MESH_CONNECTOR_FABRIC_PARITY_ACTIVE_V1':
        raise InvalidMap('unsupported connector contract')
    projection = contract.get('route_observation')
    if not isinstance(projection, dict) or projection.get('schema_version') != 1:
        raise InvalidMap('missing route observation version')
    if projection.get('status') != 'REVIEW_EVIDENCE_PENDING_SOURCE_RECEIPTS':
        raise InvalidMap('unexpected route observation status')
    if not projection.get('failure_domain_basis'):
        raise InvalidMap('missing failure domain basis')
    policy = projection.get('freshness_policy', {})
    if policy.get('status') != 'PROPOSED_NOT_DEPLOYED' or policy.get('no_monitor_installed') is not True:
        raise InvalidMap('freshness policy overclaimed')
    for key in ('availability_ttl_seconds', 'authenticated_read_ttl_seconds', 'inventory_ttl_seconds'):
        if not isinstance(policy.get(key), int) or policy[key] <= 0:
            raise InvalidMap('invalid freshness interval')
    entries = projection.get('entries')
    if not isinstance(entries, list) or not entries:
        raise InvalidMap('empty route observation')
    ids = [entry.get('id') for entry in entries]
    if any(not isinstance(id, str) or not id for id in ids) or len(ids) != len(set(ids)):
        raise InvalidMap('duplicate or missing route id')
    connector_ids = {connector['id'] for connector in contract['connectors']}
    sources = projection.get('sources', {})
    for entry in entries:
        if entry.get('observation_state') not in OBSERVATIONS:
            raise InvalidMap('invalid observation state')
        if entry.get('canonical_connector_id') is not None and entry['canonical_connector_id'] not in connector_ids:
            raise InvalidMap('unknown canonical connector')
        if set(entry.get('scopes', {})) != {'read', 'write', 'admin'} or any(
            scope not in SCOPES for scope in entry['scopes'].values()
        ):
            raise InvalidMap('invalid scope observation')
        for key in ('task_classes', 'hardware_requirements', 'dependencies', 'failure_domains',
                    'limits', 'alternative_route_ids', 'evidence_refs'):
            if not isinstance(entry.get(key), list):
                raise InvalidMap('missing route field')
        if not set(entry['alternative_route_ids']).issubset(ids):
            raise InvalidMap('unknown alternative route')
        if not entry['evidence_refs'] or not set(entry['evidence_refs']).issubset(sources):
            raise InvalidMap('unknown or missing evidence')
        availability = entry.get('availability', {})
        if not set(availability.get('evidence_refs', [])).issubset(sources):
            raise InvalidMap('unknown availability evidence')
        if availability.get('observed_at') is not None:
            timestamp(availability['observed_at'])
        if entry['observation_state'] == 'tested' and availability.get('observed_at') is None:
            raise InvalidMap('tested route lacks time')
    for source in sources.values():
        if source.get('observed_at') is not None:
            timestamp(source['observed_at'])
        ref = source.get('ref')
        if isinstance(ref, str) and ref.startswith('docs/receipts/'):
            receipt_path = (ROOT / ref).resolve()
            if not receipt_path.is_relative_to(ROOT / 'docs/receipts'):
                raise InvalidMap('evidence path escaped receipt root')
            try:
                receipt = json.loads(receipt_path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise InvalidMap('missing or unreadable local receipt') from exc
            if (receipt.get('kind') != source.get('kind') or
                receipt.get('observed_at') != source.get('observed_at') or
                receipt.get('output_sha256') != source.get('output_sha256') or
                receipt.get('secret_values') is not False):
                raise InvalidMap('local receipt does not match evidence declaration')
    return projection


def eligible(contract, *, task_class, scope, target, authority, hardware=(), now=None):
    """Return candidate rows only; never confer or execute task authority."""
    projection = validate(contract)
    if scope not in {'read', 'write', 'admin'} or not all(
        isinstance(x, str) and x for x in (task_class, target)
    ):
        raise InvalidMap('exact task class, target and scope required')
    if not isinstance(authority, dict) or authority.get('approved') is not True or any(
        authority.get(key) != value for key, value in
        (('task_class', task_class), ('scope', scope), ('target', target))
    ) or not authority.get('reference'):
        return []
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise InvalidMap('clock needs timezone')
    policy = projection['freshness_policy']
    ttl = policy['authenticated_read_ttl_seconds'] if scope == 'read' else policy['availability_ttl_seconds']
    candidates = []
    for entry in projection['entries']:
        if entry['observation_state'] != 'tested' or task_class not in entry['task_classes']:
            continue
        if not set(entry['hardware_requirements']).issubset(hardware):
            continue
        if entry['kind'] in {'metadata', 'service'} or entry['scopes'][scope] != 'tested':
            continue
        observed_at = entry['availability']['observed_at']
        if observed_at is None or not 0 <= (now - timestamp(observed_at)).total_seconds() <= ttl:
            continue
        if not any(
            projection['sources'][ref].get('kind') in DIRECT_EVIDENCE and
            str(projection['sources'][ref].get('ref', '')).startswith('docs/receipts/') and
            projection['sources'][ref].get('observed_at') and
            0 <= (now - timestamp(projection['sources'][ref]['observed_at'])).total_seconds() <= ttl
            for ref in entry['availability']['evidence_refs']
        ):
            continue
        candidates.append(entry)
    return candidates


def resume_candidates(contract, *, task, checkpoint, commitment, lease, now=None):
    """Read-only admission aid for an already-owned task; no lease mutation."""
    validate(contract)
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise InvalidMap('clock needs timezone')
    required = ('task_id', 'result_id', 'task_class', 'scope', 'target',
                'source_head', 'writer_id', 'idempotency_key')
    if not all(isinstance(task.get(key), str) and task[key] for key in required):
        return []
    if not re.fullmatch(r'[0-9a-f]{40}', task['source_head']):
        return []
    if any(checkpoint.get(key) != task[key] for key in
           ('task_id', 'result_id', 'source_head', 'idempotency_key')):
        return []
    if checkpoint.get('state') not in {'active', 'ready'} or checkpoint.get('effect_committed') is not False:
        return []
    if checkpoint.get('writer_id') != task['writer_id']:
        return []
    if lease.get('task_id') != task['task_id'] or lease.get('holder') != task['writer_id']:
        return []
    epoch = lease.get('fencing_epoch')
    if not isinstance(epoch, int) or epoch < 1 or checkpoint.get('fencing_epoch') != epoch:
        return []
    try:
        if timestamp(lease.get('expires_at')) <= now:
            return []
    except InvalidMap:
        return []
    if commitment.get('task_id') != task['task_id'] or commitment.get('result_id') != task['result_id']:
        return []
    if commitment.get('retrieval') != 'authorized_adapter' or not re.fullmatch(
        r'[0-9a-f]{64}', commitment.get('receipt_sha256', '')
    ):
        return []
    if any(commitment.get(key) != task[key] for key in ('task_class', 'scope', 'target')):
        return []
    if commitment.get('approved') is not True or not commitment.get('authority_reference'):
        return []
    try:
        age = (now - timestamp(commitment.get('retrieved_at'))).total_seconds()
    except InvalidMap:
        return []
    if not 0 <= age <= 900:
        return []
    return eligible(contract, task_class=task['task_class'], scope=task['scope'],
                    target=task['target'], hardware=task.get('hardware', []),
                    authority={'approved': True, 'reference': commitment['authority_reference'],
                               'task_class': task['task_class'], 'scope': task['scope'],
                               'target': task['target']}, now=now)


def render(contract):
    projection = validate(contract)
    lines = [
        '# Capability map (generated)',
        '',
        'Generated from `manifests/connector-capabilities.json#route_observation`.',
        'Do not edit this view. The projection is descriptive and its review evidence',
        'is pending source receipts. A candidate route is not a permission grant.',
        '',
        '| Route | Observation | Availability | Read | Write | Admin | Owner |',
        '| --- | --- | --- | --- | --- | --- | --- |',
    ]
    for entry in projection['entries']:
        clean = lambda value: str(value).replace('|', '/').replace('\n', ' ')
        lines.append('| ' + ' | '.join(clean(value) for value in (
            entry['id'], entry['observation_state'], entry['availability']['state'],
            entry['scopes']['read'], entry['scopes']['write'], entry['scopes']['admin'],
            entry['maintenance_owner'])) + ' |')
    lines += [
        '',
        '## Route detail',
        '',
    ]
    for entry in projection['entries']:
        lines += [
            '### ' + entry['id'],
            '',
            '- Task classes: ' + (', '.join(entry['task_classes']) or 'none qualified'),
            '- Hardware: ' + (', '.join(entry['hardware_requirements']) or 'none declared'),
            '- Dependencies: ' + (', '.join(entry['dependencies']) or 'none declared'),
            '- Failure domains (inferred): ' + (', '.join(entry['failure_domains']) or 'none classified'),
            '- Evidence: ' + ', '.join(entry['evidence_refs']),
            '- Limits: ' + '; '.join(entry['limits']),
            '',
        ]
    lines += [
        'Freshness: availability 300 seconds, authenticated read 900 seconds,',
        'inventory 86400 seconds. These intervals are proposed, not an installed',
        'monitor. Null or expired time and indirect evidence block route selection.',
        'Task authority, exact target, current grants and required hardware are',
        'checked separately. Historical success cannot authorize a write or admin action.',
        '',
        'Installed fleet adoption, automatic failover and physical-outage recovery',
        'remain separate, unproven gates. Cloud #11 owns real hosted qualification;',
        'Skills #323 owns versioned skill bindings and actual consumption.',
        '',
    ]
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['validate', 'render', 'check-view'])
    args = parser.parse_args()
    contract = load()
    if args.command == 'render':
        VIEW.write_text(render(contract))
    elif args.command == 'check-view' and VIEW.read_text() != render(contract):
        raise SystemExit('generated capability view is stale')
