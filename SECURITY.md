# Security Policy

Engineering Workstation Bootstrap installs tools, changes host configuration, and guides authentication. Security reports deserve a private path and a precise response.

## Supported versions

Until the first stable release, only the latest commit on the default branch is supported for security fixes.

After stable releases begin, this file will list supported release lines explicitly.

| Version | Supported |
|---|---|
| Latest default branch | Yes |
| Older development snapshots | No |
| Unreleased forks or modified packages | Best effort only |

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability.

Use GitHub's private vulnerability reporting feature for this repository when available:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Provide the details requested below.

If private vulnerability reporting is not available, contact the maintainer through the private contact method listed on the maintainer's GitHub profile. Do not include working credentials, private keys, access tokens, or sensitive production data in an unencrypted message.

## What to include

A useful report includes:

- affected version or commit
- affected operating system and architecture
- affected command or script
- clear reproduction steps
- expected and observed behavior
- potential impact
- whether privileges, credentials, or network access are required
- logs with secrets removed
- a suggested mitigation, when known

## High-priority security areas

Reports are especially valuable when they involve:

- credential or token exposure
- unsafe handling of private keys
- command injection
- arbitrary code execution
- privilege escalation
- unsafe package download or verification
- dependency substitution
- destructive configuration replacement
- secrets written to logs, receipts, archives, or source control
- bypass of authentication or approval boundaries
- untrusted pull request code receiving elevated credentials
- release artifact tampering

## Response targets

This is a small open-source project, not a staffed security operations center pretending to be awake in every time zone.

The maintainer will aim to:

- acknowledge a valid report within 5 business days
- provide an initial assessment within 10 business days
- coordinate remediation and disclosure based on severity and complexity

These are targets, not contractual service levels.

## Disclosure

Please allow reasonable time to investigate and correct a vulnerability before public disclosure. When appropriate, the project will publish a security advisory, affected versions, mitigation steps, and credit for the reporter unless anonymity is requested.

## Security design principles

The project must:

- store no user secrets in the repository or release packages
- keep humans involved for authentication and privileged approval
- use narrowly scoped credentials in automation
- verify downloaded artifacts where practical
- avoid replacing user-owned configuration wholesale
- separate optional provider integrations from core workstation readiness
- keep receipts free of secrets
- test installation behavior in clean environments

## Out of scope

The following are normally out of scope unless they demonstrate a defect in this project:

- vulnerabilities in an upstream tool with no project-specific exposure
- unsupported operating systems
- modified third-party packages
- compromised user accounts or machines
- social engineering
- denial-of-service claims requiring unrealistic local access
