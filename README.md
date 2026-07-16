# Engineering Workstation Bootstrap

A governed, reproducible, idempotent, secret-free control plane for preparing engineering hosts used with SharePlane, WESS, Codex, GitHub, Cloudflare, and Playwright browser validation.

This repository turns a new or drifted workstation into a declared, validated engineering host. It automates everything that can be automated safely, pauses for authentication or privileged approval where human control is required, and produces evidence showing what succeeded, what failed, and what must happen next.

## Current maturity

Status: **release candidate under validation**

- macOS implementation: available on the draft implementation branch
- hosted repository validation: required before merge
- clean-host installation rehearsal: pending
- idempotence rehearsal: pending
- release package: implemented, not yet published
- Linux and remote-host profiles: declared, not yet implemented

Do not treat the current draft branch as a production installer until its hosted and clean-host validation gates pass.

## What this solves

Without a control plane, workstation setup becomes a mixture of remembered commands, copied credentials, package drift, undocumented shell edits, and heroic reconstruction from terminal history. This repository replaces that with:

- declared host dependencies
- pinned language runtimes
- managed configuration fragments
- guided provider authentication
- reusable browser-validation tooling
- declarative repository cloning
- machine-readable readiness receipts
- repeatable reconciliation and recovery
- package and release automation

## Supported profiles

| Profile | Status | Intended use |
|---|---|---|
| `mac-studio` | Active implementation | Primary high-capability macOS engineering host |
| `macbook` | Active declaration | Portable macOS engineering host |
| `linux-workstation` | Planned | Linux engineering workstation |
| `remote-codex-host` | Planned | Remote or isolated execution host |

The current executable installation path supports macOS. Unsupported profiles must fail clearly rather than claim portability through optimistic shell scripting.

## Prerequisites for a clean Mac

A new Mac needs only:

- internet access
- Terminal
- a local administrator account
- the administrator password
- browser access for OAuth and MFA

The bootstrap handles or guides the rest.

## Quick start for a new Mac

### 1. Install Xcode Command Line Tools

```bash
xcode-select -p >/dev/null 2>&1 || xcode-select --install
```

Complete the macOS dialog and reopen Terminal when installation finishes.

### 2. Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Apply the shell initialization line printed by Homebrew.

### 3. Install Git and GitHub CLI

```bash
brew install git gh
```

### 4. Authenticate GitHub

```bash
gh auth login --hostname github.com --git-protocol ssh --web
gh auth setup-git
```

Complete browser OAuth and MFA.

### 5. Clone this private repository

```bash
mkdir -p "$HOME/Developer"

gh repo clone pinklon/engineering-workstation-bootstrap \
  "$HOME/Developer/engineering-workstation-bootstrap"

cd "$HOME/Developer/engineering-workstation-bootstrap"
```

### 6. Run the guided bootstrap

```bash
bash bin/workstation-bootstrap install
```

The installer detects existing state, installs missing dependencies, configures managed fragments, guides provider enrollment, configures browser validation, clones declared repositories, and runs the workstation doctor.

For the complete sequence, failure handling, and recovery path, read [`docs/NEW-MACHINE-RUNBOOK.md`](docs/NEW-MACHINE-RUNBOOK.md).

## Existing workstation commands

### Preview without mutation

```bash
workstation-bootstrap dry-run
```

### Install a new workstation

```bash
workstation-bootstrap install
```

### Reconcile drift

```bash
workstation-bootstrap reconcile
```

### Check readiness

```bash
workstation-bootstrap status
workstation-doctor --full
```

### Validate individual planes

```bash
github-auth-doctor
cloudflare-auth-doctor
browser-gate-python -c 'import playwright; print("Playwright import OK")'
```

## What is automated

- Xcode Command Line Tools detection
- Homebrew installation handoff
- host dependency installation from `Brewfile`
- Python and Node runtime installation from `mise.toml`
- managed shell, Git, and SSH fragments
- `~/bin` command wrappers
- GitHub CLI enrollment and verification
- GitHub SSH key creation and registration when needed
- Cloudflare Wrangler enrollment and verification
- persistent Playwright virtual environment
- persistent Chromium browser cache
- declarative repository cloning
- human-readable readiness output
- JSON readiness receipts
- package construction and checksums
- repository validation and secret scanning

## What remains human-controlled

The bootstrap does not bypass security boundaries. Human interaction remains required for:

- macOS administrator approval
- GitHub OAuth, MFA, and access approval
- Cloudflare OAuth, MFA, and access approval
- SSH key passphrase selection
- provider-side privileged approval
- production deployment authorization
- credential rotation or revocation

## Authentication planes

Authentication is deliberately separated:

| Plane | Mechanism | Validation |
|---|---|---|
| Local GitHub CLI | macOS credential store through `gh auth login` | `gh auth status`, `gh api user` |
| Git transport | SSH private key and agent or Keychain | `ssh -T git@github.com` |
| Connected GitHub application | application-managed installation token | validated by the connected application |
| GitHub Actions | workflow token, environment secret, or GitHub App | workflow-specific validation |
| Cloudflare interactive host | Wrangler OAuth | `wrangler whoami` |
| Cloudflare headless automation | narrowly scoped CI secret | workflow-specific validation |

A working connected application does not prove local `gh` or SSH health. A working `gh` login does not prove Cloudflare access. Details are in [`docs/AUTHENTICATION-PLANES.md`](docs/AUTHENTICATION-PLANES.md).

## Configuration ownership

The bootstrap does not blindly overwrite user configuration. Managed content lives under:

```text
~/.config/engineering-workstation-bootstrap/
```

User-owned files receive stable include or source entries:

```text
~/.zshrc
~/.gitconfig
~/.ssh/config
```

Shared browser tooling lives under:

```text
~/.local/share/codex-tools/browser-gate/
```

Readiness receipts live under:

```text
~/.local/state/engineering-workstation-bootstrap/receipts/
```

## Declared repositories

The initial manifest can clone:

- `pinklon/pinklon-shareplane-next`
- `pinklon/wess-service-experience-and-knowledge`
- `pinklon/skills`

Repository declarations are maintained in [`manifests/repositories.txt`](manifests/repositories.txt). Product dependencies remain owned by each product repository. This bootstrap supplies the host platform, not a global dependency casserole.

## Packaging

The v1 distribution format is a deterministic tar archive plus checksum:

```text
engineering-workstation-bootstrap-<version>.tar.gz
engineering-workstation-bootstrap-<version>.tar.gz.sha256
```

Build locally:

```bash
make package VERSION=0.1.0-rc1
```

Verify:

```bash
shasum -a 256 -c \
  dist/engineering-workstation-bootstrap-0.1.0-rc1.tar.gz.sha256
```

A tag-triggered GitHub workflow can publish the archive and checksum as release assets after the release process is authorized. No package is currently published. See [`docs/PACKAGE-INSTALLATION.md`](docs/PACKAGE-INSTALLATION.md).

A signed and notarized macOS `.pkg` is a later distribution tier. It should follow stable install, upgrade, rollback, uninstall, privilege, signing, and notarization contracts rather than wrapping immature assumptions in a handsome box.

## Validation model

Repository validation checks:

- Bash syntax
- ShellCheck findings
- accidental credential material
- executable placeholder paths
- bootstrap dry-run behavior
- deterministic package creation
- package checksum verification
- package contents

Run locally:

```bash
make validate
```

The full workstation doctor validates:

- supported host
- Homebrew
- Git
- GitHub CLI
- Python
- Node
- Wrangler
- managed shell configuration
- GitHub CLI, API, and SSH access
- Cloudflare access
- Playwright import
- Chromium headless launch

## Receipts

Doctor runs create JSON receipts containing:

- generation timestamp
- selected profile
- overall result
- each validation check and status

Receipts provide evidence for troubleshooting, workstation comparison, and future audit or recovery workflows. They must never contain credentials.

## Security boundary

Never commit or package:

- GitHub tokens
- Cloudflare tokens
- OAuth stores
- SSH private keys
- Keychain exports
- `.env` credentials
- Wrangler credential state
- production secrets

Never solve an isolated authentication failure by globally exporting a broad personal access token. Repair the failed plane specifically.

## Failure behavior

The bootstrap is designed to fail with an exact remediation when it cannot proceed. It must not:

- silently skip required dependencies
- terminate the caller's interactive shell
- install into a product repository
- mutate production services
- overwrite user configuration without managed boundaries
- treat one healthy authentication plane as proof that all planes are healthy

## Upgrade, rollback, and recovery

Routine drift repair:

```bash
workstation-bootstrap reconcile
workstation-doctor --full
```

Package-based upgrades must preserve user-owned files and managed state boundaries. Rollback should restore the prior package version and rerun the doctor. Detailed upgrade, rollback, and uninstall contracts remain part of release hardening before a stable package is published.

## Repository structure

```text
.
├── Brewfile
├── Makefile
├── README.md
├── install.sh
├── mise.toml
├── bin/
├── bootstrap/
├── config/
├── docs/
├── manifests/
├── packaging/
├── validation/
└── .github/workflows/
```

## Documentation

- [New machine runbook](docs/NEW-MACHINE-RUNBOOK.md)
- [Authentication planes](docs/AUTHENTICATION-PLANES.md)
- [Package installation](docs/PACKAGE-INSTALLATION.md)
- [Release workflow](docs/RELEASE-WORKFLOW.md)

Additional operational guides should cover architecture, configuration ownership, provider setup, browser validation, testing, troubleshooting, upgrade, rollback, uninstall, and contribution standards before the first stable release.

## Release gates

A stable release requires:

1. exact-head hosted validation passes
2. package build and checksum validation passes
3. clean macOS host installation passes
4. a second reconcile run proves idempotence
5. GitHub, Cloudflare, SSH, and browser doctors pass
6. rollback and uninstall behavior is tested
7. documentation matches actual behavior
8. no credentials or production mutations occur

Until those gates pass, this repository remains a controlled release candidate rather than a magical one-command cure for every workstation humanity has ever misconfigured.
