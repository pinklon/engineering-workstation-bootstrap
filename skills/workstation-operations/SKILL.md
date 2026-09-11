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
