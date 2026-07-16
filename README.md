# Engineering Workstation Bootstrap

A governed, reproducible, idempotent, secret-free control plane for preparing engineering hosts used with SharePlane, WESS, Codex, GitHub, Cloudflare, and Playwright browser validation.

## New Mac entry point

A clean Mac needs internet access, Terminal, a local administrator account, and browser access for OAuth and MFA.

Because this repository is private, the first bootstrap requires GitHub CLI authentication. Follow `docs/NEW-MACHINE-RUNBOOK.md`, then run:

```bash
cd "$HOME/Developer/engineering-workstation-bootstrap"
./bin/workstation-bootstrap install
```

Routine reconciliation:

```bash
workstation-bootstrap reconcile
workstation-doctor --full
```

## What is automated

- Xcode Command Line Tools detection
- Homebrew installation handoff
- Host dependency installation from `Brewfile`
- Python and Node runtime installation from `mise.toml`
- managed shell, Git, and SSH fragments
- GitHub CLI enrollment and verification
- GitHub SSH key creation and upload when no public key exists
- Cloudflare Wrangler enrollment and verification
- persistent Playwright virtual environment and Chromium cache
- declared repository cloning
- human-readable and JSON readiness receipts

## What remains human-controlled

- macOS administrator approval
- GitHub OAuth, MFA, and access approval
- Cloudflare OAuth, MFA, and access approval
- SSH key passphrase choice
- provider-side privileged approvals
- production deployment authorization

## Security boundary

Never commit tokens, private keys, OAuth stores, Keychain exports, `.env` credentials, Wrangler state, or production secrets. Authentication planes are independently enrolled and validated.

## Commands

```text
workstation-bootstrap install
workstation-bootstrap reconcile
workstation-bootstrap status
workstation-bootstrap dry-run
workstation-doctor --full
github-auth-doctor
cloudflare-auth-doctor
browser-gate-python <python arguments>
```

## Profiles

- `mac-studio`
- `macbook`
- `linux-workstation`
- `remote-codex-host`

The initial executable implementation supports macOS. Other profiles are declared for extension and must fail clearly rather than pretending portability exists through positive thinking.
