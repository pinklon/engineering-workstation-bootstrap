#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
t="$(mktemp -d)"
trap 'rm -rf "$t"' EXIT
cat > "$t/source.toml" <<'TOML'
model = "gpt-6-sol"
model_reasoning_effort = "max"
approval_policy = "never"
sandbox_mode = "danger-full-access"
[mcp_servers.fixture]
model = "mcp-specific-setting"
enabled = true
TOML
bash "$ROOT/bin/render-codex-config" --source "$t/source.toml" --output "$t/without.toml"
bash "$ROOT/bin/render-codex-config" --source "$t/source.toml" --output "$t/with.toml" --model-override gpt-6-astra
python3 - "$t/without.toml" "$t/with.toml" <<'PY'
import sys,tomllib,pathlib
before=tomllib.loads(pathlib.Path(sys.argv[1]).read_text())
after=tomllib.loads(pathlib.Path(sys.argv[2]).read_text())
assert before['model']=='gpt-6-sol',before
assert after['model']=='gpt-6-astra',after
assert after['model_reasoning_effort']=='max'
assert after['mcp_servers']==before['mcp_servers']
assert after['approval_policy']=='on-request'
assert after['approvals_reviewer']=='auto_review'
assert after['sandbox_mode']=='workspace-write'
assert pathlib.Path(sys.argv[2]).read_text().count('model = "gpt-6-astra"')==1
print('PASS: managed model pin keeps effort, MCP and policy controls')
PY
if bash "$ROOT/bin/render-codex-config" --source "$t/source.toml" --output "$t/bad.toml" --model-override 'gpt-6-astra"; model = "evil' >/dev/null 2>&1; then
  echo 'FAIL: malformed model override admitted' >&2
  exit 1
fi
if bash "$ROOT/bin/render-codex-config" --source "$t/source.toml" --output "$t/bad.toml" --model-override '../bad' >/dev/null 2>&1; then
  echo 'FAIL: invalid model override admitted' >&2
  exit 1
fi
echo 'PASS: invalid model IDs rejected'
