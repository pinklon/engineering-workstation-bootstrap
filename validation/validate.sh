#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

printf 'Validating shell syntax...\n'
while IFS= read -r file; do bash -n "$file"; done < <(find bin bootstrap packaging validation -maxdepth 2 -type f | sort)
bash -n install.sh
python3 - <<'PY'
import ast, pathlib
for path in pathlib.Path('lib').glob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
PY

printf 'Validating generated Homebrew manifest parity...\n'
bash bin/workstation-toolsets brewfile | cmp - Brewfile
bash validation/toolsets-fixtures.sh
bash validation/portability-fixtures.sh
bash validation/cloud-apt-fixtures.sh

if command -v shellcheck >/dev/null 2>&1; then
  printf 'Running ShellCheck...\n'
  shellcheck -e SC1090,SC1091 install.sh bin/* bootstrap/*.sh packaging/*.sh validation/*.sh
else
  printf 'WARN: shellcheck unavailable; CI must provide it.\n'
fi

printf 'Validating secret exclusions...\n'
if grep -RInE --exclude-dir=.git --exclude-dir=.local --exclude-dir=dist --exclude='validate.sh' '(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----|CLOUDFLARE_API_TOKEN=|GH_TOKEN=|GITHUB_TOKEN=)' .; then
  printf 'FAIL: possible credential material found.\n' >&2
  exit 1
fi

printf 'Validating executable examples...\n'
if grep -RInE --exclude-dir=.git --exclude-dir=.local --exclude-dir=dist --exclude='validate.sh' '(/path/to|<repository-path>|CHANGEME)' .; then
  printf 'FAIL: executable placeholder found.\n' >&2
  exit 1
fi

printf 'Validating public-release language...\n'
if grep -RInE --exclude-dir=.git --exclude-dir=.local --exclude-dir=dist --exclude='validate.sh' '(SharePlane|WESS|remote-codex-host|CODEX_BROWSER_GATE_ROOT|codex-tools|pinklon-shareplane-next|wess-service-experience-and-knowledge)' .; then
  printf 'FAIL: private-project coupling or legacy product-specific language found.\n' >&2
  exit 1
fi

printf 'Validating dry run...\n'
bash bin/workstation-bootstrap dry-run

printf 'Validating v2 staged fixtures...\n'
bash validation/v2-fixtures.sh

printf 'Validating package build...\n'
bash packaging/build-package.sh 0.0.0-validation
[[ -s dist/engineering-workstation-bootstrap-0.0.0-validation.tar.gz ]]
[[ -s dist/engineering-workstation-bootstrap-0.0.0-validation.tar.gz.sha256 ]]

printf 'PASS: repository validation\n'
