# Linux cloud setup and commissioning

This adapter provisions the `linux-cloud-core` profile in a supported Ubuntu
container. It does not create an account or a Codex cloud environment. Cloud
settings must select Python 3.13 and Node 22 before setup runs. The doctor refuses
a mismatched or broken runtime instead of installing another copy behind it.

For this repository, configure these commands in the environment:

| Setting | Value |
|---|---|
| Image | Supported Ubuntu image; versions are declared in `manifests/cloud.json` |
| Python | 3.13 |
| Node | 22 |
| Setup script | `bash bin/workstation-cloud setup` |
| Maintenance script | `bash bin/workstation-cloud maintenance` |
| Verification | `bash bin/workstation-cloud doctor` then `make validate` |

Setup installs only missing declared OS tools. It uses the selected Ubuntu
repositories and records actual versions; these packages are not byte-pinned.
The browser environment uses exact Python package versions and PyPI wheel hashes.
Playwright selects its matching Chromium builds. A healthy unchanged browser
runtime is reused without package installation or browser download. A changed
lock or runtime identity creates a separate candidate, and the current pointer
changes only after browser startup and DOM execution pass. Failed candidates are
removed; previous successful versions remain available.

Provisioning needs network access to the image's package repositories, PyPI and
Playwright browser downloads, plus noninteractive administrator access if OS
packages or browser system libraries are missing. Do not use those setup needs
as a reason to grant unrestricted network access during agent work.

The live universal image can include an LLVM repository that the setup proxy
does not allow. This core profile does not use LLVM. When that source exists,
bootstrap creates its own APT source view excluding that repository and supplies
it through `APT_CONFIG`. Image source files, Ubuntu snapshot selection and
signature verification remain unchanged. All other source failures still fail
provisioning. In a fresh reviewed checkout, use `mise trust mise.toml` when the
image's shell requires trust for that specific runtime declaration. Browser state
comes from the selected profile, not from a repository-wide mise environment override.

The state directory defaults to
`$HOME/.local/share/engineering-workstation-bootstrap/cloud`. Set
`WORKSTATION_CLOUD_ROOT` in environment settings to choose another persistent
container path. Setup and agent phases have separate shells, so temporary shell
exports in a setup script are not a durable configuration mechanism. Use
`bin/workstation-cloud` for readiness; to use its browser wrapper, configure
`WORKSTATION_BOOTSTRAP_BROWSER_ROOT` to the cloud state directory's `browser`
subdirectory in environment settings.

`readiness.json` records selected executable paths, versions, manifest and browser
lock digests, and pending capabilities. It deliberately keeps
`liveCloudCommissioned` and `publicationCleared` false. The optional Codex and
Claude CLI checks report executable availability only. This core profile does
not install or authenticate a second coding agent inside the managed agent's
container. The macOS profile declares both CLIs; cloud account enrollment and
additional agent hosting require separate qualification.

## Live acceptance

After obtaining authenticated environment settings, bind the intended repository
and reviewed scripts. Launch a cold task and a warm follow-up, retain their Git
changes and receipts, then repeat a representative workflow with the personal
workstation unavailable. Confirm repo access, effective non-secret permissions,
needed network destinations, dependency refresh and durable results. Credentials
belong in the platform's supported authentication/secret custody mechanisms.
Do not copy workstation keychains, OAuth stores, SSH private keys or `.env` files.

The hosted Linux and macOS jobs qualify these scripts and real browser startup.
They do not prove that an owner's Codex environment or agent account has been
commissioned. Provider capability checks remain under issue #6. PII models and
the final publication-content gate remain under issue #9.

Sources: [Codex cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environment),
[Playwright browser dependencies](https://playwright.dev/python/docs/browsers).
