# Tony Workstation Bootstrap v2 (staged profile)

The public repository remains portable. Tony-specific capability names belong in
`manifests/tony-private-profile.example.yaml` or a private overlay outside source
control. The generated target is inert until a later, explicit cutover job copies
it into the effective home directory.

The environment manifest records names, classes, and origins only. Credentials
are enrolled with provider-native flows and are never exported into receipts,
archives, templates, or manifests.

`package-drive` produces the human-launch candidate. `reconcile` without
`WORKSTATION_STAGE_ROOT` is deliberately refused; this repository never silently
writes a home directory. `rollback` removes only a named staged target.
