# Engineering Workstation Bootstrap

## Product statement

Modern engineering work rarely happens on one machine. Developers, architects, operators, and creators move among macOS, Windows, Linux, local workstations, remote hosts, containers, and cloud development environments. Every system arrives with different package managers, runtime versions, shell behavior, credential stores, browser tooling, and provider authentication.

Rebuilding that environment by hand is slow, inconsistent, and error-prone. The usual process depends on remembered commands, copied setup notes, undocumented configuration edits, stale credentials, and hours of rediscovery. The result is dependency drift, fragile automation, avoidable security mistakes, and lost time before useful work can begin.

Engineering Workstation Bootstrap exists to remove that friction.

The product provides a cross-platform, open-source, configuration-as-code approach for turning a new or drifted system into a declared, validated engineering environment. A user should be able to obtain the package for the current platform, run one clear command, complete only the security-sensitive human approvals, and reach a working state with evidence showing exactly what was installed, configured, skipped, or blocked.

## Product promise

From a supported system, a user should be able to:

1. obtain the appropriate open-source package
2. inspect what it will do
3. run a single, understandable entry command
4. allow automated installation and configuration
5. intervene only for security, privilege, OAuth, MFA, or credential approval
6. receive exact remediation when automation cannot continue
7. validate the resulting environment
8. reconcile drift later without rebuilding from memory

The target experience is measured in minutes, not an afternoon of browser tabs and terminal archaeology.

## Core principles

### Automate everything safe to automate

Package installation, runtime setup, configuration fragments, browser tooling, repository cloning, validation, reconciliation, receipts, packaging, and release checks should be mechanical.

### Keep humans where security matters

The product does not bypass administrator approval, MFA, OAuth consent, SSH key decisions, credential enrollment, privileged provider access, or production authorization.

### Never store secrets in the repository

Tokens, private keys, OAuth state, credential-store exports, provider secrets, and user `.env` files are outside the product source and release packages.

### Be cross-platform without pretending the platforms are identical

macOS, Windows, and Linux share product semantics, manifests, validation contracts, and command intent. Each platform uses native package management, scripting, credential stores, and configuration mechanisms.

### Make every operation understandable

The command service must be small, discoverable, documented, and consistent. Users should not need to read implementation code to determine how to preview, install, validate, reconcile, package, or troubleshoot the product.

### Preserve user ownership

The product manages explicit configuration boundaries. It must not seize entire shell, Git, SSH, editor, or provider configuration files merely because rewriting them is easier for the installer.

### Produce evidence

Every meaningful run should report what happened and produce machine-readable receipts suitable for troubleshooting, comparison, recovery, and future governance.

### Fail clearly

A failure must identify the broken capability or authentication plane and provide the next executable remediation. Generic messages such as “setup failed” are defects.

### Test outside accumulated developer machines

A bootstrap tested only on a mature workstation proves very little. Releases require clean containers, hosted runners, virtual machines, or disposable hosts appropriate to each supported platform.

## Intended users

- developers working across multiple operating systems
- independent builders maintaining several machines
- platform and infrastructure engineers
- AI and automation practitioners using local and cloud execution lanes
- open-source maintainers onboarding contributors
- regulated or governed teams that need repeatable setup evidence

## Product scope

The product is responsible for:

- host dependency declaration
- runtime installation and version control
- managed host configuration
- provider authentication guidance and validation
- browser and HTML validation tooling
- declared repository acquisition
- environment inventory and readiness checks
- drift reconciliation
- package construction and release verification
- upgrade, rollback, and uninstall contracts
- complete operating documentation

Product repositories remain responsible for their own application dependencies and lockfiles.

## Platform direction

The product roadmap includes:

- macOS archive, Homebrew, and signed package distribution
- Windows PowerShell, WinGet configuration, and packaged distribution
- Linux archive, Debian, RPM, container, and Dev Container distribution
- clean-host validation across macOS, Windows, and Linux
- a universal Dev Container and Codespaces environment
- a consistent command service across platforms

## Success criteria

The product succeeds when a user can move to a supported clean system and become engineering-ready through a documented, repeatable routine with minimal manual intervention, no secret leakage, no destructive configuration replacement, and a clear readiness result.
