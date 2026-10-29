"""Classify bounded offline Cloudflare observations without executing a probe."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import stat

MAX_BYTES = 65536
CAPABILITIES = ('authentication', 'r2-bucket-list', 'pages-project-list', 'worker-deployments')
FORMATS = ('wrangler-human', 'wrangler-json', 'cloudflare-api-json')
REASONS = ('completed', 'missing-tool', 'timeout', 'output-limit', 'launch-failed')


class InvalidObservation(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidObservation('ambiguous JSON object')
        result[key] = value
    return result


def reject_constant(_value):
    raise InvalidObservation("invalid JSON constant")


def decode(text):
    try:
        return json.loads(text, object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (ValueError, RecursionError) as error:
        raise InvalidObservation('invalid JSON') from error


def read_observations(path):
    # Refuse symlinks/devices/FIFOs rather than letting a supposed input file
    # block or follow a final-component symlink. Only the explicit input is read.
    if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW'):
        raise InvalidObservation('safe file reading unavailable')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_BYTES:
            raise InvalidObservation('input must be a bounded regular file')
        chunks, total = [], 0
        while total <= MAX_BYTES:
            chunk = os.read(fd, MAX_BYTES + 1 - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(fd)
        if total > MAX_BYTES or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise InvalidObservation('input changed or exceeded limit')
        raw = b''.join(chunks)
    finally:
        os.close(fd)
    try:
        data = decode(raw.decode('utf-8'))
    except UnicodeError as error:
        raise InvalidObservation('invalid encoding') from error
    return validate(data), hashlib.sha256(raw).hexdigest()


def validate(data):
    if (type(data) is not dict or type(data.get('schemaVersion')) is not int
            or data['schemaVersion'] != 1 or type(data.get('observations')) is not list
            or len(data['observations']) > len(CAPABILITIES)):
        raise InvalidObservation('invalid envelope')
    seen = set()
    for observation in data['observations']:
        if type(observation) is not dict:
            raise InvalidObservation('invalid observation')
        capability = observation.get('capability')
        if not isinstance(capability, str) or capability not in CAPABILITIES or capability in seen:
            raise InvalidObservation('invalid or repeated capability')
        seen.add(capability)
        if (observation.get('format') not in FORMATS
                or observation.get('reason', 'completed') not in REASONS
                or type(observation.get('exitCode')) is not int
                or not -255 <= observation['exitCode'] <= 255
                or type(observation.get('stdout')) is not str
                or type(observation.get('stderr', '')) is not str):
            raise InvalidObservation('invalid observation fields')
    return data['observations']


def object_list(value):
    return type(value) is list and all(type(item) is dict for item in value)


def reported_state(observation):
    reason = observation.get('reason', 'completed')
    if reason == 'missing-tool':
        return 'missing-tool'
    if reason != 'completed' or observation['format'] == 'wrangler-human':
        return 'unknown'
    try:
        body = decode(observation['stdout'])
    except InvalidObservation:
        return 'unknown'
    capability = observation['capability']
    success = observation['exitCode'] == 0
    if observation['format'] == 'wrangler-json':
        if capability == 'authentication' and type(body) is dict:
            if body.get('loggedIn') is False:
                return 'unauthenticated'
            if body.get('loggedIn') is True and success:
                return 'ready'
        elif capability in ('pages-project-list', 'worker-deployments') and success and object_list(body):
            return 'ready'
        return 'unknown'
    if type(body) is not dict:
        return 'unknown'
    if body.get('success') is False:
        errors = body.get('errors')
        if not object_list(errors) or not errors or any(type(item.get('code')) is not int for item in errors):
            return 'unknown'
        codes = {item['code'] for item in errors}
        if capability == 'r2-bucket-list' and codes == {10042}:
            return 'provider-not-enabled'
        if capability == 'r2-bucket-list' and codes == {10003}:
            return 'insufficient-permission'
        return 'unknown'
    if body.get('success') is not True or not success:
        return 'unknown'
    result = body.get('result')
    if capability == 'r2-bucket-list' and type(result) is dict and object_list(result.get('buckets')):
        return 'ready'
    if capability == 'pages-project-list' and object_list(result):
        return 'ready'
    if capability == 'worker-deployments' and type(result) is dict and object_list(result.get('deployments')):
        return 'ready'
    return 'unknown'


def receipt(observations, digest=None):
    by_capability = {item['capability']: item for item in observations}
    rows = []
    for capability in CAPABILITIES:
        observation = by_capability.get(capability)
        rows.append({'provider': 'cloudflare', 'capability': capability,
                     'state': 'unknown', 'reportedState': reported_state(observation) if observation else 'unknown',
                     'observationSupplied': observation is not None,
                     'evidenceKind': 'unverified-offline-observation' if observation else 'not-probed'})
    return {'schemaVersion': 1, 'secretValues': False,
            'classifiedAt': datetime.now(timezone.utc).isoformat(),
            'mode': 'offline-classification', 'inputSha256': digest,
            'ready': False, 'runtimeReadiness': 'unknown', 'authorityGranted': False,
            'probesExecuted': False, 'credentialDiscoveryPerformed': False,
            'credentialRefreshPerformed': False, 'providerMutationPerformed': False,
            'capabilities': rows,
            'nextAction': 'Use the existing authorized observer and no-refresh contract before qualifying current runtime readiness.'}


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, 'Invalid Cloudflare doctor arguments; use --help.\n')


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument('--input', help='Explicit bounded regular JSON observation file; never a credential store')
    parser.add_argument('--format', choices=('human', 'json'), default='human')
    args = parser.parse_args()
    observations, digest = [], None
    if args.input:
        try:
            observations, digest = read_observations(args.input)
        except (OSError, InvalidObservation):
            parser.exit(2, 'Observation input could not be read or validated safely.\n')
    data = receipt(observations, digest)
    if args.format == 'json':
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print('Cloudflare offline classification; no current runtime probe')
        for row in data['capabilities']:
            print(f"UNKNOWN  {row['capability']} runtime; offline report: {row['reportedState']}")
        print('RESULT: current Cloudflare readiness is UNKNOWN')
        print(data['nextAction'])
    # Offline observations cannot make an auth-doctor invocation return healthy.
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
