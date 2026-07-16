# Packaging and Distribution

## Objective

Provide a downloadable, versioned package for operators who should not need to clone the repository manually. The package contains executable bootstrap logic, manifests, documentation, and validation. It never contains credentials or provider state.

## Package format

Initial distribution uses a signed or checksum-verified tarball:

```text
engineering-workstation-bootstrap-<version>.tar.gz
engineering-workstation-bootstrap-<version>.tar.gz.sha256
```

This format is transparent, portable across supported macOS hosts, easy to inspect, and does not require an Apple Developer ID. A native `.pkg` may be added later after the install locations, upgrade model, rollback behavior, signing identity, and notarization requirements stabilize.

## Build locally

```bash
bash packaging/build-package.sh 0.1.0
```

Artifacts are created under `dist/`.

## Install from a downloaded archive

```bash
mkdir -p "$HOME/Downloads/engineering-workstation-bootstrap"
tar -xzf "$HOME/Downloads/engineering-workstation-bootstrap-0.1.0.tar.gz" \
  -C "$HOME/Downloads/engineering-workstation-bootstrap"
cd "$HOME/Downloads/engineering-workstation-bootstrap/engineering-workstation-bootstrap-0.1.0"
bash bin/workstation-bootstrap install
```

Verify the checksum before extraction:

```bash
cd "$HOME/Downloads"
shasum -a 256 -c engineering-workstation-bootstrap-0.1.0.tar.gz.sha256
```

## GitHub release model

A version tag matching `v*` triggers the release workflow. The workflow:

1. Validates the repository.
2. Builds the deterministic archive.
3. Generates a SHA-256 checksum.
4. Uploads both artifacts to the GitHub release.

The workflow must not deploy providers, create credentials, or include local state.

## Installer options

### Option A: private repository clone

Best for Tony's authenticated engineering hosts. It preserves branch history and allows reconcile operations through Git.

### Option B: release archive

Best for controlled download and installation without a working local checkout. Authentication is still required for private release access and subsequent private repository cloning.

### Option C: public bootstrap loader

A minimal public loader could install Homebrew and GitHub CLI, authenticate the operator, then download the private package. It must contain no private repository inventory, account identifiers, secrets, or production configuration.

### Option D: native macOS package

A signed and notarized `.pkg` is appropriate only after the installation contract stabilizes. It adds Apple signing, notarization, package receipts, privileged installer behavior, and uninstall obligations. Starting there would produce a beautifully polished maintenance burden before the bootstrap contract has earned it.

## Upgrade and rollback

- `workstation-bootstrap reconcile` applies the current declared state.
- Existing user files are not replaced wholesale.
- Managed fragments live under `~/.config/engineering-workstation-bootstrap`.
- Every run produces a receipt.
- A future package version must document schema changes and any migration steps.

## Security controls

Packages must exclude:

- `.git`
- `.env` files
- OAuth or Wrangler state
- SSH private keys
- Keychain exports
- local receipts
- repository working data
- provider account secrets

Release checksums protect integrity. Future public distribution should add artifact signing and provenance attestations.
