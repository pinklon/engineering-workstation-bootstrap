#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT

mkdir -p "$fixture_root/.github/workflows" "$fixture_root/manifests"
cp "$ROOT/mise.toml" "$ROOT/Brewfile" "$fixture_root/"
cp "$ROOT/manifests/cloud.json" "$ROOT/manifests/homebrew.json" "$fixture_root/manifests/"
cp "$ROOT/.github/workflows/validate.yml" "$fixture_root/.github/workflows/"

python3 "$ROOT/lib/runtime_truth.py" --root "$fixture_root"
python3 - "$fixture_root/manifests/cloud.json" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
manifest = json.loads(path.read_text())
manifest["nodeMajor"] -= 1
path.write_text(json.dumps(manifest) + "\n")
PY
if python3 "$ROOT/lib/runtime_truth.py" --root "$fixture_root" >"$fixture_root/out" 2>"$fixture_root/error"; then
  printf 'FAIL: runtime drift was accepted\n' >&2
  exit 1
fi
rg -q 'manifests/cloud.json nodeMajor is.*expected.*from mise.toml' "$fixture_root/error"
printf 'PASS: runtime truth validation rejects declaration drift\n'
