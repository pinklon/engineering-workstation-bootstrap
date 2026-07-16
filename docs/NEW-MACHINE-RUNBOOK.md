# New Machine Runbook

## 1. Start with Terminal

Confirm internet access and the local administrator password. Do not paste scripts line by line into interactive `zsh`; save scripts as files or run the repository commands exactly as documented.

## 2. Install Xcode Command Line Tools

```bash
xcode-select -p >/dev/null 2>&1 || xcode-select --install
```

Complete the macOS dialog, then reopen Terminal.

## 3. Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Apply the shell initialization line printed by Homebrew.

## 4. Install GitHub CLI

```bash
brew install git gh
```

## 5. Authenticate GitHub

```bash
gh auth login --hostname github.com --git-protocol ssh --web
gh auth setup-git
```

Complete browser OAuth and MFA. This enrolls the local CLI only. It does not configure Cloudflare, CI, connected apps, or Git transport by magic, because those are separate security planes.

## 6. Clone the bootstrap repository

```bash
mkdir -p "$HOME/Developer"
gh repo clone pinklon/engineering-workstation-bootstrap \
  "$HOME/Developer/engineering-workstation-bootstrap"
cd "$HOME/Developer/engineering-workstation-bootstrap"
```

## 7. Run the guided bootstrap

```bash
./bin/workstation-bootstrap install
```

The bootstrap installs declared packages, configures managed fragments, enrolls required providers, configures Playwright, clones declared repositories, and runs the full doctor.

## 8. Complete human checkpoints

The bootstrap may pause for:

- macOS administrator approval
- GitHub OAuth or MFA
- SSH key passphrase and provider approval
- Cloudflare OAuth or MFA

No script should bypass or persist those approvals in Git.

## 9. Validate

```bash
workstation-doctor --full
github-auth-doctor
cloudflare-auth-doctor
browser-gate-python -c 'import playwright; print("Playwright import OK")'
```

## 10. Reconcile later

```bash
workstation-bootstrap reconcile
```

Reconcile is designed to be rerunnable. Managed fragments are copied to `~/.config/engineering-workstation-bootstrap`; user configuration files receive only stable include or source lines.

## Recovery

If bootstrap stops, use the exact remediation it prints. Do not export a broad PAT globally as a universal fix. Repair the failed authentication plane specifically.
