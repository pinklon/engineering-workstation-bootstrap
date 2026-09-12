# Engineering Workstation Bootstrap

The portability tranche adds isolated installer source staging, executable
distribution-launcher tests, a locked reusable Playwright runtime, and a
[Linux cloud core adapter](docs/CLOUD-SETUP.md). These scripts do not enroll
agent accounts or establish live cloud commissioning. The final publication
secrets/PII/confidentiality gate remains required under issue #9.

I built this because reinstalling and reconfiguring the same development tools on every computer is tedious, inconsistent, and unnecessary.

Engineering Workstation Bootstrap is an open-source, cross-platform project for turning a new or drifted computer into a useful development environment with a small, understandable command surface. It automates everything that can be automated safely, pauses when administrator approval or authentication is required, stores no secrets, and reports exactly what worked and what still needs attention.

## Status

This project is an early release candidate.

- macOS foundation: implemented
- repository validation: passing
- archive packaging: implemented
- disposable-home transactional activation and rollback: implemented
- repeat activation and package reproducibility testing: implemented
- clean physical-machine installation testing: pending
- Windows and Linux implementations: planned
- Codex and Claude Code CLI installation: declared in the macOS baseline
- Local secrets/OCR/metadata tools: declared; complete publication-content gate and PII runtime qualification remain pending

Do not treat the current version as a stable installer until the lifecycle tests are complete.

## The problem

Moving between computers should not mean rebuilding a development environment from memory.

Typical setup work includes:

- finding and installing package managers
- installing Git, language runtimes, browser tools, and command-line utilities
- editing shell and source-control configuration
- authenticating with code hosts and cloud services
- recreating local validation tools
- cloning repositories
- rediscovering the same setup mistakes on every machine

This project replaces that routine with declared dependencies, guided installation, managed configuration, validation, and repeatable repair.

## Design principles

1. Automate everything safe to automate.
2. Keep a human in the loop where security matters.
3. Never store credentials, tokens, private keys, or authentication state in the repository or release package.
4. Preserve user-owned configuration.
5. Use native platform tools rather than pretending every operating system is identical.
6. Keep tools pluggable so they can be added, replaced, deprecated, or removed.
7. Keep application-specific dependencies inside each application repository.
8. Produce clear human output and machine-readable receipts.
9. Test releases on clean systems, not only on mature developer machines.

## Who this is for

- people who work across several computers
- developers who want reproducible setup
- non-developers learning or supporting software development
- independent builders and open-source maintainers
- platform teams that need repeatable workstation setup
- anyone tired of reinstalling the same pile of tools by hand

## What it manages

The project can manage or guide:

- host package installation
- Python and Node.js runtime setup
- shell, Git, and secure-shell configuration fragments
- source-control authentication
- optional cloud-provider authentication
- browser automation and HTML validation
- environment inventory and health checks
- optional repository cloning
- package construction and checksums
- readiness receipts

The default public configuration does not clone the author's private repositories. Repository cloning is optional and user-configurable.

## What remains human-controlled

The installer does not bypass:

- administrator approval
- multi-factor authentication
- browser-based sign-in
- secure-shell key decisions
- credential enrollment
- privileged cloud access
- production deployment approval

## Quick start on macOS

### 1. Install Apple's command-line developer tools

```bash
xcode-select -p >/dev/null 2>&1 || xcode-select --install
```

### 2. Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 3. Install Git and the GitHub command-line client

```bash
brew install git gh jq
```

### 4. Authenticate with GitHub

```bash
gh auth login --hostname github.com --git-protocol ssh --web
gh auth setup-git
```

### 5. Clone this repository

```bash
mkdir -p "$HOME/Developer"
gh repo clone pinklon/engineering-workstation-bootstrap \
  "$HOME/Developer/engineering-workstation-bootstrap"
cd "$HOME/Developer/engineering-workstation-bootstrap"
```

### 6. Preview, create an activation contract, then install

```bash
make dry-run
jq -n --arg home "$(cd "$HOME" && pwd -P)" \
  '{schemaVersion:1,activationAuthorized:true,allowLiveHome:true,
    authorityReference:"owner-issued-local-contract",targetHome:$home,
    version:"0.2.0",manageSkillRoots:false}' > "$HOME/Downloads/workstation-activation.json"
WORKSTATION_ACTIVATION_CONTRACT="$HOME/Downloads/workstation-activation.json" make install
```

Read [the new-machine runbook](docs/NEW-MACHINE-RUNBOOK.md) before using the full installer on an important system.

## Command service

Run:

```bash
make help
```

Primary commands:

```text
make inventory     Show installed and missing capabilities
make dry-run       Preview the bootstrap without changing the host
make validate      Validate repository code, policy, and package output
make doctor        Test workstation readiness
make auth-doctor   Test configured authentication paths
make package       Build a versioned archive and checksum
make private-profile Build a local portable profile and asset bundle
make package-drive Publish only with a checksum-bound contract
make install       Install prerequisites and activate only with a contract
make activate      Apply a prepared release transactionally
make reconcile     Repair a declared disposable staged target
make rollback      Restore every path recorded by an activation receipt
```

The command surface is intentionally small. Users should not need to reverse-engineer shell scripts merely to operate the product, though history suggests software occasionally considers that a feature.

## Pluggable capabilities

The project models capabilities separately from tool brands. For example:

- JavaScript runtime: Node.js today, replaceable later
- package manager: npm, pnpm, Yarn, or another provider
- formatter: Prettier, Biome, or another provider
- container runtime: Docker, Podman, or another provider
- cloud command-line client: enabled only when a profile needs it

See [Pluggability](docs/PLUGGABILITY.md).

## Web-development profile

The web-development guidance covers common modern needs without forcing every tool globally onto the host:

- TypeScript and JavaScript runtimes
- source formatting and linting
- unit and browser testing
- accessibility checks
- local HTML preview
- browser automation
- development containers
- continuous-integration validation

Project-specific versions stay in project lockfiles. See [Web development](docs/WEB-DEVELOPMENT.md).

## Configuration ownership

Managed configuration lives under:

```text
~/.config/engineering-workstation-bootstrap/
~/.local/share/engineering-workstation-bootstrap/
~/.local/state/engineering-workstation-bootstrap/
```

User-owned files receive narrow include or source entries rather than wholesale replacement.
Each activation prepares an immutable version directory, switches a `current`
pointer, records the pre-state, and backs up every managed live path. A failed
post-activation doctor invokes rollback automatically.

## Security boundary

Never commit or package:

- access tokens
- private keys
- authentication caches
- password-manager exports
- environment files containing secrets
- cloud-provider credentials
- production secrets

A healthy login for one service does not prove every other authentication path works. Each service is validated separately.

## Packaging

The current package format is:

```text
engineering-workstation-bootstrap-<version>.tar.gz
engineering-workstation-bootstrap-<version>.tar.gz.sha256
```

Build it with:

```bash
make package VERSION=0.1.0-rc1
```

Future distribution targets include Homebrew, Windows Package Manager, Debian packages, RPM packages, containers, and signed native installers.

## Documentation

- [Product statement](PRODUCT.md)
- [New-machine runbook](docs/NEW-MACHINE-RUNBOOK.md)
- [Command service](docs/COMMAND-SERVICE.md)
- [Authentication boundaries](docs/AUTHENTICATION-PLANES.md)
- [Pluggability](docs/PLUGGABILITY.md)
- [Web-development guidance](docs/WEB-DEVELOPMENT.md)
- [Packaging and distribution](docs/PACKAGING-AND-DISTRIBUTION.md)
- [Transactional workstation v2 profile](docs/TONY-WORKSTATION-V2.md)
- [Coding agents and publication-security tools](docs/AGENT-AND-SECURITY-TOOLS.md)

## Release gates

A stable release requires:

1. validation on an exact source revision
2. package and checksum verification
3. installation on a clean supported system
4. a second run proving repeatability
5. authentication and browser checks
6. upgrade, rollback, and uninstall testing
7. proof that user configuration is preserved
8. documentation that matches observed behavior
9. confirmation that no secrets are captured

## Public-release rule

Examples and defaults must remain general. Personal repositories, private project names, internal acronyms, private service identifiers, and organization-specific configuration do not belong in the public default package.
