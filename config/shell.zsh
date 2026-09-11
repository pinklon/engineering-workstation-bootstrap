typeset -U path PATH
path=("$HOME/bin" "$HOME/.local/bin" $path)
export WORKSTATION_BOOTSTRAP_BROWSER_ROOT="$HOME/.local/share/engineering-workstation-bootstrap/browser-gate"
export PLAYWRIGHT_BROWSERS_PATH="$WORKSTATION_BOOTSTRAP_BROWSER_ROOT/browsers"
for workstation_fragment in environment aliases functions prompt; do
  workstation_file="$HOME/.config/engineering-workstation-bootstrap/${workstation_fragment}.zsh"
  [[ -r "$workstation_file" ]] && source "$workstation_file"
done
unset workstation_fragment workstation_file
if command -v mise >/dev/null 2>&1; then
  eval "$(mise activate zsh)"
fi
