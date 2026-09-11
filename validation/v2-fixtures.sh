#!/usr/bin/env bash
set -euo pipefail
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

printf 'Validating v2 manifests...\n'
for file in manifests/{dependencies,environment,mcp,skills}.yaml; do test -s "$file"; done
printf 'Validating skill discovery fixture...\n'
find skills -type f -name SKILL.md | while IFS= read -r f; do test "$(sed -n '1p' "$f")" = '---'; done
test "$(find skills -type f -path '*/layers/*' -name SKILL.md | wc -l | tr -d ' ')" = 0
printf 'Validating instruction gate fixture...\n'
if rg -n 'Await explicit user confirmation|confirm plan|may I proceed' AGENTS.md config/codex/AGENTS.md; then exit 1; fi
rg -q 'without asking for a second routine confirmation' AGENTS.md config/codex/AGENTS.md
printf 'Validating high-risk stop fixture...\n'
if WORKSTATION_STAGE_ROOT="$HOME/not-allowed" bash bin/staged-workstation reconcile >/dev/null 2>&1; then exit 1; fi
printf 'Validating staged reconcile idempotence and secret-free receipt...\n'
WORKSTATION_STAGE_ROOT="$tmp/stage" bash bin/staged-workstation reconcile >/dev/null
first="$(shasum -a 256 "$tmp/stage/receipt.json" | awk '{print $1}')"
WORKSTATION_STAGE_ROOT="$tmp/stage" bash bin/staged-workstation reconcile >/dev/null
test "$first" = "$(shasum -a 256 "$tmp/stage/receipt.json" | awk '{print $1}')"
if rg -n '(sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]+|PRIVATE KEY|TOKEN=)' "$tmp/stage"; then exit 1; fi
printf 'Validating personal utility coverage...\n'
for tool in yt rp cgh lgh execution-packet; do rg -q "  $tool:" manifests/tony-private-profile.example.yaml; done
printf 'Validating Drive candidate identity...\n'
WORKSTATION_DRIVE_ROOT="$tmp/drive" bash bin/staged-workstation package-drive 0.2.0-fixture >/dev/null
candidate="$tmp/drive/Tony Workstation Bootstrap/current"
test -x "$candidate/START_TONY_WORKSTATION_BOOTSTRAP.command"
test "$(awk '{print $1}' "$candidate/checksums.sha256")" = "$(jq -r .sha256 "$candidate/manifest.json")"
printf 'PASS: v2 fixtures\n'
