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
