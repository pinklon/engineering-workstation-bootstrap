# Command Service

The command service is the public operating surface for Engineering Workstation Bootstrap. It exists so users can operate the product without reading shell implementation code or guessing which script to run.

## Design rules

- Commands use consistent verbs across platforms.
- Read-only commands are clearly separated from mutating commands.
- Every mutating command supports a documented preview or dry-run path where practical.
- Commands never require placeholder paths.
- Commands must not alter the caller's interactive shell options.
- Commands must not use `exec` in paste-ready examples.
- Failures identify the exact capability or authentication plane and print a remediation.
- Make targets are convenience aliases, not hidden alternative behavior.

## Primary Make targets

Run `make help` to display the command surface.

| Command | Mutation | Purpose |
|---|---:|---|
| `make help` | No | Show the supported command service |
| `make status` | No | Show repository and bootstrap status |
| `make inventory` | No | Inspect required and recommended host capabilities |
| `make dry-run` | No | Preview the selected bootstrap profile |
| `make validate` | Repository-local | Run syntax, lint, secret, placeholder, dry-run, and package checks |
| `make doctor` | No provider mutation | Validate workstation readiness and emit a receipt |
| `make auth-doctor` | No | Validate GitHub and Cloudflare authentication planes |
| `make package` | Repository-local | Build a versioned archive and checksum under `dist/` |
| `make install` | Yes | Run the guided first-time workstation bootstrap |
| `make reconcile` | Yes | Repair declared workstation drift |

## Variables

### `VERSION`

Controls the release package version.

```bash
make package VERSION=0.1.0-rc1
```

Default: `0.1.0-dev`.

### `WORKSTATION_PROFILE`

Selects the intended host profile.

```bash
make dry-run WORKSTATION_PROFILE=mac-studio
```

Current declared profiles:

- `mac-studio`
- `macbook`
- `linux-workstation`
- `remote-codex-host`

Unsupported execution paths must stop clearly.

## Read-only operating sequence

Use this sequence to inspect an existing host without starting installation:

```bash
make status
make inventory
make dry-run
make auth-doctor
make doctor
```

A doctor can fail because a capability is missing. Failure does not imply that the diagnostic mutated the host.

## Development sequence

```bash
make validate
make package VERSION=0.1.0-rc1
```

Validation is expected to run before a pull request is marked ready. Package creation writes only to the ignored `dist/` directory.

## Installation sequence

```bash
make dry-run
make install
make doctor
```

Installation may invoke package managers, write managed configuration fragments, guide OAuth or SSH enrollment, configure browser tooling, and clone declared repositories. Human approval remains required at security boundaries.

## Reconciliation sequence

```bash
make reconcile
make doctor
```

Reconcile is intended to be idempotent. Two consecutive reconcile runs on an unchanged host should produce no material configuration drift.

## Native command equivalents

Make delegates to the canonical product commands:

```text
make install       -> bash bin/workstation-bootstrap install
make reconcile     -> bash bin/workstation-bootstrap reconcile
make status        -> bash bin/workstation-bootstrap status
make dry-run       -> bash bin/workstation-bootstrap dry-run
make doctor        -> bash bin/workstation-doctor --full
make validate      -> bash validation/validate.sh
make package       -> bash packaging/build-package.sh <version>
```

Platform-specific implementations may use PowerShell or native package tooling later, but command intent and documentation remain consistent.
