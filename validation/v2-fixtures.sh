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
mkdir -p "$tmp/system-original/skill-creator/scripts"
printf '%s\n' '---' 'name: skill-creator' 'description: built-in fixture' '---' \
  > "$tmp/system-original/skill-creator/SKILL.md"
for n in {1..48}; do
  printf -v padded '%02d' "$n"
  printf 'built-in asset %s\n' "$padded" > "$tmp/system-original/skill-creator/scripts/asset-$padded"
done
chmod 755 "$tmp/system-original/skill-creator/scripts/asset-01"
ln -s asset-01 "$tmp/system-original/skill-creator/scripts/current"
ln -s current "$tmp/system-original/skill-creator/scripts/chained"
test "$(find "$tmp/system-original" -type f | wc -l | tr -d ' ')" = 49
printf 'Codex system marker fixture\n' > "$tmp/system-original/.codex-system-skills.marker"
mkdir -p "$tmp/system-original/vsok-ticket-runner"
printf '%s\n' '---' 'name: vsok-ticket-runner' 'description: retired fixture' '---' \
  > "$tmp/system-original/vsok-ticket-runner/SKILL.md"
cp -pR "$tmp/system-original" "$fixture_home/.codex/skills/.system"
cp -pR "$tmp/system-original" "$tmp/system-preserved"
rm -r "$tmp/system-preserved/vsok-ticket-runner"
printf '%s\n' '---' 'name: layered-fixture' 'description: fixture layered skill' '---' '# fixture' > "$tmp/source-skill/SKILL.md"
printf '%s\n' '# invalid internal layer kept outside discovery' > "$tmp/source-skill/layers/00/SKILL.md"
printf '%s\n' '#!/usr/bin/env bash' 'printf "reasonpack fixture\\n"' > "$tmp/reasonpack"
chmod 755 "$tmp/reasonpack"
utility_sha="$(shasum -a 256 "$tmp/reasonpack" | awk '{print $1}')"
mkdir -p "$tmp/private-profile.assets/skills" "$tmp/private-profile.assets/bin"
cp -R "$tmp/source-skill" "$tmp/private-profile.assets/skills/layered-fixture"
mkdir -p "$tmp/private-profile.assets/skills/hyperframes"
printf '%s\n' '---' 'name: hyperframes' 'description: fixture task-scoped media' '---' '# media fixture' > "$tmp/private-profile.assets/skills/hyperframes/SKILL.md"
cp "$tmp/reasonpack" "$tmp/private-profile.assets/bin/reasonpack"

printf 'Validating private-profile inventory through managed skill-root symlinks...\n'
inventory_home="$tmp/inventory-home"
managed_release="$tmp/managed-release"
mkdir -p "$inventory_home/.codex" "$inventory_home/.agents" \
  "$inventory_home/.local/share/engineering-workstation-bootstrap" \
  "$managed_release/codex-skills/linked-codex" \
  "$managed_release/agent-skills/linked-agent" \
  "$managed_release/skill-library/linked-codex" \
  "$managed_release/skill-library/linked-agent" \
  "$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-codex/layers/00" \
  "$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-agent"
ln -s "$managed_release" "$inventory_home/.local/share/engineering-workstation-bootstrap/current"
ln -s "$inventory_home/.local/share/engineering-workstation-bootstrap/current/codex-skills" "$inventory_home/.codex/skills"
ln -s "$inventory_home/.local/share/engineering-workstation-bootstrap/current/agent-skills" "$inventory_home/.agents/skills"
printf '%s\n' '---' 'name: linked-codex' 'description: managed entrypoint fixture' '---' \
  '# managed wrapper, not the package' > "$managed_release/codex-skills/linked-codex/SKILL.md"
printf '%s\n' '---' 'name: linked-agent' 'description: managed entrypoint fixture' '---' \
  '# managed wrapper, not the package' > "$managed_release/agent-skills/linked-agent/SKILL.md"
mkdir -p "$managed_release/codex-skills/.system/skill-creator/scripts"
printf '%s\n' '---' 'name: skill-creator' 'description: built-in fixture' '---' \
  > "$managed_release/codex-skills/.system/skill-creator/SKILL.md"
printf 'built-in support asset\n' > "$managed_release/codex-skills/.system/skill-creator/scripts/helper.txt"
printf '%s\n' '---' 'name: linked-codex' \
  'description: Managed entrypoint for the externally stored linked-codex skill package.' '---' '' \
  "Read and follow the complete skill at \`$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-codex/SKILL.md\`. Resolve every relative reference from the package." \
  > "$managed_release/skill-library/linked-codex/SKILL.md"
printf '%s\n' '---' 'name: linked-agent' \
  'description: Managed entrypoint for the externally stored linked-agent skill package.' '---' '' \
  "Read and follow the complete skill at \`$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-agent/SKILL.md\`. Resolve every relative reference from the package." \
  > "$managed_release/skill-library/linked-agent/SKILL.md"
printf '%s\n' '---' 'name: linked-codex' 'description: full package fixture' '---' \
  '# canonical package' > "$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-codex/SKILL.md"
printf '%s\n' '# internal layer remains package material' \
  > "$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-codex/layers/00/SKILL.md"
printf '%s\n' '---' 'name: linked-agent' 'description: full package fixture' '---' \
  '# canonical package' > "$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-agent/SKILL.md"
# A retired local skill remains in old installs but is not re-exported.
mkdir -p "$managed_release/codex-skills/governed-edit-protocol"
printf '%s\n' '---' 'name: governed-edit-protocol' 'description: retired fixture' '---' \
  > "$managed_release/codex-skills/governed-edit-protocol/SKILL.md"
for old in llmstack-installer-discipline vsok-ticket-runner vsok-refactor-protocol; do
  mkdir -p "$managed_release/codex-skills/$old"
  printf '%s\n' '---' "name: $old" 'description: obsolete fixture' '---' \
    > "$managed_release/codex-skills/$old/SKILL.md"
done
mkdir -p "$managed_release/agent-skills/hyperframes"
printf '%s\n' '---' 'name: hyperframes' 'description: creative fixture' '---' \
  > "$managed_release/agent-skills/hyperframes/SKILL.md"
HOME="$inventory_home" bash bin/workstation-private-profile inventory \
  --output "$profile_tmp/inventoried-profile.json" >/dev/null
test "$(jq '.skills | length' "$profile_tmp/inventoried-profile.json")" = 2
test "$(jq '.taskScopedSkills | length' "$profile_tmp/inventoried-profile.json")" = 1
test "$(jq -r '.taskScopedSkills[0].name' "$profile_tmp/inventoried-profile.json")" = hyperframes
test "$(jq -r '[.skills[].name] | sort | join(",")' "$profile_tmp/inventoried-profile.json")" = 'linked-agent,linked-codex'
test ! -e "$profile_tmp/inventoried-profile.assets/skills/skill-creator"
test -f "$managed_release/codex-skills/.system/skill-creator/scripts/helper.txt"
test ! -e "$profile_tmp/inventoried-profile.assets/skills/governed-edit-protocol"
test ! -e "$profile_tmp/inventoried-profile.assets/skills/llmstack-installer-discipline"
test ! -e "$profile_tmp/inventoried-profile.assets/skills/vsok-refactor-protocol"
test ! -e "$profile_tmp/inventoried-profile.assets/skills/vsok-ticket-runner"
test -f "$profile_tmp/inventoried-profile.assets/skills/hyperframes/SKILL.md"
test -f "$profile_tmp/inventoried-profile.assets/skills/linked-codex/layers/00/SKILL.md"
cmp "$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-codex/SKILL.md" \
  "$profile_tmp/inventoried-profile.assets/skills/linked-codex/SKILL.md"
cmp "$inventory_home/.local/share/engineering-workstation-bootstrap/versions/canonical/linked-agent/SKILL.md" \
  "$profile_tmp/inventoried-profile.assets/skills/linked-agent/SKILL.md"

jq -n --arg utilitySha "$utility_sha" \
  '{schemaVersion:1,profile:"fixture-private",secretValues:false,
    shell:{preservePrompt:true,githubRoot:"/fixture/github",functions:["cgh","lgh"]},
    skills:[{name:"layered-fixture",sourceDir:"private-profile.assets/skills/layered-fixture",installRoot:"codex-skills",state:"enabled"}],
    taskScopedSkills:[{name:"hyperframes",sourceDir:"private-profile.assets/skills/hyperframes",installRoot:"agent-skills",state:"on-demand"}],
    environment:[{name:"SUPABASE_ACCESS_TOKEN",class:"oauth-enrolled",origin:"provider",valueIncluded:false}],
    mcp:[{name:"supabase-fixture",state:"auth-required",startup:"disabled",credentials:"preserve"}],
    utilities:[{name:"reasonpack",source:"private-profile.assets/bin/reasonpack",sha256:$utilitySha,aliases:["yt","rp"],dependencies:[],classification:"canonicalize"}]}' > "$tmp/private-profile.json"
profile_sha="$(shasum -a 256 "$tmp/private-profile.json" | awk '{print $1}')"

write_activation_contract() {
  local version="$1" output="$2" model="${3:-}"
  local builtin_fp marker_fp legacy_fp
  builtin_fp="$(python3 lib/workstation-recovery.py fingerprint "$fixture_home/.codex/skills/.system/skill-creator")"
  marker_fp="$(python3 lib/workstation-recovery.py fingerprint "$fixture_home/.codex/skills/.system/.codex-system-skills.marker")"
  legacy_fp='null'
  if [[ -d "$fixture_home/.codex/skills/.system/vsok-ticket-runner" ]]; then
    legacy_fp="$(python3 lib/workstation-recovery.py fingerprint "$fixture_home/.codex/skills/.system/vsok-ticket-runner")"
  fi
  jq -n --arg targetHome "$fixture_home" --arg version "$version" --arg profileSha "$profile_sha" --arg model "$model" \
    --argjson builtinFp "$builtin_fp" --argjson markerFp "$marker_fp" --argjson legacyFp "$legacy_fp" \
    '{schemaVersion:1,activationAuthorized:true,allowLiveHome:false,authorityReference:"fixture:activation",
      targetHome:$targetHome,version:$version,privateProfileSha256:$profileSha,manageSkillRoots:true,
      codexSystemSkills:([{name:"skill-creator",classification:"openai-builtin",action:"preserve",
        evidenceReference:"fixture:verified-openai-builtin",authorityReference:"fixture:owner",
        fingerprint:$builtinFp},
        {name:".codex-system-skills.marker",classification:"openai-builtin",action:"preserve",
        evidenceReference:"fixture:verified-codex-marker",authorityReference:"fixture:owner",
        fingerprint:$markerFp}]
        + (if $legacyFp == null then [] else [{name:"vsok-ticket-runner",classification:"retired-legacy",
          action:"exclude",evidenceReference:"fixture:oct-12-retirement",authorityReference:"fixture:owner",
          fingerprint:$legacyFp}] end))}
      + (if $model == "" then {} else {codexModel:$model} end)' > "$output"
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
printf 'Validating stale private-profile built-in rejection...\n'
jq '.skills += [{name:"skill-creator",sourceDir:"private-profile.assets/skills/layered-fixture",installRoot:"codex-skills",state:"enabled"}]' \
  "$tmp/private-profile.json" > "$tmp/system-duplicate-profile.json"
system_duplicate_sha="$(shasum -a 256 "$tmp/system-duplicate-profile.json" | awk '{print $1}')"
write_activation_contract fixture-system-duplicate "$tmp/activation-system-duplicate-base.json"
jq --arg sha "$system_duplicate_sha" '.privateProfileSha256=$sha' \
  "$tmp/activation-system-duplicate-base.json" > "$tmp/activation-system-duplicate.json"
if WORKSTATION_TRANSACTION_ID=fixture-system-duplicate bash bin/workstation-activate \
  --activation-contract "$tmp/activation-system-duplicate.json" --private-profile "$tmp/system-duplicate-profile.json" \
  --home "$fixture_home" --version fixture-system-duplicate >"$tmp/system-duplicate.log" 2>&1; then exit 1; fi
grep -Fq 'private profile duplicates a reserved Codex .system skill' "$tmp/system-duplicate.log"
test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-system-duplicate-fixture-system-duplicate"
diff -qr "$tmp/system-original" "$fixture_home/.codex/skills/.system"
printf 'Validating retired-governor activation rejection...\n'
write_activation_contract fixture-retired "$tmp/activation-retired-base.json"
jq '.skills += [{name:"governed-edit-protocol",sourceDir:"private-profile.assets/skills/layered-fixture",installRoot:"codex-skills",state:"enabled"}]' \
  "$tmp/private-profile.json" > "$tmp/retired-profile.json"
retired_profile_sha="$(shasum -a 256 "$tmp/retired-profile.json" | awk '{print $1}')"
jq --arg sha "$retired_profile_sha" '.privateProfileSha256=$sha' \
  "$tmp/activation-retired-base.json" > "$tmp/activation-retired.json"
if WORKSTATION_TRANSACTION_ID=fixture-retired bash bin/workstation-activate \
  --activation-contract "$tmp/activation-retired.json" --private-profile "$tmp/retired-profile.json" \
  --home "$fixture_home" --version fixture-retired >/dev/null 2>&1; then exit 1; fi
test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-retired-fixture-retired"

# Every historical private profile must fail closed on the newly retired
# governors. Do not rely on a missing package to produce a false PASS.
for old in llmstack-installer-discipline vsok-ticket-runner vsok-refactor-protocol; do
  jq --arg name "$old" '.skills += [{name:$name,sourceDir:"private-profile.assets/skills/layered-fixture",installRoot:"codex-skills",state:"enabled"}]' \
    "$tmp/private-profile.json" > "$tmp/retired-extended-profile.json"
  old_sha="$(shasum -a 256 "$tmp/retired-extended-profile.json" | awk '{print $1}')"
  jq --arg sha "$old_sha" '.privateProfileSha256=$sha' "$tmp/activation-retired-base.json" > "$tmp/activation-retired-extended.json"
  if WORKSTATION_TRANSACTION_ID=fixture-retired-extended bash bin/workstation-activate \
    --activation-contract "$tmp/activation-retired-extended.json" --private-profile "$tmp/retired-extended-profile.json" \
    --home "$fixture_home" --version fixture-retired >"$tmp/retired-extended.log" 2>&1; then exit 1; fi
  grep -Fq 'retired legacy editing skills must not be installed' "$tmp/retired-extended.log"
done
jq '.skills += [{name:"hyperframes",sourceDir:"private-profile.assets/skills/hyperframes",installRoot:"agent-skills",state:"enabled"}]' \
  "$tmp/private-profile.json" > "$tmp/creative-global-profile.json"
creative_sha="$(shasum -a 256 "$tmp/creative-global-profile.json" | awk '{print $1}')"
jq --arg sha "$creative_sha" '.privateProfileSha256=$sha' "$tmp/activation-retired-base.json" > "$tmp/activation-creative-global.json"
if WORKSTATION_TRANSACTION_ID=fixture-creative-global bash bin/workstation-activate \
  --activation-contract "$tmp/activation-creative-global.json" --private-profile "$tmp/creative-global-profile.json" \
  --home "$fixture_home" --version fixture-retired >"$tmp/creative-global.log" 2>&1; then exit 1; fi
grep -Fq 'creative skills must be staged for task-scoped use' "$tmp/creative-global.log"

printf 'Validating task-scoped creative skills cannot enter Codex .system...\n'
for creative in hyperframes hyperframes-animation media-use; do
  mkdir -p "$fixture_home/.codex/skills/.system/$creative"
  printf '%s\n' '---' "name: $creative" 'description: scoped fixture' '---' \
    > "$fixture_home/.codex/skills/.system/$creative/SKILL.md"
  creative_fp="$(python3 lib/workstation-recovery.py fingerprint "$fixture_home/.codex/skills/.system/$creative")"
  write_activation_contract fixture-system-creative "$tmp/activation-system-creative-base.json"
  jq --arg name "$creative" --argjson fingerprint "$creative_fp" \
    '.codexSystemSkills += [{name:$name,classification:"owner-managed",action:"preserve",
      evidenceReference:"fixture:creative",authorityReference:"fixture:owner",fingerprint:$fingerprint}]' \
    "$tmp/activation-system-creative-base.json" > "$tmp/activation-system-creative.json"
  if WORKSTATION_TRANSACTION_ID=fixture-system-creative bash bin/workstation-activate \
    --activation-contract "$tmp/activation-system-creative.json" --private-profile "$tmp/private-profile.json" \
    --home "$fixture_home" --version fixture-system-creative >"$tmp/system-creative.log" 2>&1; then exit 1; fi
  grep -Fq 'task-scoped creative skill cannot be globally discovered' "$tmp/system-creative.log"
  test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-system-creative-fixture-system-creative"
  rm -r "$fixture_home/.codex/skills/.system/$creative"
done
mkdir -p "$fixture_home/.codex/skills/.system/owner-alias"
printf '%s\n' '---' 'name: "hyperframes"' 'description: aliased scoped fixture' '---' \
  > "$fixture_home/.codex/skills/.system/owner-alias/SKILL.md"
alias_fp="$(python3 lib/workstation-recovery.py fingerprint "$fixture_home/.codex/skills/.system/owner-alias")"
write_activation_contract fixture-system-alias "$tmp/activation-system-alias-base.json"
jq --argjson fingerprint "$alias_fp" \
  '.codexSystemSkills += [{name:"owner-alias",classification:"owner-managed",action:"preserve",
    evidenceReference:"fixture:alias",authorityReference:"fixture:owner",fingerprint:$fingerprint}]' \
  "$tmp/activation-system-alias-base.json" > "$tmp/activation-system-alias.json"
if WORKSTATION_TRANSACTION_ID=fixture-system-alias bash bin/workstation-activate \
  --activation-contract "$tmp/activation-system-alias.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-system-alias >"$tmp/system-alias.log" 2>&1; then exit 1; fi
grep -Fq 'task-scoped creative skill cannot be globally discovered' "$tmp/system-alias.log"
test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-system-alias-fixture-system-alias"
rm -r "$fixture_home/.codex/skills/.system/owner-alias"

printf 'Validating retired identities cannot be preserved through Codex .system aliases...\n'
for declared_retired in governed-edit-protocol vsok-ticket-runner vsok-unregistered; do
  for category in owner-managed openai-builtin; do
    for name_prefix in 'name:' ' name:'; do
      mkdir -p "$fixture_home/.codex/skills/.system/owner-alias"
      name_indent="${name_prefix%name:}"
      printf '%s\n' '---' "$name_prefix \"$declared_retired\"" "${name_indent}description: aliased retired fixture" '---' \
        > "$fixture_home/.codex/skills/.system/owner-alias/SKILL.md"
      alias_fp="$(python3 lib/workstation-recovery.py fingerprint "$fixture_home/.codex/skills/.system/owner-alias")"
      write_activation_contract fixture-system-retired-alias "$tmp/activation-system-retired-alias-base.json"
      jq --arg category "$category" --argjson fingerprint "$alias_fp" \
        '.codexSystemSkills += [{name:"owner-alias",classification:$category,action:"preserve",
          evidenceReference:"fixture:retired-alias",authorityReference:"fixture:owner",fingerprint:$fingerprint}]' \
        "$tmp/activation-system-retired-alias-base.json" > "$tmp/activation-system-retired-alias.json"
      if python3 lib/workstation-recovery.py system-skills-check "$tmp/activation-system-retired-alias.json" \
        "$fixture_home" >"$tmp/system-retired-alias.log" 2>&1; then
        printf 'FAIL: preserved %s alias with %s\n' "$category" "$name_prefix" >&2
        exit 1
      fi
      grep -Fq 'retired legacy Codex .system skill cannot be preserved' "$tmp/system-retired-alias.log"
      rm -r "$fixture_home/.codex/skills/.system/owner-alias"
    done
  done
done

printf 'Validating indented built-in frontmatter and delimiter whitespace remain preserved...\n'
for opening_marker in '---' '--- '; do
  for closing_marker in '---' '--- '; do
    printf '%s\n' "$opening_marker" ' name: "skill-creator"' ' description: indented built-in fixture' "$closing_marker" \
      > "$fixture_home/.codex/skills/.system/skill-creator/SKILL.md"
    write_activation_contract fixture-system-indented-builtin "$tmp/activation-system-indented-builtin.json"
    python3 lib/workstation-recovery.py system-skills-check "$tmp/activation-system-indented-builtin.json" "$fixture_home"
  done
done
cp "$tmp/system-original/skill-creator/SKILL.md" "$fixture_home/.codex/skills/.system/skill-creator/SKILL.md"

printf 'Validating ambiguous Codex .system skill frontmatter fails closed...\n'
for frontmatter_case in missing nested duplicate embedded_delimiter; do
  mkdir -p "$fixture_home/.codex/skills/.system/owner-alias"
  case "$frontmatter_case" in
    missing)
      printf '%s\n' '---' 'description: no declared identity' '---' \
        > "$fixture_home/.codex/skills/.system/owner-alias/SKILL.md"
      expected_frontmatter_error='Codex .system skill name is missing' ;;
    nested)
      printf '%s\n' '---' 'metadata:' '  name: vsok-ticket-runner' 'description: nested identity' '---' \
        > "$fixture_home/.codex/skills/.system/owner-alias/SKILL.md"
      expected_frontmatter_error='Codex .system skill name is missing' ;;
    duplicate)
      printf '%s\n' '---' 'name: owner-alias' 'name: vsok-ticket-runner' '---' \
        > "$fixture_home/.codex/skills/.system/owner-alias/SKILL.md"
      expected_frontmatter_error='duplicate Codex .system skill name' ;;
    embedded_delimiter)
      printf '%s\n' '---' 'name: owner-alias' 'description: |' '  ---' 'name: vsok-ticket-runner' '---' \
        > "$fixture_home/.codex/skills/.system/owner-alias/SKILL.md"
      expected_frontmatter_error='duplicate Codex .system skill name' ;;
  esac
  alias_fp="$(python3 lib/workstation-recovery.py fingerprint "$fixture_home/.codex/skills/.system/owner-alias")"
  write_activation_contract fixture-system-ambiguous "$tmp/activation-system-ambiguous-base.json"
  jq --argjson fingerprint "$alias_fp" \
    '.codexSystemSkills += [{name:"owner-alias",classification:"owner-managed",action:"preserve",
      evidenceReference:"fixture:ambiguous",authorityReference:"fixture:owner",fingerprint:$fingerprint}]' \
    "$tmp/activation-system-ambiguous-base.json" > "$tmp/activation-system-ambiguous.json"
  if python3 lib/workstation-recovery.py system-skills-check "$tmp/activation-system-ambiguous.json" \
    "$fixture_home" >"$tmp/system-ambiguous.log" 2>&1; then exit 1; fi
  grep -Fq "$expected_frontmatter_error" "$tmp/system-ambiguous.log"
  rm -r "$fixture_home/.codex/skills/.system/owner-alias"
done

printf 'Validating nested Codex .system links stay inside their package...\n'
system_scripts="$fixture_home/.codex/skills/.system/skill-creator/scripts"
for link_case in absolute escaping dangling chained; do
  rm "$system_scripts/current"
  case "$link_case" in
    absolute) ln -s "$system_scripts/asset-01" "$system_scripts/current"; expected_link_error='absolute link is forbidden' ;;
    escaping) ln -s '../../vsok-ticket-runner/SKILL.md' "$system_scripts/current"; expected_link_error='link leaves its package' ;;
    dangling) ln -s missing-asset "$system_scripts/current"; expected_link_error='link is dangling' ;;
    chained)
      ln -s '../../vsok-ticket-runner/SKILL.md' "$system_scripts/hop"
      ln -s hop "$system_scripts/current"
      expected_link_error='link leaves its package' ;;
  esac
  write_activation_contract "fixture-link-$link_case" "$tmp/activation-link-$link_case.json"
  if WORKSTATION_TRANSACTION_ID="fixture-link-$link_case" bash bin/workstation-activate \
    --activation-contract "$tmp/activation-link-$link_case.json" --private-profile "$tmp/private-profile.json" \
    --home "$fixture_home" --version "fixture-link-$link_case" >"$tmp/link-$link_case.log" 2>&1; then exit 1; fi
  grep -Fq "$expected_link_error" "$tmp/link-$link_case.log"
  test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-link-$link_case-fixture-link-$link_case"
  rm "$system_scripts/current"
  if [[ "$link_case" == chained ]]; then rm "$system_scripts/hop"; fi
  ln -s asset-01 "$system_scripts/current"
done

printf 'Validating unknown and stale Codex .system classifications fail closed...\n'
write_activation_contract fixture-resurrection "$tmp/activation-resurrection-base.json"
jq '(.codexSystemSkills[] | select(.name == "vsok-ticket-runner")) |=
    (.classification = "owner-managed" | .action = "preserve")' \
  "$tmp/activation-resurrection-base.json" > "$tmp/activation-resurrection.json"
if WORKSTATION_TRANSACTION_ID=fixture-resurrection bash bin/workstation-activate \
  --activation-contract "$tmp/activation-resurrection.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-resurrection >"$tmp/resurrection.log" 2>&1; then exit 1; fi
grep -Fq 'retired legacy Codex .system skill cannot be preserved' "$tmp/resurrection.log"
test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-resurrection-fixture-resurrection"
write_activation_contract fixture-unknown "$tmp/activation-unknown.json"
mkdir -p "$fixture_home/.codex/skills/.system/unclassified-local"
printf '%s\n' '---' 'name: unclassified-local' 'description: unknown' '---' \
  > "$fixture_home/.codex/skills/.system/unclassified-local/SKILL.md"
if WORKSTATION_TRANSACTION_ID=fixture-unknown bash bin/workstation-activate \
  --activation-contract "$tmp/activation-unknown.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-unknown >"$tmp/unknown.log" 2>&1; then exit 1; fi
grep -Fq 'Codex .system has unclassified entries' "$tmp/unknown.log"
test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-unknown-fixture-unknown"
test -f "$fixture_home/.codex/skills/.system/unclassified-local/SKILL.md"
rm -r "$fixture_home/.codex/skills/.system/unclassified-local"
write_activation_contract fixture-stale "$tmp/activation-stale.json"
printf 'changed after classification\n' >> "$fixture_home/.codex/skills/.system/skill-creator/SKILL.md"
if WORKSTATION_TRANSACTION_ID=fixture-stale bash bin/workstation-activate \
  --activation-contract "$tmp/activation-stale.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-stale >"$tmp/stale.log" 2>&1; then exit 1; fi
grep -Fq 'Codex .system classification is stale' "$tmp/stale.log"
test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-stale-fixture-stale"
cp "$tmp/system-original/skill-creator/SKILL.md" "$fixture_home/.codex/skills/.system/skill-creator/SKILL.md"

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
diff -qr "$tmp/system-preserved" "$fixture_home/.codex/skills/.system"
test ! -e "$fixture_home/.codex/skills/.system/vsok-ticket-runner"
test -f "$fixture_home/.local/state/engineering-workstation-bootstrap/backups/fixture-v1/files/.codex/skills/.system/vsok-ticket-runner/SKILL.md"
test -x "$fixture_home/.codex/skills/.system/skill-creator/scripts/asset-01"
cmp "$tmp/system-original/.codex-system-skills.marker" "$fixture_home/.codex/skills/.system/.codex-system-skills.marker"
test "$(readlink "$fixture_home/.codex/skills/.system/skill-creator/scripts/current")" = asset-01
test "$(readlink "$fixture_home/.codex/skills/.system/skill-creator/scripts/chained")" = current
test -f "$fixture_home/.local/share/engineering-workstation-bootstrap/current/task-scoped-skills/hyperframes/SKILL.md"
test ! -e "$fixture_home/.agents/skills/hyperframes"
test ! -e "$fixture_home/.codex/skills/vsok-ticket-runner"
test ! -e "$fixture_home/.codex/skills/llmstack-installer-discipline"
# Task-scoped packages must survive a future profile regeneration from a
# managed release even though no wrapper advertises them globally.
HOME="$fixture_home" bash bin/workstation-private-profile inventory --output "$profile_tmp/reinventoried.json" >/dev/null
test "$(jq -r '[.taskScopedSkills[]?.name] | join(",")' "$profile_tmp/reinventoried.json")" = hyperframes
test -f "$profile_tmp/reinventoried.assets/skills/hyperframes/SKILL.md"

printf 'Validating repeat activation idempotence and nested rollback...\n'
write_activation_contract fixture-v1 "$tmp/activation-v2.json" gpt-6-astra
WORKSTATION_TRANSACTION_ID=fixture-v2 bash bin/workstation-activate \
  --activation-contract "$tmp/activation-v2.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-v1 >/dev/null
test "$(grep -Fxc "source \"\$HOME/.config/engineering-workstation-bootstrap/shell.zsh\"" "$fixture_home/.zshrc")" = 1
activation_two="$fixture_home/.local/state/engineering-workstation-bootstrap/receipts/activation-fixture-v2.json"
test "$(grep -Fxc 'model = "gpt-6-astra"' "$fixture_home/.codex/config.toml")" = 1
test "$(grep -Fxc 'approvals_reviewer = "auto_review"' "$fixture_home/.codex/config.toml")" = 1
test "$(readlink "$fixture_home/.local/share/engineering-workstation-bootstrap/current")" = "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-v1-fixture-v2"
diff -qr "$tmp/system-preserved" "$fixture_home/.codex/skills/.system"
bash bin/workstation-rollback --receipt "$activation_two" --home "$fixture_home" >/dev/null
diff -qr "$tmp/system-preserved" "$fixture_home/.codex/skills/.system"
test "$(grep -Fxc 'model = "fixture-model"' "$fixture_home/.codex/config.toml")" = 1
test "$(cat "$fixture_home/.local/state/engineering-workstation-bootstrap/current-transaction")" = fixture-v1
bash bin/workstation-rollback --receipt "$activation_one" --home "$fixture_home" >/dev/null
diff -qr "$tmp/system-original" "$fixture_home/.codex/skills/.system"
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
stage_root="$profile_tmp/stage"
WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation reconcile >/dev/null
first="$(shasum -a 256 "$stage_root/receipt.json" | awk '{print $1}')"
test "$(jq -r '.schema_version' "$stage_root/receipt.json")" = 2
for managed in config/codex/AGENTS.md config/codex/config.toml; do
  test "$(jq -r --arg name "$managed" '.managed_sha256[$name]' "$stage_root/receipt.json")" = \
    "$(shasum -a 256 "$stage_root/$managed" | awk '{print $1}')"
done
WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation reconcile >/dev/null
test "$first" = "$(shasum -a 256 "$stage_root/receipt.json" | awk '{print $1}')"
for file in AGENTS.md docs/CAPABILITY-MAP.md docs/CONNECTOR-FABRIC.md \
  docs/AGENT-OPERATING-CONTRACT.md manifests/connector-capabilities.json \
  skills/workstation-operations/SKILL.md; do
  cmp "$file" "$stage_root/$file"
done
rg -q 'docs/AGENT-OPERATING-CONTRACT.md' "$stage_root/AGENTS.md"
rg -q 'manifests/connector-capabilities.json#route_observation' \
  "$stage_root/skills/workstation-operations/SKILL.md"
for nested in config/codex/AGENTS.md config/codex/config.toml; do
  cp "$stage_root/$nested" "$profile_tmp/nested-original"
  printf '\nunrelated nested edit\n' >> "$stage_root/$nested"
  edited_hash="$(shasum -a 256 "$stage_root/$nested" | awk '{print $1}')"
  if WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation reconcile >/dev/null 2>&1; then exit 1; fi
  if WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation rollback >/dev/null 2>&1; then exit 1; fi
  test "$edited_hash" = "$(shasum -a 256 "$stage_root/$nested" | awk '{print $1}')"
  cp "$profile_tmp/nested-original" "$stage_root/$nested"
done
printf '{"schema_version":1,"mode":"staged","status":"ready","secret_values":false}\n' > "$stage_root/receipt.json"
cp "$stage_root/config/codex/config.toml" "$profile_tmp/legacy-config-original"
printf '\nlegacy nested edit\n' >> "$stage_root/config/codex/config.toml"
if WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation reconcile >/dev/null 2>&1; then exit 1; fi
if WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation rollback >/dev/null 2>&1; then exit 1; fi
cp "$profile_tmp/legacy-config-original" "$stage_root/config/codex/config.toml"
WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation reconcile >/dev/null
test "$(jq -r '.schema_version' "$stage_root/receipt.json")" = 2
printf 'unrelated nested content\n' > "$stage_root/docs/unrelated.txt"
if WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation reconcile >/dev/null 2>&1; then exit 1; fi
if WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation rollback >/dev/null 2>&1; then exit 1; fi
test "$(cat "$stage_root/docs/unrelated.txt")" = 'unrelated nested content'
rm "$stage_root/docs/unrelated.txt"
cp "$stage_root/AGENTS.md" "$profile_tmp/managed-stage-policy"
printf 'changed stage policy\n' > "$stage_root/AGENTS.md"
if WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation reconcile >/dev/null 2>&1; then exit 1; fi
test "$(cat "$stage_root/AGENTS.md")" = 'changed stage policy'
cp "$profile_tmp/managed-stage-policy" "$stage_root/AGENTS.md"
WORKSTATION_STAGE_ROOT="$stage_root" bash bin/staged-workstation rollback >/dev/null
test ! -e "$stage_root"

printf 'Validating stage-root custody before any policy replacement...\n'
unrelated_stage="$profile_tmp/unrelated-stage"
mkdir -p "$unrelated_stage"
printf 'unrelated agent policy\n' > "$unrelated_stage/AGENTS.md"
if WORKSTATION_STAGE_ROOT="$unrelated_stage" bash bin/staged-workstation reconcile >/dev/null 2>&1; then exit 1; fi
test "$(cat "$unrelated_stage/AGENTS.md")" = 'unrelated agent policy'
test ! -e "$unrelated_stage/receipt.json"
if WORKSTATION_STAGE_ROOT="$unrelated_stage" bash bin/staged-workstation rollback >/dev/null 2>&1; then exit 1; fi
test "$(cat "$unrelated_stage/AGENTS.md")" = 'unrelated agent policy'
ln -s "$unrelated_stage" "$profile_tmp/alias-stage"
if WORKSTATION_STAGE_ROOT="$profile_tmp/alias-stage" bash bin/staged-workstation reconcile >/dev/null 2>&1; then exit 1; fi
test "$(cat "$unrelated_stage/AGENTS.md")" = 'unrelated agent policy'
mkdir -p "$profile_tmp/relative-cwd"
repo_root="$(pwd -P)"
(
  cd "$profile_tmp/relative-cwd"
  if WORKSTATION_STAGE_ROOT=relative-stage bash "$repo_root/bin/staged-workstation" reconcile >/dev/null 2>&1; then exit 1; fi
  test ! -e relative-stage
  if WORKSTATION_STAGE_ROOT=relative-stage bash "$repo_root/bin/staged-workstation" rollback >/dev/null 2>&1; then exit 1; fi
)

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

printf 'Validating digest-bound staged Codex config source and rollback...\n'
cat > "$tmp/staged-codex.toml" <<'TOML'
# Managed routine-execution posture; high-risk stops remain in AGENTS.md.
# Managed routine-execution posture; high-risk stops remain in AGENTS.md.
model = "fixture-model"
model_reasoning_effort = "high"
personality = "pragmatic"
[projects."/synthetic/still-trusted"]
trust_level = "trusted"
[mcp_servers."supabase-fixture"]
url = "https://example.invalid/mcp"
bearer_token_env_var = "SUPABASE_ACCESS_TOKEN"
enabled = true
TOML
write_activation_contract fixture-staged "$tmp/staged-base.json"
config_source_sha="$(shasum -a 256 "$tmp/staged-codex.toml" | awk '{print $1}')"
jq --arg src "$tmp/staged-codex.toml" --arg sha "$config_source_sha" \
  '.codexConfigSource=$src | .codexConfigSourceSha256=$sha' \
  "$tmp/staged-base.json" > "$tmp/staged-contract.json"
jq '.codexConfigSourceSha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"' \
  "$tmp/staged-contract.json" > "$tmp/staged-bad.json"
if WORKSTATION_TRANSACTION_ID=staged-bad bash bin/workstation-activate \
  --activation-contract "$tmp/staged-bad.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-staged >"$tmp/staged-bad.log" 2>&1; then exit 1; fi
grep -Fq 'staged Codex config changed after approval' "$tmp/staged-bad.log"
test ! -e "$fixture_home/.local/share/engineering-workstation-bootstrap/versions/fixture-staged-staged-bad"
WORKSTATION_TRANSACTION_ID=staged-good bash bin/workstation-activate \
  --activation-contract "$tmp/staged-contract.json" --private-profile "$tmp/private-profile.json" \
  --home "$fixture_home" --version fixture-staged >/dev/null
python3 - "$fixture_home/.codex/config.toml" <<'PY'
import pathlib,sys,tomllib
p=pathlib.Path(sys.argv[1]);text=p.read_text();d=tomllib.loads(text)
assert text.count('# Managed routine-execution posture; high-risk stops remain in AGENTS.md.')==1
assert d['model']=='fixture-model' and d['model_reasoning_effort']=='high'
assert d['personality']=='pragmatic' and d['projects']['/synthetic/still-trusted']['trust_level']=='trusted'
assert d['mcp_servers']['supabase-fixture']['enabled'] is False
PY
bash bin/workstation-rollback --receipt "$fixture_home/.local/state/engineering-workstation-bootstrap/receipts/activation-staged-good.json" --home "$fixture_home" >/dev/null
printf 'PASS: staged source SHA binding, normalization, and rollback\n'

printf 'PASS: v2 activation, rollback, discovery, policy, MCP, utilities, secrets, reproducibility, and Drive fixtures\n'
