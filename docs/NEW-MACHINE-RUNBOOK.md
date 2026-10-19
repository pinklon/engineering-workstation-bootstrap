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
brew install git gh jq
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

## 7. Issue a local activation contract

Activation is deliberately separate from repository or package validation. Create
a contract bound to the physical home path and the package version:

```bash
jq -n --arg home "$(cd "$HOME" && pwd -P)" \
  '{schemaVersion:1,activationAuthorized:true,allowLiveHome:true,
    authorityReference:"owner-issued-local-contract",targetHome:$home,
    version:"0.2.0",manageSkillRoots:false}' > "$HOME/Downloads/workstation-activation.json"
```

Set `manageSkillRoots` only when a local private profile has inventoried and
checksum-bound every user-managed active skill entrypoint. The reserved Codex
`.system` subtree is classified per top-level entry in the same activation
contract's `codexSystemSkills` array, rather than exported as private-profile
skill wrappers. Record the exact subtree fingerprint, evidence and owner
authority for each verified OpenAI built-in or owner-managed entry to preserve.
An explicitly retired governor/VSOK entry can be excluded only with its cleanup
authority and fingerprint; unknown entries block activation. An empty array is
valid only when the subtree has no entries. Verify retained and excluded entries,
plus the exact rollback backup, in a disposable projection before any live
activation. See [skill discovery](TONY-WORKSTATION-V2.md#skill-discovery) for
the contract fields and provenance rules.
Regenerate older private profiles that listed `.system` built-ins as ordinary
skills; activation rejects those duplicates.

An owner may optionally pin a **verified account-supported Codex model** for a
single managed activation by adding `codexModel` to that same exact activation
contract. For example, after an independent, authenticated disposable CLI probe
succeeds with a specific model ID, add `codexModel` with that exact ID. The
renderer replaces only the root Codex `model` value in the new, rollback-protected
release; it preserves `model_reasoning_effort`, MCP/provider configuration and
unrelated user-owned settings. Without `codexModel`, the previous model is
preserved. Model availability is product/account-specific: API-model existence
alone is not proof that a ChatGPT-signed-in Codex CLI can use it. Never update
files through the live managed `~/.codex/config.toml` symlink directly.

## 8. Run the guided bootstrap

```bash
WORKSTATION_ACTIVATION_CONTRACT="$HOME/Downloads/workstation-activation.json" \
  bash bin/workstation-bootstrap install
```

The bootstrap installs declared packages, configures managed fragments, enrolls required providers, configures Playwright, clones declared repositories, and runs the full doctor.

## 9. Complete human checkpoints

The bootstrap may pause for:

- macOS administrator approval
- GitHub OAuth or MFA
- SSH key passphrase and provider approval
- Cloudflare OAuth or MFA

No script should bypass or persist those approvals in Git.

## 10. Validate

```bash
workstation-doctor --full
workstation-toolsets doctor
browser-gate-python -m playwright --version
```

## 11. Reconcile or roll back later

```bash
WORKSTATION_ACTIVATION_CONTRACT="$HOME/Downloads/workstation-activation.json" \
  workstation-bootstrap reconcile
workstation-rollback --latest
```

Reconcile is designed to be rerunnable. Managed fragments resolve through the
versioned `current` pointer; user shell content receives one stable source line.
Rollback restores the recorded file, directory, and symlink pre-state rather than
guessing what existed before activation.

## Recovery

If bootstrap stops, use the exact remediation it prints. Do not export a broad PAT globally as a universal fix. Repair the failed authentication plane specifically.
