# Agent operating contract v1

Authority: [root AGENTS.md](../AGENTS.md) and the governing owner issue.
Capability authority: [connector manifest](../manifests/connector-capabilities.json)
under Workstation #18. This document is an instruction and lookup chain, not a
task registry, lease service, credential store, or substitute for the existing
shared dispatcher. The generated [capability view](CAPABILITY-MAP.md) is a
reading aid.
The offline fresh-context fixture checks these lookup references and a
synthetic checkpoint/lease. It does not prove installed discovery, an
authenticated dispatcher read, atomic lease enforcement or a live consumer.
The existing dispatcher must authenticate the caller, read current state
atomically, and enforce its own lease/fencing/idempotency contract.

## Resume and route lookup

1. Resolve the durable task ID and result ID through the existing shared
   dispatch/task store. Read the latest checkpoint, exact source and artifact
   identity, current writer lease/fencing token and its expiry, reviewer,
   release and execution custodians, and pending output locations. Do not
   reconstruct active state from chat history.
2. Retrieve only relevant owner conversation commitments using an authorized
   conversation adapter. Bind each to its exact conversation reference,
   timestamp, task scope, and recipient. A remembered instruction, private DM
   identifier or summary alone is not a reusable grant. Keep private
   transcript content and scoped credential references out of public source
   and receipts.
3. Apply still-valid bounded approvals already granted for this exact work.
   Do not ask for routine confirmation again. Recheck new security,
   privilege, credential, destructive, production, publication and
   consequential boundaries against the governing authority.
4. Check one active writer and lease/fencing identity before any write. A
   reviewer may inspect without taking the writer slot. An expired or
   conflicting lease blocks mutation until the existing dispatcher resolves
   ownership; do not launch a competing writer.
5. Read `manifests/connector-capabilities.json#route_observation`, then
   relevant canonical connector/profile fields and the latest doctor/host
   receipts. Match exact task class, target, hardware, read/write/admin scope,
   auth custody, dependencies and failure domains. Null, stale, discovered,
   indirect or historical evidence is not a current execution proof. Refresh
   only with the smallest authorized probe.
6. Try supported alternate executors through their existing custodians when
   the preferred route is unavailable. Check shared failure domains and
   current grants independently; a listed alternative is not an automatic
   failover command. Ask Tony to courier files or commands only after
   supported routes are actually exhausted or need his unique authority.
7. Before transfer or retry, preserve task ID, result ID, checkpoint,
   source/input digest, lease epoch and idempotency key in the existing shared
   store. Reject a stale writer and duplicate committed effect. Checkpoint
   ongoing output and resume from that state, not from transcript assumptions.

## Private collaboration communication

Keep the personal owner conversation separate from private task collaboration.
Use one private collaboration thread per bounded task. Its opening record
references the canonical scope, task/result IDs, writer/reviewer/release/
execution custody, current evidence and output checkpoint. A participant
explicitly accepts or declines a requested role, then records a bounded
result or blocker in that same task thread. A channel or thread index helps
people navigate; it is not a dispatcher, lease, grant or evidence of
execution.

Membership and message text never grant infrastructure authority. Resolve
permissions through the governing issue, current grants and existing task
store. Do not mirror personal conversations or secrets into task channels,
repository files or public receipts. Record only available interaction
checkpoints and state coverage gaps when earlier conversation or task history
cannot be retrieved. Durable archive retention and installed consumer
adoption require separate acceptance; a task thread alone proves neither.

## Custody and proof

| Duty | Existing owner |
| --- | --- |
| Capability manifest, connector doctor and managed host source | Workstation #18 |
| Actual Cloud cold/warm task and saved environment | Workstation #11 |
| Versioned Skills binding, consumption and rollback | Skills #323 |
| Task identity, writer lease, fencing, idempotency and checkpoints | Existing Control Tower dispatch ownership (#329/#757) |
| Review | Independent reviewer for the exact source head |
| Release and installation | Designated release/host custodian after separate approval |
| Protected publisher or service execution | Its current task-specific incumbent |

Report CODED, TESTED, REVIEWED, MERGED, INSTALLED and LIVE-CONSUMED
separately. A generated view or fixture test proves source behavior only.
The capability-map PR may be reverted to restore the prior contract; any
future installed release uses its own managed rollback receipt.

## Consumer adoption and rollback packet

| Consumer | Source lookup | Installed/real consumption |
| --- | --- | --- |
| Repository agent reading this AGENTS.md | Candidate in this PR | Offline synthetic test only |
| Managed Mac CLI and native desktop | Source pointer in workstation skill | Unobserved for this map |
| Saved Codex Cloud and Cloud CLI | Same checked-out manifest after source admission | Unobserved; Cloud #11 gate |
| Hyperion and VPS | No install in this tranche | Unobserved; host custody and Skills #323 gates |
| Protected publisher and Mission Control | No writer or executor change | Unobserved; incumbents retained |
| Fresh new repository | Existing profile/manifest digest path | Unobserved after merge |

Rollout sequence: merge the reviewed source only after exact-head checks;
separately stage a managed release with a digest and rollback receipt; have
each designated consumer locate the contract in a fresh context and perform
an authorized harmless task; retain result and checkpoint identities; only
then mark that consumer adopted. Revert this source PR if its route
projection or instructions are wrong. For a later installation, use the
existing `workstation-rollback --receipt` path and preserve its predecessor.
No host install, service mutation or automatic failover occurs in this PR.
