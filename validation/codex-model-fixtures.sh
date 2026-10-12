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
# Repeated managed releases must never accumulate a second policy banner.
cat > "$t/duplicated.toml" <<'TOML'
# Managed routine-execution posture; high-risk stops remain in AGENTS.md.
model = "gpt-6.1-sol"
# Managed routine-execution posture; high-risk stops remain in AGENTS.md.
model_reasoning_effort = "high"
# Managed routine-execution posture; high-risk stops remain in AGENTS.md.
personality = "pragmatic"
[projects."/private/tmp/legacy-absent"]
trust_level = "trusted"
[mcp_servers.example]
url = "https://example.invalid/mcp"
TOML
bash "$ROOT/bin/render-codex-config" --source "$t/duplicated.toml" --output "$t/cleaned.toml"
bash "$ROOT/bin/render-codex-config" --source "$t/cleaned.toml" --output "$t/cleaned-twice.toml"
cmp "$t/cleaned.toml" "$t/cleaned-twice.toml"
python3 - "$t/duplicated.toml" "$t/cleaned.toml" <<'PY'
import pathlib,sys,tomllib
source,output=(pathlib.Path(p) for p in sys.argv[1:])
before=tomllib.loads(source.read_text()); after=tomllib.loads(output.read_text())
assert output.read_text().count('# Managed routine-execution posture; high-risk stops remain in AGENTS.md.')==1
assert after['model']=='gpt-6.1-sol' and after['model_reasoning_effort']=='high'
assert after['personality']==before['personality']
assert after['projects']==before['projects'] and after['mcp_servers']==before['mcp_servers']
assert after['approval_policy']=='on-request' and after['approvals_reviewer']=='auto_review' and after['sandbox_mode']=='workspace-write'
print('PASS: managed renderer idempotent; config semantics retained')
PY
echo 'PASS: invalid model IDs rejected'
