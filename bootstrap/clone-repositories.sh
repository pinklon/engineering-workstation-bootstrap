#!/usr/bin/env bash
set -euo pipefail
PROFILE="${1:-mac-studio}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_ROOT="${WORKSTATION_REPO_ROOT:-$HOME/Developer}"
mkdir -p "$DEST_ROOT"
while IFS='|' read -r repo directory profiles; do
  [[ -z "$repo" || "$repo" == \#* ]] && continue
  [[ ",$profiles," == *",$PROFILE,"* || "$profiles" == "all" ]] || continue
  target="$DEST_ROOT/$directory"
  if [[ -d "$target/.git" ]]; then
    printf 'PASS  Repository exists: %s\n' "$target"
  elif [[ -e "$target" ]]; then
    printf 'FAIL  Target exists but is not a Git repository: %s\n' "$target" >&2
    exit 1
  else
    gh repo clone "$repo" "$target"
  fi
done < "$ROOT/manifests/repositories.txt"
