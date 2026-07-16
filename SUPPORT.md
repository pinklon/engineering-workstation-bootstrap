# Support

Engineering Workstation Bootstrap is a community open-source project maintained on a best-effort basis.

## Start here

Before opening an issue:

1. Read the [README](README.md).
2. Run `make help`.
3. Run `make inventory`.
4. Run `make dry-run`.
5. Run `make validate` when working from source.
6. Check existing issues for the same problem.

## Bug reports

Open a GitHub issue for reproducible defects. Include:

- operating system and version
- processor architecture
- bootstrap version or commit
- command run
- expected result
- actual result
- relevant logs with secrets removed
- whether the environment was clean, previously configured, or managed by an employer

Do not paste tokens, private keys, account identifiers, or unredacted authentication output.

## Feature requests

Feature requests should describe the user problem before prescribing the tool. The project is deliberately pluggable; a request framed as “provide capability X” is usually more durable than “install brand Y forever.”

Include:

- the workflow being improved
- affected platforms
- why existing capabilities are insufficient
- security and privilege implications
- whether the tool should be required, recommended, optional, or project-local

## Questions

Use GitHub Discussions when enabled. Until then, use an issue with a clear question label if available.

## Security issues

Do not report vulnerabilities publicly. Follow [SECURITY.md](SECURITY.md).

## Support boundaries

The project can help diagnose its own installation, configuration, packaging, and validation behavior.

It cannot guarantee support for:

- every operating system release
- employer-managed devices with unknown policy restrictions
- every package-manager mirror or network proxy
- modified forks or unofficial packages
- failures inside unrelated tools after they install successfully
- lost credentials or compromised accounts

## Commercial support

No commercial support, warranty, or service-level agreement is currently offered.
