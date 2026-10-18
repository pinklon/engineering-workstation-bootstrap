# Repository execution policy

Read this file before changing the repository. A governing issue and its explicit
owner authorization define the task boundary. Once that authority exists, proceed
through ordinary scoped planning, editing, validation, bounded repair, commits,
pushes, and draft pull-request updates without seeking a duplicate confirmation.

Keep public defaults secret-free and cross-platform. Use an isolated branch and
validate deterministically. Stop for a genuinely new authority boundary only:
production/public release, destructive migration, credential creation or wider
permission, DNS/access/repository-settings changes, or an unresolved semantic
contradiction. Never activate a live workstation as part of repository validation.

## Capability lookup for agents

For connector and execution-surface capability claims, start at
`manifests/connector-capabilities.json`, the versioned contract named by
`manifests/mcp.yaml`. Read the generated `docs/CAPABILITY-MAP.md` for a
summary and `docs/CONNECTOR-FABRIC.md` for the contract explanation;
the document is not a second authority. Check a fresh, surface-specific doctor
receipt before relying on a declared route. An absent, stale, or untested receipt
is unknown and cannot authorize a consequential operation. Availability and
authentication do not grant task authority; check the governing issue and the
read, governed-write, or admin boundary separately.

For versioned shared Skills and runtime consumption, follow the canonical
`pinklon/skills` registry and its #323 owner lane. For real hosted Cloud
qualification, follow Workstation #11. This repository's #18 manifest and
doctor own connector declarations and source checks. A shared task dispatcher
must check its existing task/lease authority first, then this map and current
surface receipts; this map does not create a dispatcher or a failover lease.
Do not copy credentials between surfaces or infer a live installation from
this checkout.

At task resumption, follow the versioned
`docs/AGENT-OPERATING-CONTRACT.md` lookup chain. Retrieve relevant owner
commitments through an authorized adapter, then reconcile the shared task
checkpoint, current writer lease, exact source, and capability evidence.
Conversation memory is a locator, not the durable task state.
