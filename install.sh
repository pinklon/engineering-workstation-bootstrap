#!/usr/bin/env bash
set -euo pipefail

REPO="pinklon/engineering-workstation-bootstrap"
BRANCH="main"
ROOT="${HOME}/.local/share/engineering-workstation-bootstrap"

[[ -f "${WORKSTATION_ACTIVATION_CONTRACT:-}" ]] || {
  printf 'REFUSE: set WORKSTATION_ACTIVATION_CONTRACT before the installer changes live workstation state.\n' >&2
  exit 64
}

printf 'Engineering Workstation Bootstrap\n\n'

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf 'This entry point currently supports macOS. Use docs/NEW-MACHINE-RUNBOOK.md for other profiles.\n' >&2
  exit 2
fi

mkdir -p "$(dirname "$ROOT")"
rm -rf "$ROOT.new"
mkdir -p "$ROOT.new"

if command -v gh >/dev/null 2>&1 && gh auth status --hostname github.com >/dev/null 2>&1; then
  gh repo clone "$REPO" "$ROOT.new/repo" -- --branch "$BRANCH" --depth 1
else
  printf 'GitHub CLI authentication is not available yet.\n'
  printf 'Install Homebrew and GitHub CLI first, then authenticate with:\n'
  printf '  gh auth login --hostname github.com --git-protocol ssh --web\n\n'
  printf 'Private repository bootstrap cannot continue anonymously.\n'
  exit 3
fi

rm -rf "$ROOT"
mv "$ROOT.new/repo" "$ROOT"
exec bash "$ROOT/bin/workstation-bootstrap" install "$@"
