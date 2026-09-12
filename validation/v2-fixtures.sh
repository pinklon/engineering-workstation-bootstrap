#!/usr/bin/env bash
set -euo pipefail

tmp="$(mktemp -d)"
profile_tmp="$(mktemp -d /tmp/workstation-profile-fixture.XXXXXX)"
trap 'rm -rf "$tmp" "$profile_tmp"' EXIT
fixture_home="$tmp/home"
mkdir -p "$fixture_home/.codex/skills/legacy/layers/00" "$fixture_home/.agents/skills" "$fixture_home/bin" "$tmp/source-skill/layers/00"
fixture_home="$(cd "$fixture_home" && pwd -P)"
printf '%s\n' '# user-owned-start' 'export USER_SETTING=preserved' > "$fixture_home/.zshrc"
printf '%s\n' 'model = "fixture-model"' 'approvals_reviewer = "user"' '' '[mcp_servers."supabase-fixture"]' 'url = "https://example.invalid/mcp"' 'bearer_token_env_var = "SUPABASE_ACCESS_TOKEN"' 'enabled = true' > "$fixture_home/.codex/config.toml"
printf '%s\n' '---' 'name: legacy' 'description: fixture' '---' > "$fixture_home/.codex/skills/legacy/SKILL.md"
printf '%s\n' '# invalid internal layer' > "$fixture_home/.codex/skills/legacy/layers/00/SKILL.md"
printf '%s\n' '---' 'name: layered-fixture' 'description: fixture layered skill' '---' '# fixture' > "$tmp/source-skill/SKILL.md"
printf '%s\n' '# invalid internal layer kept outside discovery' > "$tmp/source-skill/layers/00/SKILL.md"
printf '%s\n' '#!/usr/bin/env bash' 'printf "reasonpack fixture\\n"' > "$tmp/reasonpack"
chmod 755 "$tmp/reasonpack"
utility_sha="$(shasum -a 256 "$tmp/reasonpack" | awk '{print $1}')"
mkdir -p "$tmp/private-profile.assets/skills" "$tmp/private-profile.assets/bin"
cp -R "$tmp/source-skill" "$tmp/private-profile.assets/skills/layered-fixture"
cp "$tmp/reasonpack" "$tmp/private-profile.assets/bin/reasonpack"

printf 'Validating private-profile inventory through managed skill-root symlinks...\n'
inventory_home="$tmp/inventory-home"
managed_release="$tmp/managed-release"
mkdir -p "$inventory_home/.codex" "$inventory_home/.agents" \
  "$inventory_home/.local/share/engineering-workstation-bootstrap" \
  "$managed_release/codex-skills/linked-codex" \
  "$managed_release/agent-skills/linked-agent" \
  "$managed_release/skill-library/linked-codex/layers/00" \
  "$managed_release/skill-library/linked-agent"
ln -s "$managed_release" "$inventory_home/.local/share/engineering-workstation-bootstrap/current"
ln -s "$inventory_home/.local/share/engineering-workstation-bootstrap/current/codex-skills" "$inventory_home/.codex/skills"
ln -s "$inventory_home/.local/share/engineering-workstation-bootstrap/current/agent-skills" "$inventory_home/.agents/skills"
printf '%s\n' '---' 'name: linked-codex' 'description: managed entrypoint fixture' '---' \
  '# managed wrapper, not the package' > "$managed_release/codex-skills/linked-codex/SKILL.md"
printf '%s\n' '---' 'name: linked-agent' 'description: managed entrypoint fixture' '---' \
  '# managed wrapper, not the package' > "$managed_release/agent-skills/linked-agent/SKILL.md"
printf '%s\n' '---' 'name: linked-codex' 'description: full package fixture' '---' \
  '# canonical package' > "$managed_release/skill-library/linked-codex/SKILL.md"
printf '%s\n' '# internal layer remains package material' \
  > "$managed_release/skill-library/linked-codex/layers/00/SKILL.md"
printf '%s\n' '---' 'name: linked-agent' 'description: full package fixture' '---' \
  '# canonical package' > "$managed_release/skill-library/linked-agent/SKILL.md"
HOME="$inventory_home" bash bin/workstation-private-profile inventory \
  --output "$profile_tmp/inventoried-profile.json" >/dev/null
test "$(jq '.skills | length' "$profile_tmp/inventoried-profile.json")" = 2
test "$(jq -r '[.skills[].name] | sort | join(",")' "$profile_tmp/inventoried-profile.json")" = 'linked-agent,linked-codex'
test -f "$profile_tmp/inventoried-profile.assets/skills/linked-codex/layers/00/SKILL.md"
cmp "$managed_release/skill-library/linked-codex/SKILL.md" \
  "$profile_tmp/inventoried-profile.assets/skills/linked-codex/SKILL.md"
cmp "$managed_release/skill-library/linked-agent/SKILL.md" \
  "$profile_tmp/inventoried-profile.assets/skills/linked-agent/SKILL.md"

jq -n --arg utilitySha "$utility_sha" \
  '{schemaVersion:1,profile:"fixture-private",secretValues:false,
    shell:{preservePrompt:true,githubRoot:"/fixture/github",functions:["cgh","lgh"]},
    skills:[{name:"layered-fixture",sourceDir:"private-profile.assets/skills/layered-fixture",installRoot:"codex-skills",state:"enabled"}],
    environment:[{name:"SUPABASE_ACCESS_TOKEN",class:"oauth-enrolled",origin:"provider",valueIncluded:false}],
    mcp:[{name:"supabase-fixture",state:"auth-required",startup:"disabled",credentials:"preserve"}],
    utilities:[{name:"reasonpack",source:"private-profile.assets/bin/reasonpack",sha256:$utilitySha,aliases:["yt","rp"],dependencies:[],classification:"canonicalize"}]}' > "$tmp/private-profile.json"
profile_sha="$(shasum -a 256 "$tmp/private-profile.json" | awk '{print $1}')"

write_activation_contract() {
  local version="$1" output="$2"
  jq -n --arg targetHome "$fixture_home" --arg version "$version" --arg profileSha "$profile_sha" \
    '{schemaVersion:1,activationAuthorized:true,allowLiveHome:false,authorityReference:"fixture:activation",
      targetHome:$targetHome,version:$version,privateProfileSha256:$profileSha,manageSkillRoots:true}' > "$output"
}

printf 'Validating manifests and instruction policy...\n'
for file in manifests/{dependencies,environment,managed-paths,mcp,skills}.yaml; do test -s "$file"; done
for file in skills/*/SKILL.md; do test "$(sed -n '1p' "$file")" = '---'; done
if rg -n 'Await explicit user confirmation|confirm plan|may I proceed' AGENTS.md config/codex/AGENTS.md; then exit 1; fi
rg -q 'without asking for a second routine confirmation' AGENTS.md config/codex/AGENTS.md
rg -q 'production/public-release' AGENTS.md config/codex/AGENTS.md

printf 'Validating explicit activation gate...\n'
if bash bin/workstation-activate --home "$fixture_home" --version fixture >/dev/null 2>&1; then exit 1; fi

printf 'Validating transactional activation and pre-state receipt...\n'
write_activation_contract fixture-v1 "$tmp/activation-v1.json"
WORKSTATION_TRANSACTION_ID=fixture-v1 bash bin/workstation-activate \
  --activation-contract "$tmp/activation-v1.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-v1 >/dev/null
activation_one="$fixture_home/.local/state/engineering-workstation-bootstrap/receipts/activation-fixture-v1.json"
test "$(jq -r .status "$activation_one")" = active
test -x "$fixture_home/bin/workstation-toolsets"
for command in workstation-bootstrap browser-gate-python github-auth-doctor cloudflare-auth-doctor; do test -x "$fixture_home/bin/$command"; done
test -f "$fixture_home/.local/share/engineering-workstation-bootstrap/current/runtime/bootstrap/configure-browser-gate.sh"
bash "$fixture_home/.local/share/engineering-workstation-bootstrap/current/runtime/bin/workstation-toolsets" brewfile | cmp - Brewfile
test "$(jq -r '.paths | length' "$(jq -r .backupManifest "$activation_one")")" -ge 10
test "$(grep -Fxc "source \"\$HOME/.config/engineering-workstation-bootstrap/shell.zsh\"" "$fixture_home/.zshrc")" = 1
rg -q '^export USER_SETTING=preserved$' "$fixture_home/.zshrc"
rg -q '^model = "fixture-model"$' "$fixture_home/.codex/config.toml"
test "$(grep -Fxc 'approvals_reviewer = "auto_review"' "$fixture_home/.codex/config.toml")" = 1
rg -q '^bearer_token_env_var = "SUPABASE_ACCESS_TOKEN"$' "$fixture_home/.codex/config.toml"
awk '/^\[mcp_servers\."supabase-fixture"\]/{inside=1;next} /^\[/{inside=0} inside && /^enabled = false$/{found=1} END{exit(found?0:1)}' "$fixture_home/.codex/config.toml"
test -x "$fixture_home/bin/reasonpack"
rg -q '^alias yt=reasonpack$' "$fixture_home/.config/engineering-workstation-bootstrap/aliases.zsh"
rg -q '^alias rp=reasonpack$' "$fixture_home/.config/engineering-workstation-bootstrap/aliases.zsh"
rg -q '^cgh\(\)' "$fixture_home/.config/engineering-workstation-bootstrap/functions.zsh"
rg -q '^lgh\(\)' "$fixture_home/.config/engineering-workstation-bootstrap/functions.zsh"
test "$(find -L "$fixture_home/.codex/skills" "$fixture_home/.agents/skills" -type f -path '*/layers/*/SKILL.md' | wc -l | tr -d ' ')" = 0
test -f "$fixture_home/.local/share/engineering-workstation-bootstrap/current/skill-library/layered-fixture/layers/00/SKILL.md"

printf 'Validating repeat activation idempotence and nested rollback...\n'
write_activation_contract fixture-v1 "$tmp/activation-v2.json"
WORKSTATION_TRANSACTION_ID=fixture-v2 bash bin/workstation-activate \
  --activation-contract "$tmp/activation-v2.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-v1 >/dev/null
test "$(grep -Fxc "source \"\$HOME/.config/engineering-workstation-bootstrap/shell.zsh\"" "$fixture_home/.zshrc")" = 1
activation_two="$fixture_home/.local/state/engineering-workstation-bootstrap/receipts/activation-fixture-v2.json"
test "$(readlink "$fixture_home/.local/share/engineering-workstation-bootstrap/current")" = "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-v1-fixture-v2"
bash bin/workstation-rollback --receipt "$activation_two" --home "$fixture_home" >/dev/null
test "$(cat "$fixture_home/.local/state/engineering-workstation-bootstrap/current-transaction")" = fixture-v1
bash bin/workstation-rollback --receipt "$activation_one" --home "$fixture_home" >/dev/null
test ! -L "$fixture_home/.local/share/engineering-workstation-bootstrap/current"
test "$(sed -n '1p' "$fixture_home/.zshrc")" = '# user-owned-start'
test -f "$fixture_home/.codex/skills/legacy/layers/00/SKILL.md"

printf 'Validating automatic rollback after a partial apply...\n'
before_hash="$(shasum -a 256 "$fixture_home/.zshrc" | awk '{print $1}')"
write_activation_contract fixture-partial "$tmp/activation-partial.json"
if WORKSTATION_TRANSACTION_ID=fixture-partial WORKSTATION_FAIL_AFTER_PATHS=3 bash bin/workstation-activate \
  --activation-contract "$tmp/activation-partial.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-partial >/dev/null 2>&1; then exit 1; fi
test "$before_hash" = "$(shasum -a 256 "$fixture_home/.zshrc" | awk '{print $1}')"
test -f "$fixture_home/.codex/skills/legacy/layers/00/SKILL.md"
test "$(jq -r .status "$fixture_home/.local/state/engineering-workstation-bootstrap/receipts/activation-fixture-partial.json")" = rolled-back

printf 'Validating automatic rollback on failed post-activation doctor...\n'
before_hash="$(shasum -a 256 "$fixture_home/.zshrc" | awk '{print $1}')"
write_activation_contract fixture-fail "$tmp/activation-fail.json"
if WORKSTATION_TRANSACTION_ID=fixture-fail WORKSTATION_DOCTOR_FORCE_FAIL=1 bash bin/workstation-activate \
  --activation-contract "$tmp/activation-fail.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-fail >/dev/null 2>&1; then exit 1; fi
test "$before_hash" = "$(shasum -a 256 "$fixture_home/.zshrc" | awk '{print $1}')"
test "$(jq -r .status "$fixture_home/.local/state/engineering-workstation-bootstrap/receipts/activation-fixture-fail.json")" = rolled-back

printf 'Validating secret exclusion...\n'
jq '.secretValues=false | .leak=("ghp_" + "abcdefghijklmnopqrstuvwxyz123456")' "$tmp/private-profile.json" > "$tmp/unsafe-profile.json"
unsafe_sha="$(shasum -a 256 "$tmp/unsafe-profile.json" | awk '{print $1}')"
jq --arg sha "$unsafe_sha" '.privateProfileSha256=$sha' "$tmp/activation-v1.json" > "$tmp/unsafe-contract.json"
if WORKSTATION_TRANSACTION_ID=unsafe bash bin/workstation-activate --activation-contract "$tmp/unsafe-contract.json" \
  --private-profile "$tmp/unsafe-profile.json" --home "$fixture_home" --version fixture-v1 >/dev/null 2>&1; then exit 1; fi

printf 'Validating staged reconcile idempotence...\n'
WORKSTATION_STAGE_ROOT="$tmp/stage" bash bin/staged-workstation reconcile >/dev/null
first="$(shasum -a 256 "$tmp/stage/receipt.json" | awk '{print $1}')"
WORKSTATION_STAGE_ROOT="$tmp/stage" bash bin/staged-workstation reconcile >/dev/null
test "$first" = "$(shasum -a 256 "$tmp/stage/receipt.json" | awk '{print $1}')"

printf 'Validating package reproducibility and private-overlay exclusion...\n'
bash packaging/build-package.sh 0.2.0-fixture >/dev/null
package="dist/engineering-workstation-bootstrap-0.2.0-fixture.tar.gz"
package_sha="$(shasum -a 256 "$package" | awk '{print $1}')"
cp "$package" "$tmp/first-package.tar.gz"
bash packaging/build-package.sh 0.2.0-fixture >/dev/null
test "$package_sha" = "$(shasum -a 256 "$package" | awk '{print $1}')"
tar -tzf "$package" > "$tmp/package-entries.txt"
if rg -q 'tony-private-profile\.json|activation-.*\.json' "$tmp/package-entries.txt"; then exit 1; fi
rg -q '/CLAUDE\.md$' "$tmp/package-entries.txt"
rg -q '/manifests/homebrew\.json$' "$tmp/package-entries.txt"
mkdir -p "$tmp/unpacked"
tar -xzf "$package" -C "$tmp/unpacked"
unpacked="$tmp/unpacked/engineering-workstation-bootstrap-0.2.0-fixture"
make -C "$unpacked" help >/dev/null
bash "$unpacked/packaging/build-package.sh" extracted-fixture >/dev/null
test -s "$unpacked/dist/engineering-workstation-bootstrap-extracted-fixture.tar.gz"

printf 'Validating contract-bound Drive current/releases/receipts layout...\n'
mkdir -p "$tmp/drive"
drive_root="$(cd "$tmp/drive" && pwd -P)"
jq -n --arg driveRoot "$drive_root" --arg sha "$package_sha" --arg profileSha "$profile_sha" \
  '{schemaVersion:1,publicationAuthorized:true,authorityReference:"fixture:publication",driveRoot:$driveRoot,version:"0.2.0-fixture",archiveSha256:$sha,privateProfileSha256:$profileSha}' > "$tmp/publication.json"
bash bin/workstation-publish-drive --publication-contract "$tmp/publication.json" --version 0.2.0-fixture \
  --drive-root "$drive_root" --archive "$package" --private-profile "$tmp/private-profile.json" >/dev/null
distribution="$drive_root/Tony Workstation Bootstrap"
test -L "$distribution/current"
for path in START_TONY_WORKSTATION_BOOTSTRAP.command manifest.json checksums.sha256 VERSION README-FIRST.txt; do test -e "$distribution/current/$path"; done
test -d "$distribution/releases/0.2.0-fixture"
test -f "$distribution/current/private/private-profile.json"
test -f "$distribution/current/private/private-profile.assets/skills/layered-fixture/layers/00/SKILL.md"
test "$(find "$distribution/receipts" -type f -name 'publish-*.json' | wc -l | tr -d ' ')" -ge 1
test "$(awk 'NR==1 {print $1}' "$distribution/current/checksums.sha256")" = "$(jq -r .sha256 "$distribution/current/manifest.json")"

printf 'PASS: v2 activation, rollback, discovery, policy, MCP, utilities, secrets, reproducibility, and Drive fixtures\n'
