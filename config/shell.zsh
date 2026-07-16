export PATH="$HOME/bin:$PATH"
export WORKSTATION_BOOTSTRAP_BROWSER_ROOT="$HOME/.local/share/engineering-workstation-bootstrap/browser-gate"
export PLAYWRIGHT_BROWSERS_PATH="$WORKSTATION_BOOTSTRAP_BROWSER_ROOT/browsers"
if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate zsh)"
fi
