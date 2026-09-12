#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${WORKSTATION_BOOTSTRAP_BROWSER_ROOT:-$HOME/.local/share/engineering-workstation-bootstrap/browser-gate}"
PYTHON="${WORKSTATION_BROWSER_PYTHON:-python3}"
MODE="${1:-setup}"
[[ "$MODE" == setup || "$MODE" == --check ]] || { printf 'Usage: configure-browser-gate.sh [setup|--check]\n' >&2; exit 64; }
LOCKFILE="$REPO/manifests/browser-requirements.txt"
key="$("$PYTHON" - "$LOCKFILE" <<'PY'
import hashlib, pathlib, platform, sys
if sys.version_info < (3, 10):
    raise SystemExit('Browser setup requires Python 3.10 or newer.')
identity = (sys.version + platform.platform() + str(pathlib.Path(sys.executable).resolve())).encode()
print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes() + identity).hexdigest())
PY
)"

healthy() {
  local candidate="$1"
  [[ -x "$candidate/venv/bin/python" && -f "$candidate/requirements.txt" ]] || return 1
  cmp -s "$LOCKFILE" "$candidate/requirements.txt" || return 1
  [[ -f "$candidate/runtime-key" && "$(cat "$candidate/runtime-key")" == "$key" ]] || return 1
  "$candidate/venv/bin/python" - "$LOCKFILE" <<'PY' || return 1
import importlib.metadata, pathlib, sys
for line in pathlib.Path(sys.argv[1]).read_text().splitlines():
    if line and not line[0].isspace() and not line.startswith('#'):
        name, version = line.split()[0].split('==')
        if importlib.metadata.version(name) != version:
            raise SystemExit('Browser dependency version mismatch: ' + name)
PY
  PLAYWRIGHT_BROWSERS_PATH="$candidate/browsers" "$candidate/venv/bin/python" "$REPO/lib/browser-smoke.py"
}

if healthy "$ROOT/current" >/dev/null 2>&1; then
  printf 'PASS: locked Playwright/Chromium runtime is healthy; no installation or download\n'
  exit 0
fi
if [[ "$MODE" == --check ]]; then
  printf 'FAIL: browser runtime is missing, drifted or cannot launch. Run the reviewed browser setup during provisioning.\n' >&2
  exit 1
fi

mkdir -p "$ROOT/versions"
lock="$ROOT/setup.lock"
mkdir "$lock" 2>/dev/null || { printf 'Browser setup is already locked; inspect the owning run before retrying.\n' >&2; exit 1; }
candidate=''
cleanup() {
  [[ -z "$candidate" ]] || rm -rf "$candidate"
  rmdir "$lock"
}
trap cleanup EXIT
# Keep prior versions usable until a new runtime has passed a real launch.
candidate="$(mktemp -d "$ROOT/versions/runtime.XXXXXX")"
"$PYTHON" -m venv "$candidate/venv"
PIP_DISABLE_PIP_VERSION_CHECK=1 "$candidate/venv/bin/python" -m pip install \
  --require-hashes --only-binary=:all: -r "$LOCKFILE"
mkdir -p "$candidate/browsers"
browser_args=(install chromium)
if [[ "${WORKSTATION_BROWSER_INSTALL_DEPS:-0}" == 1 ]]; then browser_args+=(--with-deps); fi
PLAYWRIGHT_BROWSERS_PATH="$candidate/browsers" "$candidate/venv/bin/python" -m playwright "${browser_args[@]}"
cp "$LOCKFILE" "$candidate/requirements.txt"
printf '%s\n' "$key" > "$candidate/runtime-key"
healthy "$candidate"
"$PYTHON" - "$ROOT/current" "$candidate" <<'PY'
import os, pathlib, sys
current, candidate = map(pathlib.Path, sys.argv[1:])
if current.exists() and not current.is_symlink():
    raise SystemExit('Refuse to replace a non-symlink browser current path.')
temporary = current.with_name('current.next.' + str(os.getpid()))
try:
    temporary.symlink_to(candidate.resolve())
    os.replace(temporary, current)
finally:
    temporary.unlink(missing_ok=True)
PY
candidate=''
printf 'PASS: locked browser runtime activated; prior versions retained\n'
