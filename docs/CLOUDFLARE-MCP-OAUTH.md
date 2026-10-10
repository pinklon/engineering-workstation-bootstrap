# Cloudflare MCP OAuth: managed Mac recovery and drift control

**Canonical scope:** Workstation Bootstrap connector fabric and Issue #18.
These are two separate client-owned OAuth grants:
`cloudflare-api` at `https://mcp.cloudflare.com/mcp`, and
`cloudflare-observability` at `https://observability.mcp.cloudflare.com/mcp`.
The public `cloudflare-docs` connector is not an equivalent authenticated grant.

## Rules

- `codex mcp list` reporting **OAuth** means the transport supports OAuth.
  It does **not** attest that its access or refresh token is currently valid.
- Do not read, export, copy, move, replay, log, or version-control OAuth tokens or
  Keychain entries. Keep credential custody inside Codex; never pass tokens to a
  GhostMesh model, custom refresh daemon, VPS, or hosted environment.
- Access-token expiry should normally be handled by Codex. An expired/revoked
  refresh grant, or a rotating-token concurrency race, can still require fresh
  **owner browser authorization**. No finite OAuth grant can be promised never
  to require reauthorization. The upstream Codex OAuth lifecycle remains under
  active repair (openai/codex#35006).
- Avoid concurrently launching many global Codex sessions that all refresh the
  same Cloudflare OAuth grant. A health failure cannot authorize widening
  Cloudflare account scope, replacing browser OAuth with a long-lived API token,
  bypassing Access, or mutating Workers/Production.
- Missing/unauthorized Cloudflare API or observability is **DEGRADED** for any
  `ghostmesh-core` or `shareplane-publisher` capability profile requiring it.
  Cloudflare Docs and independently authenticated Wrangler are distinct lanes,
  not evidence that these two grants work.

## Diagnose without touching credentials

```bash
workstation-cloudflare-mcp status
```

The result `CONFIGURED_AUTH_UNVERIFIED` deliberately means **not yet proven**.
When a recent Codex startup *log file* exists, classify only relevant Cloudflare
error lines without copying raw log content into the output:

```bash
workstation-cloudflare-mcp status --startup-log "$HOME/Downloads/recent-codex-startup.log"
```

The optional `--output` writes a sanitized private, immutable 0600 receipt.
`REAUTH_REQUIRED` means a login is needed. `RETRYABLE_PROVIDER_FAILURE`
means preserve the grant and retry after an appropriate delay.
`CLIENT_REGISTRATION_REQUIRED` is a different recovery problem. A missing
error in a log is **not proof** of successful authentication.

## Repair the grants, only with the owner present

In an interactive Mac Terminal, finish existing long-running Codex tasks and
close unnecessary concurrent Codex sessions. With Codex signed in to the
intended ChatGPT account:

```bash
codex mcp login cloudflare-api
codex mcp login cloudflare-observability
```

Approve the Cloudflare browser consent only after confirming the intended
account and scopes. Never paste an OAuth callback or token in chat.

Do **not** run `codex mcp logout` first merely as a troubleshooting ritual:
it discards existing grants and can needlessly invalidate a still usable
credential. Do not automate login from timers or agents, and do not interpret
a successful browser callback as an independently verified read canary.

After login, start a **fresh** Codex CLI/desktop session. Verify the Cloudflare
API search for account metadata and Observability `workers_list` by actual
read-only MCP calls, using exact intended account scope and without worker
mutations. Record per-connector tool success, new-session persistence, and
independent least-privilege/read-only scope evidence. If a running desktop
session still reports old `invalid_grant`, restart that session to adopt the
new credential generation. A current upstream limitation can leave an already
running process with an obsolete in-memory grant after external CLI login.

## Persistent prevention

The canonical Workstation CLI `workstation-cloudflare-mcp` is intentionally
**not an OAuth refresh daemon**. It can be rerun safely as a diagnostic after
Codex updates, new-session failures or provider changes. This makes degraded
state explicit and repairable without a separate credential authority. It does
not manufacture a 'healthy' response from static configuration or silently
disable the affected service.

Upstream reference: https://github.com/openai/codex/issues/35006
