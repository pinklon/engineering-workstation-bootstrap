#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT
mkdir -p "$fixture_root/runtime/bin" "$fixture_root/runtime/manifests" "$fixture_root/path"
cp "$ROOT/bin/workstation-toolsets" "$fixture_root/runtime/bin/"
cat > "$fixture_root/runtime/manifests/homebrew.json" <<'JSON'
{"schemaVersion":1,"packages":[{"kind":"brew","name":"fixture-runtime","command":"workstation-fixture-runtime","versionArgs":["--version"]}]}
JSON
cat > "$fixture_root/path/workstation-fixture-runtime" <<'SCRIPT'
#!/usr/bin/env bash
[[ "$1" == --version ]] || exit 2
printf 'fixture runtime 1.0\n'
SCRIPT
chmod 755 "$fixture_root/path/workstation-fixture-runtime"
PATH="$fixture_root/path:$PATH" bash "$fixture_root/runtime/bin/workstation-toolsets" doctor > "$fixture_root/healthy.log"
rg -q 'PASS  workstation-fixture-runtime: fixture runtime 1.0' "$fixture_root/healthy.log"

# A discoverable executable can fail before any repository code runs.
cat > "$fixture_root/path/workstation-fixture-runtime" <<'SCRIPT'
#!/usr/bin/env bash
printf 'dyld: Library not loaded: fixture-library\n' >&2
printf 'fixture-private-diagnostic-must-not-escape\n' >&2
exit 127
SCRIPT
if PATH="$fixture_root/path:$PATH" bash "$fixture_root/runtime/bin/workstation-toolsets" doctor > "$fixture_root/broken.log" 2>&1; then
  printf 'FAIL: doctor accepted an executable with a broken shared library\n' >&2
  exit 1
fi
rg -q 'required shared library could not load' "$fixture_root/broken.log"
if rg -q 'fixture-private-diagnostic-must-not-escape' "$fixture_root/broken.log"; then exit 1; fi

rm "$fixture_root/path/workstation-fixture-runtime"
if PATH="$fixture_root/path:$PATH" bash "$fixture_root/runtime/bin/workstation-toolsets" doctor > "$fixture_root/missing.log" 2>&1; then
  printf 'FAIL: doctor accepted a missing executable\n' >&2
  exit 1
fi
rg -q 'FAIL  workstation-fixture-runtime missing' "$fixture_root/missing.log"
printf 'PASS: healthy, broken-library, and missing-tool startup fixtures\n'
