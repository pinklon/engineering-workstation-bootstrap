#!/usr/bin/env bash

ws_die() {
  printf 'REFUSE: %s\n' "$*" >&2
  exit 64
}

ws_need() {
  command -v "$1" >/dev/null 2>&1 || ws_die "required command is unavailable: $1"
}

ws_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    sha256sum "$1" | awk '{print $1}'
  fi
}

ws_real_dir() {
  (cd "$1" 2>/dev/null && pwd -P)
}

ws_assert_relative_path() {
  case "$1" in
    ''|/*|../*|*/../*|*/..|.) ws_die "unsafe managed relative path: $1" ;;
  esac
}

ws_assert_under_home() {
  local target_home="$1" path="$2"
  case "$path" in
    "$target_home"/*) ;;
    *) ws_die "managed path escapes target home: $path" ;;
  esac
}

ws_remove_exact_path() {
  local target_home="$1" path="$2"
  ws_assert_under_home "$target_home" "$path"
  if [[ -L "$path" || -f "$path" ]]; then
    rm -f "$path"
  elif [[ -d "$path" ]]; then
    rm -rf "$path"
  fi
}

ws_path_type() {
  local path="$1"
  if [[ -L "$path" ]]; then printf 'symlink'
  elif [[ -f "$path" ]]; then printf 'file'
  elif [[ -d "$path" ]]; then printf 'directory'
  elif [[ -e "$path" ]]; then printf 'other'
  else printf 'absent'
  fi
}

ws_secret_pattern() {
  printf '%s' '((^|[^A-Za-z0-9])(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----|(^|[^A-Za-z])(TOKEN|SECRET|PASSWORD|API_KEY)[[:space:]]*=[[:space:]]*[^$<{[:space:]][^[:space:]]*)'
}
