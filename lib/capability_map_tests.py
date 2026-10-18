"""Offline fresh-context checks for the manifest's route observation."""
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import capability_map as routes


class CapabilityMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = routes.load()
        cls.when = routes.timestamp(
            cls.contract['route_observation']['sources']['cloud-probe-local']['observed_at']
        ) + dt.timedelta(seconds=39)

    def authority(self, task='stdlib-computation', scope='read'):
        return {'approved': True, 'reference': 'fixture-scoped-issue',
                'task_class': task, 'scope': scope, 'target': 'scratch-fixture'}

    def select(self, task='stdlib-computation', scope='read', authority=None, now=None):
        return routes.eligible(self.contract, task_class=task, scope=scope,
                               target='scratch-fixture',
                               authority=authority or self.authority(task, scope),
                               now=now or self.when)

    def test_fresh_context_finds_source_without_review_zip(self):
        with tempfile.TemporaryDirectory() as cwd:
            script = '''
import datetime as dt, importlib.util, json, sys
spec=importlib.util.spec_from_file_location("capability_map", sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
contract=module.load()
found=module.eligible(contract, task_class="stdlib-computation", scope="read",
  target="scratch-fixture", authority={"approved":True,
  "reference":"fixture-scoped-issue", "task_class":"stdlib-computation",
  "scope":"read", "target":"scratch-fixture"},
  now=module.timestamp(contract["route_observation"]["sources"]
    ["cloud-probe-local"]["observed_at"])+dt.timedelta(seconds=39))
print(json.dumps([entry["id"] for entry in found]))
'''
            result = subprocess.run(
                [sys.executable, '-I', '-c', script, str(Path(routes.__file__).resolve())],
                cwd=cwd, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), ['surface.dot-cloud'])

    def test_no_authority_or_wrong_scope_never_selects(self):
        self.assertEqual(routes.eligible(self.contract, task_class='stdlib-computation',
            scope='read', target='scratch-fixture', authority={}, now=self.when), [])
        self.assertEqual(self.select(scope='write'), [])
        self.assertEqual(self.select(scope='admin'), [])
        self.assertEqual(self.select(authority={**self.authority(), 'target': 'other'}), [])

    def test_unknown_discovered_historical_and_indirect_evidence_block(self):
        for task in ['gpu', 'desktop-local', 'fresh-cloud-task', 'repository-read',
                     'device-inventory', 'owner-conversation-read']:
            with self.subTest(task=task):
                self.assertEqual(self.select(task=task), [])
        self.assertEqual(self.select(now=self.when + dt.timedelta(minutes=16)), [])
        self.assertEqual(self.select(now=self.when - dt.timedelta(minutes=2)), [])
        entries = {e['id']: e for e in self.contract['route_observation']['entries']}
        self.assertIn('openai-task-control-plane',
                      set(entries['surface.dot-cloud']['failure_domains']) &
                      set(entries['surface.bootstrap-cloud']['failure_domains']))

    def test_probe_cannot_be_reused_for_unprobed_operation_or_target(self):
        # Predecessor negative control: both task classes are advertised by the
        # row, and its only local receipt is fresh, but it proves scratch only.
        row = self.contract['route_observation']['entries'][0]
        self.assertIn('connector-read', row['task_classes'])
        self.assertIn('portable-source-test', row['task_classes'])
        for task_class, target in [('connector-read', 'unprobed-provider'),
                                   ('portable-source-test', 'unpreflighted-source'),
                                   ('stdlib-computation', 'different-scratch')]:
            with self.subTest(task_class=task_class, target=target):
                self.assertEqual(routes.eligible(self.contract, task_class=task_class,
                    scope='read', target=target,
                    authority={'approved': True, 'reference': 'fixture-scoped-issue',
                               'task_class': task_class, 'scope': 'read', 'target': target},
                    now=self.when), [])
        changed = copy.deepcopy(self.contract)
        changed['route_observation']['sources']['cloud-probe-local']['qualified_target'] = 'different-scratch'
        with self.assertRaises(routes.InvalidMap):
            routes.validate(changed)

    def test_availability_and_capability_expiry_are_independent_fail_closed_gates(self):
        observed = routes.timestamp(
            self.contract['route_observation']['sources']['cloud-probe-local']['observed_at'])
        self.assertEqual([e['id'] for e in self.select(now=observed + dt.timedelta(seconds=300))],
                         ['surface.dot-cloud'])
        for seconds in (301, 899, 901):
            with self.subTest(seconds=seconds):
                self.assertEqual(self.select(now=observed + dt.timedelta(seconds=seconds)), [])
        # A caller cannot make stale capability evidence current by only
        # changing the row's availability timestamp.
        changed = copy.deepcopy(self.contract)
        changed['route_observation']['entries'][0]['availability']['observed_at'] = (
            observed + dt.timedelta(seconds=800)).isoformat()
        self.assertEqual(routes.eligible(changed, task_class='stdlib-computation',
            scope='read', target='scratch-fixture', authority=self.authority(),
            now=observed + dt.timedelta(seconds=899)), [])

    def test_unavailable_unknown_and_contradictory_state_block(self):
        self.assertEqual([e['id'] for e in self.select()], ['surface.dot-cloud'])
        for state in ('UNAVAILABLE', 'unknown', 'degraded', 'historical_success'):
            with self.subTest(state=state):
                changed = copy.deepcopy(self.contract)
                changed['route_observation']['entries'][0]['availability']['state'] = state
                self.assertEqual(routes.eligible(changed, task_class='stdlib-computation',
                    scope='read', target='scratch-fixture', authority=self.authority(),
                    now=self.when), [])
        changed = copy.deepcopy(self.contract)
        changed['route_observation']['sources']['cloud-probe']['availability_state'] = 'UNAVAILABLE'
        self.assertEqual(routes.eligible(changed, task_class='stdlib-computation',
            scope='read', target='scratch-fixture', authority=self.authority(),
            now=self.when), [])

    def test_references_and_generated_view_are_checked(self):
        changed = copy.deepcopy(self.contract)
        changed['route_observation']['entries'][0]['evidence_refs'] = ['nonexistent']
        with self.assertRaises(routes.InvalidMap):
            routes.validate(changed)
        changed = copy.deepcopy(self.contract)
        changed['route_observation']['sources']['cloud-probe-local']['output_sha256'] = '0' * 64
        with self.assertRaises(routes.InvalidMap):
            routes.validate(changed)
        self.assertEqual(routes.VIEW.read_text(), routes.render(self.contract))

    def test_projection_preserves_reviewed_identity_scope_and_safe_context(self):
        projection = self.contract['route_observation']
        self.assertEqual(len(projection['entries']), 18)
        self.assertEqual(len({e['id'] for e in projection['entries']}), 18)
        self.assertTrue(projection['source_review_sha256_verified_by_parent'])
        self.assertFalse(projection['source_review_sha256_verified_locally'])
        self.assertIn('cloud-contract', projection['sources'])
        self.assertEqual(len(projection['sources']['cloud-probe']['original_output_sha256']), 64)
        self.assertIn('conflicting-evidence', projection['freshness_policy']['reprobe_triggers'])
        rows = {e['id']: e for e in projection['entries']}
        self.assertIn('fleet-handoff', rows['connector.github']['evidence_refs'])
        self.assertIn('surface.dot-cloud', rows['surface.mc-cloud']['alternative_route_ids'])
        for row in rows.values():
            self.assertEqual(set(row['scopes']), {'read', 'write', 'admin'})
            self.assertTrue(row['transports'])
            self.assertTrue(row['prerequisites'])
            self.assertIn(row['identity_verification'],
                          {'runtime_observed', 'parent_verified', 'unknown'})
            self.assertTrue(row['operator_admission'])

    def task_state(self):
        task = {'task_id': 'synthetic-task-1', 'result_id': 'synthetic-result-1',
                'task_class': 'stdlib-computation', 'scope': 'read',
                'target': 'scratch-fixture', 'source_head': 'a' * 40,
                'writer_id': 'synthetic-writer', 'idempotency_key': 'synthetic-once'}
        checkpoint = {key: task[key] for key in
                      ('task_id', 'result_id', 'source_head', 'writer_id', 'idempotency_key')}
        checkpoint.update(state='active', effect_committed=False, fencing_epoch=7)
        commitment = {'task_id': task['task_id'], 'result_id': task['result_id'],
                      'task_class': task['task_class'], 'scope': task['scope'],
                      'target': task['target'], 'approved': True,
                      'retrieval': 'authorized_adapter', 'receipt_sha256': 'b' * 64,
                      'retrieved_at': self.when.isoformat(),
                      'authority_reference': 'synthetic-owner-commitment'}
        lease = {'task_id': task['task_id'], 'holder': task['writer_id'],
                 'fencing_epoch': 7,
                 'expires_at': (self.when + dt.timedelta(minutes=5)).isoformat()}
        return task, checkpoint, commitment, lease

    def test_resume_requires_current_owner_checkpoint_and_exact_commitment(self):
        task, checkpoint, commitment, lease = self.task_state()
        def candidates(t=task, c=checkpoint, a=commitment, l=lease, now=None):
            return routes.resume_candidates(self.contract, task=t, checkpoint=c,
                commitment=a, lease=l, now=now or self.when)
        self.assertEqual([r['id'] for r in candidates()], ['surface.dot-cloud'])
        self.assertEqual(candidates(l={**lease, 'holder': 'duplicate-writer'}), [])
        self.assertEqual(candidates(c={**checkpoint, 'fencing_epoch': 6}), [])
        self.assertEqual(candidates(c={**checkpoint, 'effect_committed': True}), [])
        self.assertEqual(candidates(a={**commitment, 'retrieval': 'chat-memory'}), [])
        self.assertEqual(candidates(a={**commitment, 'approved': False}), [])
        self.assertEqual(candidates(a={**commitment, 'retrieved_at': '2026-01-01T00:00:00Z'}), [])
        self.assertEqual(candidates(t={**task, 'scope': 'write'}), [])
        self.assertEqual(candidates(now=self.when + dt.timedelta(minutes=16)), [])

    def test_fresh_agent_lookup_chain_and_synthetic_resume(self):
        with tempfile.TemporaryDirectory() as cwd:
            script = '''
import datetime as dt, importlib.util, json, pathlib, sys
root=pathlib.Path(sys.argv[1])
agents=(root/"AGENTS.md").read_text()
assert "docs/AGENT-OPERATING-CONTRACT.md" in agents
assert "manifests/connector-capabilities.json" in agents
operating=(root/"docs/AGENT-OPERATING-CONTRACT.md").read_text()
assert "route_observation" in operating and "fencing" in operating
spec=importlib.util.spec_from_file_location("capability_map",root/"lib/capability_map.py")
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
contract=module.load(root/"manifests/connector-capabilities.json")
when=module.timestamp(contract["route_observation"]["sources"]
  ["cloud-probe-local"]["observed_at"])+dt.timedelta(seconds=39)
task={"task_id":"synthetic-task-1","result_id":"synthetic-result-1",
 "task_class":"stdlib-computation","scope":"read","target":"scratch-fixture",
 "source_head":"a"*40,"writer_id":"synthetic-writer","idempotency_key":"synthetic-once"}
checkpoint={key:task[key] for key in
 ("task_id","result_id","source_head","writer_id","idempotency_key")}
checkpoint.update(state="active",effect_committed=False,fencing_epoch=7)
commitment={"task_id":task["task_id"],"result_id":task["result_id"],
 "task_class":task["task_class"],"scope":task["scope"],"target":task["target"],
 "approved":True,"retrieval":"authorized_adapter","receipt_sha256":"b"*64,
 "retrieved_at":when.isoformat(),"authority_reference":"synthetic-owner-commitment"}
lease={"task_id":task["task_id"],"holder":task["writer_id"],"fencing_epoch":7,
 "expires_at":(when+dt.timedelta(minutes=5)).isoformat()}
found=module.resume_candidates(contract,task=task,checkpoint=checkpoint,
 commitment=commitment,lease=lease,now=when)
print(json.dumps([row["id"] for row in found]))
'''
            result = subprocess.run(
                [sys.executable, '-I', '-c', script, str(routes.ROOT)],
                cwd=cwd, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), ['surface.dot-cloud'])


if __name__ == '__main__':
    unittest.main()
