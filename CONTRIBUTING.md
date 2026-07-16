# Contributing

Thanks for helping improve Engineering Workstation Bootstrap.

This project exists to make development environment setup repeatable, understandable, and less tedious across computers and operating systems. Contributions should move the project toward that goal without hiding complexity, weakening security, or binding the product permanently to one fashionable tool.

## Before you start

For a small documentation correction, opening a pull request directly is fine.

For a new capability, platform, package format, provider integration, or behavior change, open an issue first. Describe:

- the problem being solved
- the operating systems affected
- the proposed user experience
- security or privilege implications
- alternatives considered
- how the change will be tested on a clean environment

This prevents several people from independently constructing incompatible solutions to the same annoyance, a traditional software-development pastime.

## Development setup

Clone the repository and inspect the available commands:

```bash
git clone https://github.com/pinklon/engineering-workstation-bootstrap.git
cd engineering-workstation-bootstrap
make help
```

Run the non-mutating inventory and validation commands:

```bash
make inventory
make dry-run
make validate
```

Do not run `make install` on a primary workstation while developing an unreviewed change. Use a disposable user account, virtual machine, hosted runner, container, or other clean test environment appropriate to the platform.

## Design principles

Contributions must preserve these principles:

1. Automate everything that is safe to automate.
2. Keep a human in the loop for authentication, administrator approval, secrets, and other security boundaries.
3. Never commit or package credentials, private keys, tokens, OAuth state, or user secrets.
4. Preserve user-owned configuration and make managed boundaries explicit.
5. Prefer capabilities over permanent allegiance to a specific tool.
6. Keep project-specific dependencies in the project that uses them.
7. Use native platform mechanisms where macOS, Windows, and Linux differ.
8. Produce clear human output and machine-readable evidence.
9. Fail with an exact explanation and a practical next step.
10. Test on a clean environment, not only on an accumulated personal workstation.

## Scope boundaries

Host-level tools and configuration belong here when they are broadly useful across projects.

Application frameworks, libraries, linters, test runners, and build tools that require project-specific versioning usually belong in the consuming project and its lockfiles.

A proposed global installation must explain why repository-local installation is insufficient.

## Pull requests

Keep pull requests focused. Include:

- the problem addressed
- the behavior before and after the change
- platforms affected
- files changed
- validation performed
- security implications
- known limitations
- any manual testing still required

Use clear commit messages. The repository uses squash merging, so the pull request title and description should make sense as the permanent history entry.

## Validation requirements

At minimum, run:

```bash
make validate
```

Changes affecting installation, reconciliation, packaging, or configuration must also prove:

- first-run behavior on a clean environment
- second-run idempotence
- preservation of existing user configuration
- useful failure messages
- absence of secrets in logs and receipts
- package contents and checksum correctness when packaging changes

Platform-specific work must be tested on the relevant native platform or an accepted clean hosted environment.

## Shell scripts

Shell changes must pass:

- Bash syntax validation
- ShellCheck
- the repository validation harness

Paste-ready documentation must not:

- change a reader's interactive shell options
- use `exec` in a way that replaces the reader's shell
- include destructive commands without explicit safeguards
- contain fake executable paths presented as ready to run

## Documentation

Documentation is part of the product, not ceremonial debris generated after the code works.

Update relevant guides whenever behavior changes. Commands in documentation must match the actual command service and current platform support.

Use plain language. Define unavoidable acronyms on first use. Avoid references to private projects, internal systems, or assumptions that only make sense on the maintainer's machines.

## Security reports

Do not open a public issue for a suspected vulnerability, leaked secret, unsafe privilege boundary, or credential exposure. Follow [SECURITY.md](SECURITY.md).

## Licensing of contributions

By submitting a contribution, you agree that it may be licensed under the Apache License 2.0 used by this repository.
