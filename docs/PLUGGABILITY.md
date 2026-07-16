# Pluggability and Tool Choice

Engineering Workstation Bootstrap does not treat the initial tool list as permanent truth.

The product starts with widely used, well-supported defaults because users need a practical baseline. Those defaults are replaceable. Tools can be added, removed, substituted, scoped to a platform, or demoted from required to optional without rewriting the entire product.

## Why this matters

Developer tooling changes quickly. A tool that is sensible today may become unmaintained, insecure, redundant, too expensive, or simply worse than a newer alternative. Hard-coding every choice into one installer would turn the bootstrap into another brittle environment that users eventually have to escape.

The product therefore separates:

- capability intent
- selected implementation
- platform installation method
- validation method
- configuration ownership
- required, recommended, and optional status

The product depends on capabilities, not brands.

For example, the capability is `shell-static-analysis`. ShellCheck may be the current default provider. A future release can replace or supplement it without changing the meaning of `make validate`.

## Capability model

Each managed capability should declare:

```yaml
id: shell-static-analysis
classification: required
providers:
  macos:
    tool: shellcheck
    installer: homebrew
  linux:
    tool: shellcheck
    installer: native-package-manager
  windows:
    tool: shellcheck
    installer: winget-or-bundle
validation:
  command: shellcheck --version
removal:
  supported: true
```

The exact schema may evolve, but the separation of intent from implementation is mandatory.

## Tool classifications

### Required

The product cannot satisfy its supported contract without the capability.

Examples:

- source control
- package management
- runtime management
- shell validation
- structured-data processing
- provider authentication clients

### Recommended

The capability materially improves the default engineering experience but is not required for baseline operation.

Examples:

- enhanced diff rendering
- fuzzy navigation
- HTML live preview
- local performance tools

### Optional

The capability supports a particular workflow, preference, or advanced use case.

Examples:

- container runtime
- local Kubernetes tooling
- AI model tooling
- platform-specific editors

### Deprecated

The capability or provider remains recognized for migration or removal but should not be installed on new systems.

## Provider selection

A profile may select different providers for the same capability.

Example:

```yaml
capabilities:
  container-runtime:
    provider: docker-desktop
```

Another profile could select:

```yaml
capabilities:
  container-runtime:
    provider: colima
```

The doctor validates the selected provider against the capability contract rather than assuming one tool is universal.

## Add, subtract, and replace

Every managed tool should support a documented lifecycle:

1. declare the capability
2. select a provider
3. install or detect it
4. validate it
5. configure only owned boundaries
6. record evidence
7. upgrade or reconcile it
8. remove it when no longer selected

Removing a tool must not leave hidden shell fragments, stale PATH entries, broken aliases, abandoned credentials, or orphaned configuration unless the product explicitly documents the residue.

## User overrides

Users should be able to override defaults without forking the repository.

The intended model is layered configuration:

```text
product defaults
platform defaults
profile defaults
user overrides
local machine state
```

Higher layers may refine lower layers, but validation must report the effective selection.

## Public contribution model

Public contributors should be able to propose:

- a new capability
- a new provider for an existing capability
- support for another operating system
- a better validation method
- a deprecation or replacement
- a new package format

A tool should not be accepted merely because it is fashionable. It should have a clear capability, maintenance posture, security boundary, installation path, validation contract, and removal path.

## Decision standard

A provider remains in the default stack only while it is useful, maintained, secure enough for its role, scriptable, testable, and simpler than the alternatives.

If a selected tool turns out to be poor, the correct response is to replace it through the capability model, not defend it because it appeared in the first release.
