# Engineering Workstation Bootstrap

## Why this exists

I use more than one computer, and I do not want to reinstall and reconfigure the same development tools every time I move to another system.

That problem is not unique to me. People work across desktops, laptops, remote machines, containers, and cloud environments. Every system has different package managers, runtime versions, command shells, credential stores, browser tools, and setup history. Rebuilding a useful environment by hand is repetitive, inconsistent, and easy to get wrong.

Engineering Workstation Bootstrap exists to make that routine repeatable.

## Product statement

Engineering Workstation Bootstrap is an open-source, cross-platform setup and validation system for development workstations. A user should be able to obtain the package for a supported platform, inspect what it will do, run one clear command, complete only the security-sensitive approvals, and receive a working environment with a clear readiness report.

The product automates everything safe to automate. It keeps a human in the loop for administrator approval, authentication, multi-factor verification, key management, and privileged service access. It does not store secrets in source control or release packages.

## Product promise

From a supported system, a user should be able to:

1. obtain the appropriate open-source package
2. inspect the planned changes
3. run a small, documented command surface
4. allow automated installation and configuration
5. intervene only when security or privilege requires it
6. receive exact remediation when automation cannot continue
7. validate the resulting environment
8. repair drift later without rebuilding from memory

The target experience is measured in minutes, not an afternoon of browser tabs and terminal archaeology.

## Core principles

### Automate everything safe to automate

Package installation, runtime setup, managed configuration, browser tooling, optional repository cloning, validation, reconciliation, receipts, packaging, and release checks should be mechanical.

### Keep humans where security matters

The product does not bypass administrator approval, multi-factor authentication, browser sign-in, secure-shell key decisions, credential enrollment, privileged provider access, or production authorization.

### Never store secrets

Tokens, private keys, authentication state, credential-store exports, provider secrets, and user environment files containing credentials remain outside the source repository and release packages.

### Be cross-platform without pretending platforms are identical

macOS, Windows, and Linux share product semantics, manifests, validation contracts, and command intent. Each platform uses its own native package management, scripting, credential storage, and configuration mechanisms.

### Keep tools replaceable

The product depends on capabilities rather than permanent allegiance to a particular tool. A runtime, formatter, package manager, container engine, editor extension, cloud client, or browser tool can be added, replaced, deprecated, or removed through declared providers and profiles.

### Make operation understandable

The command service must be small, discoverable, documented, and consistent. Users should not need to read implementation code to preview, install, validate, reconcile, package, or troubleshoot the product.

### Preserve user ownership

The product manages explicit configuration boundaries. It must not replace an entire shell, source-control, secure-shell, editor, or provider configuration merely because overwriting it is easier.

### Produce evidence

Every meaningful run should report what happened and produce machine-readable receipts suitable for troubleshooting, comparison, recovery, and future governance.

### Fail clearly

A failure must identify the broken capability or authentication path and provide the next executable remediation. Generic messages such as “setup failed” are defects.

### Test outside accumulated developer machines

A bootstrap tested only on a mature workstation proves very little. Releases require clean containers, hosted runners, virtual machines, or disposable hosts appropriate to each supported platform.

## Intended users

- people working across multiple computers
- developers who want reproducible setup
- non-developers learning or supporting software development
- independent builders and open-source maintainers
- platform and infrastructure engineers
- teams that need repeatable setup evidence

## Product scope

The product is responsible for:

- host dependency declaration
- runtime installation and version control
- managed host configuration
- authentication guidance and validation
- browser and HTML validation tooling
- optional repository acquisition
- environment inventory and readiness checks
- drift reconciliation
- package construction and release verification
- upgrade, rollback, and uninstall contracts
- complete operating documentation

Application repositories remain responsible for their own dependencies and lockfiles.

## Public defaults

The public package must not contain:

- private repository names
- organization-specific acronyms
- internal service identifiers
- personal infrastructure paths
- company-specific configuration
- credentials or secret material

Personal customization belongs in user-owned manifests or profiles that are excluded from the public defaults.

## Platform direction

The roadmap includes:

- macOS archive, Homebrew, and signed package distribution
- Windows PowerShell, Windows Package Manager configuration, and packaged distribution
- Linux archive, Debian, RPM, container, and development-container distribution
- clean-host validation across macOS, Windows, and Linux
- cloud development-environment support
- a consistent command service across platforms

## Success criteria

The product succeeds when a user can move to a supported clean system and become development-ready through a documented, repeatable routine with minimal manual intervention, no secret leakage, no destructive configuration replacement, and a clear readiness result.
