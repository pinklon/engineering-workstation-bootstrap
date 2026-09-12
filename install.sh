#!/usr/bin/env bash
set -euo pipefail

REPO="pinklon/engineering-workstation-bootstrap"
BRANCH="main"

[[ -f "${WORKSTATION_ACTIVATION_CONTRACT:-}" ]] || {
  printf 'REFUSE: set WORKSTATION_ACTIVATION_CONTRACT before the installer changes live workstation state.\n' >&2
  exit 64
}

printf 'Engineering Workstation Bootstrap\n\n'

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf 'This entry point currently supports macOS. Use docs/NEW-MACHINE-RUNBOOK.md for other profiles.\n' >&2
  exit 2
fi

# A source checkout must never replace the managed release/version store.
checkout_root="$(mktemp -d "${TMPDIR:-/tmp}/workstation-source.XXXXXX")"
trap 'rm -rf "$checkout_root"' EXIT

if command -v gh >/dev/null 2>&1 && gh auth status --hostname github.com >/dev/null 2>&1; then
  gh repo clone "$REPO" "$checkout_root/repo" -- --branch "$BRANCH" --depth 1
else
  printf 'GitHub CLI authentication is not available yet.\n'
  printf 'Install Homebrew and GitHub CLI first, then authenticate with:\n'
  printf '  gh auth login --hostname github.com --git-protocol ssh --web\n\n'
  printf 'Private repository bootstrap cannot continue anonymously.\n'
  exit 3
fi

bash "$checkout_root/repo/bin/workstation-bootstrap" install "$@"
