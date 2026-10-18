#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/lib/connector_fabric_tests.py"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/lib/capability_map_tests.py"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT/lib/source_preflight_tests.py"
node --test "$ROOT/lib/workstation_skills_preflight.test.mjs"
