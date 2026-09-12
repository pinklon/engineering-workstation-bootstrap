#!/usr/bin/env bash
set -euo pipefail
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT
export WORKSTATION_BOOTSTRAP_BROWSER_ROOT="$fixture_root/browser"
export WORKSTATION_BROWSER_PYTHON
WORKSTATION_BROWSER_PYTHON="$(command -v python3)"
if [[ "$(uname -s)" == Linux ]]; then export WORKSTATION_BROWSER_INSTALL_DEPS=1; fi

bash bootstrap/configure-browser-gate.sh setup
first="$(readlink "$fixture_root/browser/current")"
# Unchanged warm setup must work with package index and browser downloads unavailable.
PIP_NO_INDEX=1 PLAYWRIGHT_DOWNLOAD_HOST=http://127.0.0.1:9 \
  bash bootstrap/configure-browser-gate.sh setup
[[ "$(readlink "$fixture_root/browser/current")" == "$first" ]]
bash bootstrap/configure-browser-gate.sh --check

# A modified lock plus an unavailable package must fail and preserve the prior runtime.
mkdir -p "$fixture_root/modified/bootstrap" "$fixture_root/modified/manifests" "$fixture_root/modified/lib"
cp bootstrap/configure-browser-gate.sh "$fixture_root/modified/bootstrap/"
cp lib/browser-smoke.py "$fixture_root/modified/lib/"
cp manifests/browser-requirements.txt "$fixture_root/modified/manifests/"
printf '\nworkstation-synthetic-missing-package==0.0.0 --hash=sha256:%064d\n' 0 >> "$fixture_root/modified/manifests/browser-requirements.txt"
if PIP_NO_INDEX=1 bash "$fixture_root/modified/bootstrap/configure-browser-gate.sh" setup > "$fixture_root/failed-install.log" 2>&1; then exit 1; fi
[[ "$(readlink "$fixture_root/browser/current")" == "$first" ]]
bash bootstrap/configure-browser-gate.sh --check
[[ "$(find "$fixture_root/browser/versions" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" == 1 ]]

mv "$first/runtime-key" "$first/runtime-key.removed"
if bash bootstrap/configure-browser-gate.sh --check >/dev/null 2>&1; then exit 1; fi
mv "$first/runtime-key.removed" "$first/runtime-key"
bash bootstrap/configure-browser-gate.sh --check
printf 'PASS: real browser cold/warm setup, missing coverage, and failed upgrade preservation\n'
