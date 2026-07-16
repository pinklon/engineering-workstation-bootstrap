# Authentication Planes

## Local GitHub CLI

Credential store: macOS Keychain through `gh auth login`.

Validation:

```bash
gh auth status --hostname github.com
gh api user
```

## Git transport

Credential store: local SSH private key and SSH agent or Keychain integration.

Validation:

```bash
ssh -T git@github.com
```

GitHub may return process status 1 while printing successful authentication because it does not provide shell access. Diagnostics must parse the success message.

## Connected GitHub application

Credential store and lifecycle are managed by the connected application. Its success does not prove local `gh` or SSH health.

## GitHub Actions

Use workflow `GITHUB_TOKEN`, environment secrets, or a dedicated GitHub App. Do not reuse personal workstation credentials.

## Cloudflare Wrangler

Interactive hosts use `wrangler login`. Headless CI uses a narrowly scoped provider token stored in the approved CI secret boundary. Provider authentication does not authorize production deployment unless the workflow separately grants that authority.

## Prohibited shortcuts

- globally exported broad PATs
- committed tokens or `.env` files
- copied Keychain or OAuth credential stores
- shared SSH private keys without an approved recovery design
- treating one working plane as proof that all planes work
