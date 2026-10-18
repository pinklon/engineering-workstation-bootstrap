---
name: workstation-operations
description: Operate a staged Engineering Workstation Bootstrap target without activating a live home directory.
---

# Workstation operations

Use the repository manifests as the source of truth. Install only this declared
entry point; `layers/` paths are implementation material and are never discovery
roots. Routine repository work proceeds under the governing task authority.
Stop for credential enrollment, production, destructive migration, or live-home
activation.

For route discovery, read `manifests/connector-capabilities.json#route_observation`
and its generated `docs/CAPABILITY-MAP.md` view. Follow root `AGENTS.md`
for the authority and evidence lookup order. Unknown, indirect, stale or
historical observations cannot authorize execution. The existing task
dispatcher retains task/lease ownership; this skill does not dispatch work.
Follow `docs/AGENT-OPERATING-CONTRACT.md` before resuming a shared task.
