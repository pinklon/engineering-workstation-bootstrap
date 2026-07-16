export PATH="$HOME/bin:$PATH"
export CODEX_BROWSER_GATE_ROOT="$HOME/.local/share/codex-tools/browser-gate"
export PLAYWRIGHT_BROWSERS_PATH="$CODEX_BROWSER_GATE_ROOT/browsers"
if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate zsh)"
fi
