#!/usr/bin/env bash
set -euo pipefail
ROOT="${CODEX_BROWSER_GATE_ROOT:-$HOME/.local/share/codex-tools/browser-gate}"
VENV="$ROOT/venv"
BROWSERS="$ROOT/browsers"
mkdir -p "$ROOT" "$BROWSERS"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/python" -m pip install playwright
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$VENV/bin/python" -m playwright install chromium
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$VENV/bin/python" - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content('<title>browser-gate-ok</title>')
    assert page.title() == 'browser-gate-ok'
    browser.close()
print('PASS: Playwright Chromium gate')
PY
