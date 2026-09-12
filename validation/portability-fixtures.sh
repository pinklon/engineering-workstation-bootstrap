#!/usr/bin/env bash
set -euo pipefail
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT
prior_store="$fixture_root/prior/.local/share/engineering-workstation-bootstrap"
mkdir -p "$fixture_root/path" "$prior_store/versions"
printf 'retained\n' > "$prior_store/versions/marker"
printf '{}\n' > "$fixture_root/activation.json"
export TRANCHE_FIXTURE_ROOT="$fixture_root"
# Route any home references in the entrypoint to the fixture without changing HOME.
export TRANCHE_FIXTURE_HOME="$fixture_root/prior"
python3 - "$fixture_root/installer.sh" <<'PY'
from pathlib import Path
import sys
source = Path('install.sh').read_text()
Path(sys.argv[1]).write_text(source.replace('${HOME}', '${TRANCHE_FIXTURE_HOME}').replace('$HOME', '$TRANCHE_FIXTURE_HOME'))
PY
cat > "$fixture_root/path/uname" <<'SCRIPT'
#!/usr/bin/env bash
printf 'Darwin\n'
SCRIPT
cat > "$fixture_root/path/gh" <<'SCRIPT'
#!/usr/bin/env bash
if [[ "$1" == auth ]]; then exit 0; fi
[[ "${TRANCHE_CLONE_FAIL:-0}" == 0 ]] || exit 31
mkdir -p "$4/bin"
printf '%s\n' "$4" > "$TRANCHE_FIXTURE_ROOT/source-path"
cat > "$4/bin/workstation-bootstrap" <<'ENTRY'
#!/usr/bin/env bash
[[ "$1" == install ]] || exit 32
[[ -f "$WORKSTATION_ACTIVATION_CONTRACT" ]] || exit 33
printf 'invoked\n' > "$TRANCHE_FIXTURE_ROOT/invoked"
exit "${TRANCHE_INSTALL_EXIT:-0}"
ENTRY
SCRIPT
chmod 755 "$fixture_root/path/"*
for failure in 0 37; do
  actual=0
  PATH="$fixture_root/path:$PATH" WORKSTATION_ACTIVATION_CONTRACT="$fixture_root/activation.json" \
    TRANCHE_INSTALL_EXIT="$failure" bash "$fixture_root/installer.sh" >/dev/null || actual=$?
  [[ "$actual" == "$failure" ]]
  [[ -f "$fixture_root/invoked" && ! -e "$(cat "$fixture_root/source-path")" ]]
  [[ "$(cat "$prior_store/versions/marker")" == retained ]]
done
if PATH="$fixture_root/path:$PATH" WORKSTATION_ACTIVATION_CONTRACT="$fixture_root/activation.json" \
  TRANCHE_CLONE_FAIL=1 bash "$fixture_root/installer.sh" >/dev/null 2>&1; then exit 1; fi
printf 'PASS: installer source staging, error propagation and cleanup\n'

mkdir -p "$fixture_root/package/bin" "$fixture_root/profile.assets"
printf '{}\n' > "$fixture_root/profile.json"
printf 'asset\n' > "$fixture_root/profile.assets/asset.txt"
cat > "$fixture_root/package/bin/workstation-bootstrap" <<'SCRIPT'
#!/usr/bin/env bash
[[ "$1" == install ]] || exit 40
jq -n --arg contract "$WORKSTATION_ACTIVATION_CONTRACT" \
  --arg profile "${WORKSTATION_PRIVATE_PROFILE:-}" --arg source "$0" \
  '{contract:$contract,profile:$profile,source:$source}' > "$TRANCHE_FIXTURE_ROOT/launch.json"
exit "${TRANCHE_INSTALL_EXIT:-0}"
SCRIPT
tar -czf "$fixture_root/launcher.tar.gz" -C "$fixture_root" package
archive_sha="$(shasum -a 256 "$fixture_root/launcher.tar.gz" | awk '{print $1}')"
profile_sha="$(shasum -a 256 "$fixture_root/profile.json" | awk '{print $1}')"
for overlay in public private; do
  mkdir -p "$fixture_root/drive-$overlay"
  drive="$(cd "$fixture_root/drive-$overlay" && pwd -P)"
  jq -n --arg drive "$drive" --arg sha "$archive_sha" --arg profile "$profile_sha" \
    '{schemaVersion:1,publicationAuthorized:true,authorityReference:"fixture:launcher",
      driveRoot:$drive,version:"fixture",archiveSha256:$sha,privateProfileSha256:$profile}' > "$fixture_root/publication.json"
  args=()
  [[ "$overlay" != private ]] || args=(--private-profile "$fixture_root/profile.json")
  bash bin/workstation-publish-drive --publication-contract "$fixture_root/publication.json" \
    --drive-root "$drive" --version fixture --archive "$fixture_root/launcher.tar.gz" "${args[@]}" >/dev/null
  jq '.version="fixture-2"' "$fixture_root/publication.json" > "$fixture_root/publication-2.json"
  bash bin/workstation-publish-drive --publication-contract "$fixture_root/publication-2.json" \
    --drive-root "$drive" --version fixture-2 --archive "$fixture_root/launcher.tar.gz" "${args[@]}" >/dev/null
  [[ "$(readlink "$drive/Tony Workstation Bootstrap/current")" == releases/fixture-2 ]]
  release="$drive/Tony Workstation Bootstrap/current"
  bash "$release/START_TONY_WORKSTATION_BOOTSTRAP.command" "$fixture_root/activation.json" >/dev/null
  [[ "$(jq -r .contract "$fixture_root/launch.json")" == "$fixture_root/activation.json" ]]
  [[ ! -e "$(jq -r .source "$fixture_root/launch.json")" ]]
  if [[ "$overlay" == private ]]; then
    [[ "$(jq -r .profile "$fixture_root/launch.json")" == */private/profile.json ]]
    printf 'tampered\n' >> "$release/private/profile.assets/asset.txt"
    rm "$fixture_root/launch.json"
    if bash "$release/START_TONY_WORKSTATION_BOOTSTRAP.command" "$fixture_root/activation.json" >/dev/null 2>&1; then exit 1; fi
    [[ ! -f "$fixture_root/launch.json" ]]
  else
    [[ "$(jq -r .profile "$fixture_root/launch.json")" == '' ]]
    actual=0
    TRANCHE_INSTALL_EXIT=43 bash "$release/START_TONY_WORKSTATION_BOOTSTRAP.command" "$fixture_root/activation.json" >/dev/null || actual=$?
    [[ "$actual" == 43 && ! -e "$(jq -r .source "$fixture_root/launch.json")" ]]
  fi
done
printf 'PASS: generated public/private launchers, extraction cleanup, install failure and checksum rejection\n'
