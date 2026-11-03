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

### Mesh-wide discover-before-build (source candidate)

For new agent tasks across the mesh, consult the [Control Tower mesh discovery
contract](https://github.com/pinklon/shareplane-control-tower/blob/main/docs/operations/mesh-discovery/README.md)
and its bounded five-domain pointer index before creating new capabilities,
services, selectors, or registries. Record a `CAPABILITY_DISCOVERY_V1` reuse,
extend, or new decision in the existing task receipt after checking relevant
canonical sources. No match means bounded further search, not absence.
A pointer is not live health, qualification, or execution authority. This
instruction becomes operational only after the upstream contract is merged
and normal agent startup consumption is separately witnessed under
[Control Tower #1139](https://github.com/pinklon/shareplane-control-tower/issues/1139).

### Hyperion discover-before-build

When an agent task mentions Hyperion, `hyperion-96`, local AI models or
inference, coding harnesses, GPU work, or owner-only readers, read the
[canonical Hyperion capability index](https://github.com/pinklon/shareplane-control-tower/blob/main/docs/operations/hyperion-96/CAPABILITIES.md)
and its linked `CAPABILITIES.json` and exact receipts **before** proposing a
new download, model fallback, harness, benchmark, reader, or service. This
extends the connector lookup above; it does not replace the workstation
connector manifest or create another capability registry.

Resolve historical qualification separately from installed, live-serving,
task-tested, broader-qualified and held states. A merged pointer, a prior
benchmark PASS, a discovered connector, or an old dossier does not prove
current runtime readiness. Read-only controller/lease/host observations must
be timestamped; unavailable observations remain UNKNOWN. Respect existing
GPU custody, protected runtime admission and task-specific authority.
Track actual agent intake consumption under
[Control Tower #1129](https://github.com/pinklon/shareplane-control-tower/issues/1129);
two blind discovery tests do not establish fleet-wide activation.

At task resumption, follow the versioned
`docs/AGENT-OPERATING-CONTRACT.md` lookup chain. Retrieve relevant owner
commitments through an authorized adapter, then reconcile the shared task
checkpoint, current writer lease, exact source, and capability evidence.
Conversation memory is a locator, not the durable task state.

At final handoff, record the task and turn identifiers, the accepted claim and
scope, the actual result or blocker, exact evidence and artifact identities,
and the next actor with the input or decision they need. Mark missing values
unknown; a handoff note does not transfer a writer lease or grant authority.
