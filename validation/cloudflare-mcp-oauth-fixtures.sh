#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
t="$(mktemp -d)"
trap 'rm -rf "$t"' EXIT
cat > "$t/fake-codex" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
test "$1" = mcp && test "$2" = list && test "$3" = --json
cat <<'JSON'
[
 {"name":"cloudflare-api","enabled":true,"auth_status":"o_auth",
  "transport":{"type":"streamable_http","url":"https://mcp.cloudflare.com/mcp"}},
 {"name":"cloudflare-observability","enabled":true,"auth_status":"o_auth",
  "transport":{"type":"streamable_http","url":"https://observability.mcp.cloudflare.com/mcp"}}
]
JSON
SH
chmod +x "$t/fake-codex"
cat > "$t/startup.log" <<'LOG'
2026-10-10 ERROR cloudflare-api: OAuth refresh token was rejected: invalid_grant
2026-10-10 ERROR cloudflare-observability: connection timed out
2026-10-10 SECRET pretend-token-value-not-for-echo
LOG
bash "$ROOT/bin/workstation-cloudflare-mcp" status --codex "$t/fake-codex" --startup-log "$t/startup.log" --output "$t/receipt.json"
python3 - "$t/receipt.json" <<'PY'
import json,sys,pathlib
p=pathlib.Path(sys.argv[1]);j=json.loads(p.read_text())
assert j['schema']=='ghostmesh-cloudflare-mcp-oauth-diagnostic-v1'
assert j['secret_values'] is False and j['provider_mutation'] is False
assert j['oauth_credential_store_inspected'] is False
assert {x['connector']:x['state'] for x in j['connectors']} == {
 'cloudflare-api':'REAUTH_REQUIRED',
 'cloudflare-observability':'RETRYABLE_PROVIDER_FAILURE',
}
assert 'pretend-token-value' not in p.read_text()
assert p.stat().st_mode & 0o077 == 0
assert j['scope']=='LOG_CLASSIFIED_NOT_AUTH_CANARY'
print('PASS: typed Cloudflare OAuth failure, retryable classification, immutable private receipt')
PY
if bash "$ROOT/bin/workstation-cloudflare-mcp" status --codex "$t/fake-codex" --output "$t/receipt.json" >/dev/null 2>&1; then
  echo 'FAIL: existing receipt overwritten' >&2
  exit 1
fi
bash "$ROOT/bin/workstation-cloudflare-mcp" status --codex "$t/fake-codex" > "$t/unproven.json"
python3 - "$t/unproven.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
assert all(x['state']=='CONFIGURED_AUTH_UNVERIFIED' for x in j['connectors'])
print('PASS: OAuth-capable configuration alone cannot assert authentication')
PY
bash "$ROOT/bin/workstation-cloudflare-mcp" reconnect-help > "$t/help.txt"
grep -Fqx '  codex mcp login cloudflare-api' "$t/help.txt"
grep -Fqx '  codex mcp login cloudflare-observability' "$t/help.txt"
if grep -Ei '(TOKEN|SECRET)=' "$t/receipt.json" >/dev/null; then
  echo 'FAIL: suspected credential values in receipt' >&2
  exit 1
fi
echo 'PASS: no automatic OAuth login/logout and exact owner action'
