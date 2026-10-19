#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
tmp="$(cd "$tmp" && pwd -P)"
profile_tmp="$(mktemp -d /tmp/review-agent-profile-fixture.XXXXXX)"
trap 'rm -rf "$tmp" "$profile_tmp"' EXIT
home="$tmp/home"
mkdir -p "$home/.codex/skills/.system/review-agent/agents"
printf '%s\n' 'model = "fixture-model"' > "$home/.codex/config.toml"
printf '%s\n' '# fixture shell' > "$home/.zshrc"
printf '%s\n' '---' 'name: review-agent' 'description: fixture built-in' '---' \
  > "$home/.codex/skills/.system/review-agent/SKILL.md"
printf '%s\n' 'fixture support' > "$home/.codex/skills/.system/review-agent/agents/openai.yaml"

fingerprint="$(python3 "$root/lib/workstation-recovery.py" fingerprint "$home/.codex/skills/.system/review-agent")"
jq -n --arg home "$home" --argjson fingerprint "$fingerprint" \
  '{schemaVersion:1,activationAuthorized:true,allowLiveHome:false,
    authorityReference:"fixture:catalog-bridge",targetHome:$home,
    version:"fixture-review-agent",manageSkillRoots:true,
    codexSystemSkills:[{name:"review-agent",classification:"openai-builtin",
      action:"preserve",evidenceReference:"fixture:fingerprint",
      authorityReference:"fixture:owner",fingerprint:$fingerprint}]}' \
  > "$tmp/base-contract.json"

# Only the exact owner-bound, preserved built-in is eligible. Reject invalid
# requests before a release, receipt, or current pointer exists.
jq '.codexSystemCatalogBridge="skill-creator"' "$tmp/base-contract.json" > "$tmp/bad-name.json"
if WORKSTATION_TRANSACTION_ID=bad-name bash "$root/bin/workstation-activate" \
  --activation-contract "$tmp/bad-name.json" --home "$home" > "$tmp/bad-name.log" 2>&1; then exit 1; fi
if ! rg -q 'unsupported Codex .system catalog bridge' "$tmp/bad-name.log"; then
  cat "$tmp/bad-name.log" >&2
  exit 1
fi
jq '.codexSystemCatalogBridge="review-agent" | .codexSystemSkills[0].classification="owner-managed"' \
  "$tmp/base-contract.json" > "$tmp/bad-classification.json"
if WORKSTATION_TRANSACTION_ID=bad-classification bash "$root/bin/workstation-activate" \
  --activation-contract "$tmp/bad-classification.json" --home "$home" > "$tmp/bad-classification.log" 2>&1; then exit 1; fi
rg -q 'review-agent catalog bridge requires a preserved classified built-in' "$tmp/bad-classification.log"
test ! -e "$home/.local/share/engineering-workstation-bootstrap/current"

printf '%s\n' '---' 'name: another-reviewer' 'description: fixture built-in' '---' \
  > "$home/.codex/skills/.system/review-agent/SKILL.md"
wrong_name_fingerprint="$(python3 "$root/lib/workstation-recovery.py" fingerprint "$home/.codex/skills/.system/review-agent")"
jq --argjson fingerprint "$wrong_name_fingerprint" \
  '.codexSystemCatalogBridge="review-agent" | .codexSystemSkills[0].fingerprint=$fingerprint' \
  "$tmp/base-contract.json" > "$tmp/bad-declared-name.json"
if WORKSTATION_TRANSACTION_ID=bad-declared-name bash "$root/bin/workstation-activate" \
  --activation-contract "$tmp/bad-declared-name.json" --home "$home" > "$tmp/bad-declared-name.log" 2>&1; then exit 1; fi
rg -q 'review-agent catalog bridge package declares another name' "$tmp/bad-declared-name.log"
printf '%s\n' '---' 'name: review-agent' 'description: fixture built-in' '---' \
  > "$home/.codex/skills/.system/review-agent/SKILL.md"
test ! -e "$home/.local/share/engineering-workstation-bootstrap/current"

# The default does not add a wrapper. The opt-in stages one wrapper pointing
# to the exact classified .system copy, without another package copy.
WORKSTATION_TRANSACTION_ID=no-bridge bash "$root/bin/workstation-activate" \
  --activation-contract "$tmp/base-contract.json" --home "$home" > "$tmp/no-bridge.log"
test ! -e "$home/.codex/skills/review-agent"
bash "$root/bin/workstation-rollback" \
  --receipt "$home/.local/state/engineering-workstation-bootstrap/receipts/activation-no-bridge.json" \
  --home "$home" > /dev/null

jq '.codexSystemCatalogBridge="review-agent"' "$tmp/base-contract.json" > "$tmp/bridge-contract.json"
WORKSTATION_TRANSACTION_ID=with-bridge bash "$root/bin/workstation-activate" \
  --activation-contract "$tmp/bridge-contract.json" --home "$home" > "$tmp/with-bridge.log"
release="$(cd "$home/.local/share/engineering-workstation-bootstrap/current" && pwd -P)"
test -f "$home/.codex/skills/review-agent/SKILL.md"
test -f "$home/.codex/skills/.system/review-agent/SKILL.md"
test ! -e "$release/skill-library/review-agent"
rg -Fq "$release/codex-skills/.system/review-agent/SKILL.md" \
  "$home/.codex/skills/review-agent/SKILL.md"
cmp "$home/.codex/skills/.system/review-agent/SKILL.md" \
  "$release/codex-skills/.system/review-agent/SKILL.md"
HOME="$home" bash "$root/bin/workstation-private-profile" inventory \
  --output "$profile_tmp/next.json" > /dev/null
test "$(jq '[.skills[]? | select(.name=="review-agent")] | length' "$profile_tmp/next.json")" = 0
test ! -e "$profile_tmp/next.assets/skills/review-agent"
test "$(jq -r .status "$home/.local/state/engineering-workstation-bootstrap/receipts/activation-with-bridge.json")" = active

bash "$root/bin/workstation-rollback" \
  --receipt "$home/.local/state/engineering-workstation-bootstrap/receipts/activation-with-bridge.json" \
  --home "$home" > /dev/null
test ! -e "$home/.codex/skills/review-agent"
test -f "$home/.codex/skills/.system/review-agent/SKILL.md"
test "$(jq -r .restoredAllManagedPaths "$home/.local/state/engineering-workstation-bootstrap/receipts/rollback-with-bridge.json")" = true
printf 'PASS: review-agent catalog bridge activation, profile inventory, and exact rollback\n'
