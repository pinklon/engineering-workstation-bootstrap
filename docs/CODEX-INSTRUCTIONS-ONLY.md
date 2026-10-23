# Managed Codex instructions only

Workstation #18 owns this source path. It is for a separately approved managed
instruction update when the active release must otherwise remain byte-for-byte
unchanged. It does not enroll credentials, install Skills, rewrite shell or Codex
configuration, or invoke `workstation-activate`.

## Linux first install when no managed release exists

`bin/workstation-instructions first-install-preflight` is the read-only entry
point for a Linux user's existing Codex profile. It checks the exact Workstation
instruction commit and SHA-256, accepted Control Tower catalog commit and Git
blob, target home and authority contract. It reports `FIRST_INSTALL_READY` only
when `~/.codex` is a real directory and all three managed footprints are absent:
`~/.codex/AGENTS.md`, the Workstation managed state root, and the Workstation
managed share root. A regular file, even a broken symlink, or any partial release,
pointer, marker, receipt, or backup under either root is a hold for the existing
host custodian. Do not delete or overwrite it to force first-install.

The exact-home JSON contract has only `schemaVersion:1`,
`linuxFirstInstallAuthorized:true`, `allowLiveHome`, `authorityReference`,
`targetHome`, `version`, `workstationCommit`, `workstationInstructionSha256`,
`catalogCommit`, and `catalogBlobSha1`. The host custodian binds the actual
source and catalog checkouts, home and owner-approved scope before execution.
No live-host contract is shipped in this repository. Both commands take
`--contract`, `--home`, `--workstation-repo`, and `--catalog-repo`:

```text
bin/workstation-instructions first-install-preflight --contract CONTRACT.json --home HOME --workstation-repo WORKSTATION_CHECKOUT --catalog-repo CONTROL_TOWER_CHECKOUT
bin/workstation-instructions first-install --contract CONTRACT.json --home HOME --workstation-repo WORKSTATION_CHECKOUT --catalog-repo CONTROL_TOWER_CHECKOUT
```

The first-install command repeats the preflight before writing. Under the
existing activation lock, it stages a minimal versioned release with only the
pinned `config/codex/AGENTS.md`, seals an **absent** one-path preimage and exact
rollback code, then publishes the `current` pointer, transaction marker and
`~/.codex/AGENTS.md` link. The receipt binds source, catalog, release, backup
manifest and rollback hashes. It leaves existing Codex config, Skills, shell,
services and other home paths untouched. This is an instruction-only foothold,
not a full Workstation install or Linux capability qualification. On failure
after receipt intent, the same receipt recovery removes the managed link,
pointer and marker. The release and receipts remain as audit evidence.

Rollback requires the exact activation receipt and the matching reviewed
source checkout:

```text
bin/workstation-instructions rollback --receipt ACTIVATION_RECEIPT.json --home HOME
```

The rollback refuses a changed writer marker, changed candidate bytes or
changed recovery code; it restores the previously absent instruction path and
pointer/marker. If it reports `recovery-required`, keep its receipt and hand the
host to the current custodian. A fresh Codex context must still prove that the
new instruction file is loaded and consumed. A Linux host doctor, source versus
actual inventory, privileged setup and off-host restore remain separate gates.
`validation/instruction-only-fixtures.py` exercises both the existing update
and Linux first-install against disposable homes; `make validate` runs it.

## Chosen transaction

`bin/workstation-instructions install` requires a private, exact-home contract
and two local Git checkouts containing the approved Workstation and Control Tower
commits. It reads `config/codex/AGENTS.md` from the pinned Workstation commit and
the presentation-only catalog from the pinned Control Tower commit. It verifies
the instruction SHA-256, the catalog Git blob, and the catalog fields and aliases.

Under the existing activation lock, it verifies the active release receipt,
transaction marker, managed `~/.codex/AGENTS.md` symlink, and instruction
preimage. It clones that release to a new versioned directory and changes only
the clone's `config/codex/AGENTS.md`. A full entry/mode/link hash comparison
proves that every other staged release entry matches the predecessor. The
existing live managed links are left in place. A sealed one-path backup and
receipt precede an atomic switch of the shared `current` pointer and transaction
marker. All predecessor-managed live paths, new instructions, source release
entries, and prior rollback evidence are checked again before the receipt
becomes active. The general workstation doctor is outside this narrow
transaction because it can touch other managed paths.

The exact receipt records the prior and new instruction hashes, source commits,
catalog blob, prior release and transaction, manifest checksum, and unchanged
tree hash. The previous release and its activation receipt and backup manifest
are retained. The transaction archives the exact rollback entry point and
recovery helper under its backup root, with their hashes in the receipt. Run
`bin/workstation-instructions rollback --receipt ... --home ...` from the
reviewed source checkout. That trusted launcher checks the archived and local
code hashes before recovery. The archived copy is a fallback source; verify its
three receipt hashes from a trusted checkout or system tool **before** executing
it. The currently installed Mac release has an older rollback binary; do not
rely on its `--latest` shortcut for this new receipt. Both install and rollback use the existing
activation lock; an unrelated pointer, marker, changed source, preimage or
managed live path refuses the operation. Unexpected unrelated live-path drift
leaves a `recovery-required` receipt for the host custodian rather than claiming
that the one-path rollback restored it. Interrupted pointer and marker
transitions can be recovered from the exact receipt through this rollback command.

The alternative of changing only the live `~/.codex/AGENTS.md` symlink would
break its existing `current/config/codex/AGENTS.md` contract. The full
`workstation-activate` path replaces other managed links and `.zshrc`, so it is
outside this instruction-only scope.

## Pin and approval inputs for the pending Mac update

- Workstation source commit:
  `61ef7b00644f3b9a764e89a367383852eaf3bb24`.
- Workstation `config/codex/AGENTS.md` SHA-256:
  `3958e270fae881efef41307e8c965a943bceec6886c06857f9ae2c0b7f9fc1af`.
- Control Tower catalog commit:
  `fc7189d27cdf9512c3948b9221c326f7350b1e67`.
- `architecture/mesh-presentation-aliases.v1.json` Git blob:
  `5ebb5ccc39dd1652c72fb3b4a2a38518a6a5aeeb`.
- The selected Mac's last read-only instruction preimage SHA-256 was
  `690d03f17dd2a214983d211062dc13b7191f82f4fb1d4f0e38d1fade710f8bab`.
  Refresh that read and the current release/transaction before issuing the
  exact-home contract. A mismatch blocks installation.

The contract has exactly `schemaVersion:1`, `instructionOnlyAuthorized:true`,
`allowLiveHome`, `authorityReference`, `targetHome`, `version`,
`workstationCommit`, `workstationInstructionSha256`, `catalogCommit`,
`catalogBlobSha1`, `expectedCurrent`, `expectedTransaction`, and
`expectedPreimageSha256`. The designated host custodian must bind these to the
accepted owner scope and observed target; no contract or live execution is
included in this source change. `validation/instruction-only-fixtures.py` uses
only disposable homes and local fixture Git repositories.

This source fixture proves transaction behavior, not installation or fresh
Codex-session consumption on the Mac. After a separately admitted install,
read back the receipt, pointer, marker, active bytes and untouched unrelated
paths, then start a fresh Codex session to check instruction loading. Preserve
the exact rollback receipt until that adoption gate is accepted.
