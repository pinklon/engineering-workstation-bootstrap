# Source-only owner briefing and native skill adoption

The communication rule in `config/codex/AGENTS.md` adds the accepted Owner
Change Brief to future managed instruction releases. It preserves the existing
routine execution and consequential-action boundaries. An instruction or skill
entrypoint is guidance, not evidence that a particular session loaded it.

This source change does not activate a workstation, change a default skill
footprint, modify approval/security settings, or install a private plugin. Existing
work and installed immutable releases must be preserved.

## Reviewed source identity

The bounded native candidate is the ten files under
`plugins/ghostmesh-mesh-status/skills/mesh-status/` in `pinklon/skills` at
`74f73bca1cf375fbb151f7d338bb8589b7145a7c`. Its renderer source is
`54fdfabceeaf2aa9e0736d34e92867a514859b60`; the policy snapshot is the accepted
Owner Change Brief 1.1.0 from `d112a1a4f4cad0d781d9a47cff83570ad2a5e5e5`.
Policy SHA-256:
`c35e5cd285612aae98d018a59262f10049ec3cb8849b33176d996f65ca87bcbe`.

Native payload: `SKILL.md`, `CHANGELOG.md`, `RUNTIME_CONTEXT.md`, `manifest.json`,
`report.py`, `impact.py`, `impact-fixture.json`, `work-impact.schema.json`,
`owner-operating-model.contract.json`, `test_straight_talk_report.py`.
Do not copy the whole private repository, plugin marketplace files, credentials,
account settings, or unrelated authorities into a native skill root. Do not call a
candidate canonical default-branch source before its separately authorized merge.

## Preparation using existing managed tools

1. The single admitted source owner records the exact current source and installed
   release, profile, package hashes, original managed instructions and rollback
   transaction. Use an isolated current checkout; preserve any staged checkout.
2. Generate a fresh private inventory with the existing
   `workstation-private-profile inventory` command, using its allowed temporary
   or repository `.local/` output. Preserve its existing skill entries, task-scoped
   packages, utilities, shell and MCP metadata. Stop on an unexpected profile or
   package difference. Never commit that private profile or its host paths.
3. Verify the reviewed Skills commit and existing closed-package validator, then
   copy only the ten native files into the private profile's assets directory.
   Reject missing, extra, symlinked or changed package members. Record every raw
   file hash, including the policy pin above. Reject a conflicting existing
   `mesh-status` identity rather than overwriting a newer or different package.
4. Append exactly one ordinary profile entry with `name: mesh-status`, the staged
   relative `sourceDir`, `installRoot: codex-skills`, and `state: enabled`.
   Other profile fields and package contents remain unchanged. This entry is a
   proposed enrollment; it does not authorize installation or data-source access.
5. Bind the candidate profile SHA-256 to the existing activation contract for a
   disposable-home rehearsal with `allowLiveHome: false`. Exercise the ordinary
   managed wrapper, local payload copy and exact rollback. Verify source hashes
   again before any later live transaction: the existing profile checksum binds
   profile JSON, not every referenced asset file. Do not mistake these asset
   checks for a new installer-enforced authenticated source gate.

The native package's closed local policy/impact/schema imports must work after
the original staging directory is unavailable. Source tests and a disposable
fixture prove mechanics; they do not establish real model instruction following,
authenticated outcome evidence or fleet-wide consumption.

## Separately approved installation and rollback

After source acceptance, the existing managed-release owner prepares one exact
version, target home, current private profile, source/payload hashes and retained
predecessor/backup manifest. The actual activation contract must refer to that
scoped owner decision. Preserve the effective model, config semantics, MCP and
approval/security settings and every unrelated standing/task-scoped package.
Resolve safe transition with current owners; never terminate their sessions or
edit an installed immutable symlink target in place.

Use the existing `workstation-activate` transaction and its own exact receipt;
rollback uses `workstation-rollback --receipt` for that transaction and target.
Prepare and rehearse the concrete command only after all paths, hashes, target
and current authority are resolved. No executable live cutover is supplied here.

After promotion, independently verify the installed instruction and ten payload
hashes, wrapper target, existing package/config parity, and actual fresh-session
loading. Invoke the skill with authorized current input and check its real output:
seven report sections, qualified facts separate from owner-declared context,
unsupported lifecycle/action evidence UNKNOWN, privacy preserved and no execution
authority. Record installed, loaded, invoked, consumed and output states separately.
CLI, GUI, cloud, web/mobile and each required role remain separate consumers.
ChatGPT private-plugin installation is a different supported client route.

Failed or uncertain preservation, loading, runtime identity or rollback must leave
the candidate held and identify the existing accepting owner. Never promote a
synthetic test or a root report invocation into universal adoption.

## Interrupted managed transitions

New transactions use `recoveryProtocol: 1` in the existing activation receipt.
The installer seals and syncs all preimages and candidate file pins before
publishing a durable intent. Pointer, transaction marker and each managed path
have explicit transition phases; the interrupted path is recorded before removal.
Recovery restores that path first, then the remaining paths, pointer and marker.
It copies preimages instead of consuming backups, so an interrupted rollback can
be repeated with the same exact receipt.

Recovery accepts only the recorded predecessor/candidate pointer and marker
pairs and matching managed path material. Missing or changed backups, changed
candidate files, unrelated managed content or custody, and an unowned automatic
request refuse before restoration. A failed recovery reports `REQUIRES_OWNER`
and retains `recovery-required` rather than claiming completion. Automatic
recovery belongs to the parent activation's lock; manual recovery acquires the
ordinary lock. A stale lock is an explicit owner blocker, never removed by this
protocol. A committed active receipt is not undone by a later notification error.

The controlled fixtures exercise ordinary errors and non-ERR process exits at
publication and rollback boundaries, plus corruption and custody refusals.
They do not attest survival of arbitrary power loss, a forced process kill,
concurrent unmanaged home edits, or real session loading. Such uncertainty stays
held for the existing owner. Completed legacy receipts retain their prior normal
rollback behavior; this repair does not retrofit installed immutable releases.
Activation authorization, live-home authorization and all security settings are
unchanged. The complete source rollback reverts this seven-path recovery delta,
including removal of the two added files, to the accepted source predecessor.
