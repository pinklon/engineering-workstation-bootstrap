# Coding agents and publication-security tools

The macOS baseline supports Codex and Claude Code through their official
Homebrew casks. Each agent retains its own authentication, settings, instructions,
and plugin registrations. Installation does not enroll an account, prove model
access, or copy credentials. Claude Code is proprietary software, even though
its public repository contains documentation and supporting material.

`manifests/homebrew.json` is the package declaration. Generate `Brewfile` with:

```bash
bash bin/workstation-toolsets brewfile > Brewfile
```

Repository validation rejects drift between them. `make toolsets-doctor` runs
local version probes for declared executables without starting an agent session
or requesting model inference. The full doctor also calls this check. Homebrew
selects its published stable packages; this does not pin exact package bytes.
Record installed versions when qualifying a workstation and qualify upgrades.
Python and Node runtime consolidation remains separate work.

The doctor executes each declared version command and reports its selected path.
A file found on PATH can still fail to load a shared library. Such failures are
readiness failures, not evidence against the project being tested. The doctor
does not print raw failing-command diagnostics, change PATH, reinstall packages,
or switch silently to a runtime bundled with a coding agent.

For a failing Node installation, first identify the selected binary using
`command -v node` and inventory the Homebrew and mise installations. On macOS,
use `brew linkage --test` for the identified owning formula, then repair that
formula and its missing dependency deliberately. Re-run the startup probe and
the previously blocked project validation. Record runtime ownership and version
so the next shell resolves the same supported runtime. A temporary bundled-runtime
workaround does not qualify the host installation.

## Permissions and fresh-session qualification

Dependency repair and permission prompts have different causes. This bootstrap
already renders Codex with `sandbox_mode = "workspace-write"`,
`approval_policy = "on-request"`, and `approvals_reviewer = "auto_review"`.
Automatic review routes eligible approval requests to a reviewer; it does not
expand filesystem access or enable network access. Installation does not prove
that a running desktop or CLI session uses these settings.

Inspect active session permissions, command-line overrides, trusted project
configuration, selected profiles, user configuration and managed requirements.
Do not dump entire configuration or environment files into a public receipt.
Only record non-secret effective settings needed to explain the result. After
an authorized configuration change, start a fresh session and qualify routine
repository reads, a reversible edit, required tests and a local commit in a
disposable branch under the governing task authority.

For each unexpected prompt, record the action and enforcing layer: agent sandbox,
network policy, protected Git/configuration paths, repository authority, connector
approval, or macOS privacy/administrator controls. Correct a specific mismatch
after establishing its cause. Do not replace this diagnosis with blanket Full
Access, disabled approvals, broadly trusted directories, or copied credentials.
Claude Code needs its own permission and account qualification; Codex settings
do not configure Claude. Native workstation qualification is still pending.

| Capability | Selected tools | State |
|---|---|---|
| Coding agents | Codex CLI, Claude Code CLI | macOS installation declared |
| Shared engineering | Git, gh, jq/yq, ripgrep, mise, Python, Node, uv | Baseline |
| Shell and workflow checks | ShellCheck, shfmt, actionlint, pre-commit | Baseline; hooks need repository configuration |
| Secret detection | Gitleaks | Installed by baseline; release workflow integration pending |
| PDF text and metadata | Poppler, ExifTool | Installed by baseline; extraction coverage needs validation |
| Image text | Tesseract | Installed by baseline; language selection and OCR accuracy need qualification |
| Browser execution | Existing Playwright/Chromium environment | Implemented; version locking and warm reconciliation still need repair |
| Deeper secret detection | TruffleHog | Optional installation; local no-verification mode required |
| PII recognition and redaction | Presidio plus an explicit local NLP model | Pending isolated runtime and representative qualification |
| Confidential business information | Private source-classification rules and disclosure review | Content-owner responsibility; no universal detector |

Application repositories continue to own framework, package-manager, browser,
and build-tool versions in their own manifests and lockfiles. Browser package
versions and browser binaries must match. Cloud execution needs its own Linux
setup and maintenance profile; neither CLI installation nor desktop credentials
provision a cloud environment.

## Publication contract

A successful tool doctor does not make an artifact safe to publish. The existing
publishing workflow must enforce a content gate against the final generated
files before public upload, including public previews. Pre-commit is earlier
feedback and cannot enforce final-build safety alone.

The gate must cover HTML source and rendered text, inline and bundled JS/JSON,
search indexes, comments and attributes, source maps, downloadable packages and
nested archives, metadata, extracted PDF/Office text, and OCR where needed.
External referenced assets, encrypted content, unsupported formats, extraction
failures, depth/size limits, and skipped files must appear as explicit coverage
limitations. Missing required coverage blocks release rather than returning a
clean result.

Separate three decisions: credential exposure, PII disclosure, and confidential
business content. Gitleaks addresses secrets; Presidio helps identify PII but
cannot guarantee all sensitive information will be found. Private rules and
authorized content review address organization-specific confidentiality and
intentional public disclosures.

Keep source files unchanged. Apply approved redactions to a derived release
copy, rebuild, inspect, and scan again. Hiding text with CSS or adding a black
overlay is not redaction if the original remains extractable. Human judgment
must approve changes that alter meaning or disclosure intent.

Receipts must bind the final file inventory and digests, scanner/model/ruleset
versions, coverage, results, and narrowly reviewed exceptions. Any subsequent
artifact change invalidates clearance. Logs and reports must not include raw
secrets, sensitive matched values, private rules, or source snippets. Scanner
output itself needs safe handling; a redaction flag alone is not sufficient
evidence that every report field is safe.

Scanning runs locally without sending content to model services. If optional
TruffleHog is used, disable credential verification and update checks during the
scan (`--no-verification --no-update`), enforce the no-egress execution boundary,
and preserve detection of unverified candidates. Do not use `--only-verified` as
a publication policy. Live verification is a separate authorized provider action.

The implementation must be tested with synthetic findings in final HTML,
embedded data, an archive, metadata and image text. Test missing scanners,
unreadable content, limited traversal, redaction residue, stale receipts and
safe public disclosures. The publication gate and Presidio runtime are not yet
implemented by this tool-installation change.

## Sources

- [Claude Code installation](https://code.claude.com/docs/en/setup)
- [Claude Code license](https://github.com/anthropics/claude-code/blob/main/LICENSE.md)
- [Codex Homebrew cask](https://formulae.brew.sh/cask/codex)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [TruffleHog](https://github.com/trufflesecurity/trufflehog)
- [Presidio](https://github.com/data-privacy-stack/presidio)
- [Playwright browser dependencies](https://playwright.dev/python/docs/browsers)
- [Codex approvals and sandboxing](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Codex automatic approval review](https://learn.chatgpt.com/docs/sandboxing/auto-review)
- [Codex configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic)
- [Homebrew linkage diagnostics](https://docs.brew.sh/Manpage#linkage-options-installed_formula-)
