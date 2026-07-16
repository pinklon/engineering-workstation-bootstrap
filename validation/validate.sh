#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

printf 'Validating shell syntax...\n'
while IFS= read -r file; do bash -n "$file"; done < <(find bin bootstrap packaging validation -maxdepth 2 -type f | sort)
bash -n install.sh

if command -v shellcheck >/dev/null 2>&1; then
  printf 'Running ShellCheck...\n'
  shellcheck -e SC1090,SC1091 install.sh bin/* bootstrap/*.sh packaging/*.sh validation/validate.sh
else
  printf 'WARN: shellcheck unavailable; CI must provide it.\n'
fi

printf 'Validating secret exclusions...\n'
if grep -RInE --exclude-dir=.git --exclude-dir=dist --exclude='validate.sh' '(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----|CLOUDFLARE_API_TOKEN=|GH_TOKEN=|GITHUB_TOKEN=)' .; then
  printf 'FAIL: possible credential material found.\n' >&2
  exit 1
fi

printf 'Validating executable examples...\n'
if grep -RInE --exclude-dir=.git --exclude-dir=dist --exclude='validate.sh' '(/path/to|<repository-path>|CHANGEME)' .; then
  printf 'FAIL: executable placeholder found.\n' >&2
  exit 1
fi

printf 'Validating dry run...\n'
bash bin/workstation-bootstrap dry-run

printf 'Validating package build...\n'
bash packaging/build-package.sh 0.0.0-validation
[[ -s dist/engineering-workstation-bootstrap-0.0.0-validation.tar.gz ]]
[[ -s dist/engineering-workstation-bootstrap-0.0.0-validation.tar.gz.sha256 ]]

printf 'PASS: repository validation\n'
