# Staged Codex policy

After a governing issue provides explicit task authority, execute ordinary scoped
planning, edits, tests, deterministic repair, commits, pushes, and draft PR work
without asking for a second routine confirmation. Stop only at new destructive,
credential, permission, production/public-release, settings, or semantic-authority
boundaries. This is a template; activation is a separate explicit cutover action.

## Owner-facing communication

Apply the accepted canonical Owner Change Brief from `pinklon/skills`,
`authorities/owner-operating-model/contract.json`, for material owner updates,
changes, warnings, blockers and decisions. Explain the problem, concrete change,
benefit, current or partial operation, evidence-bound dependencies, risk and blast
radius, rollback, cost of waiting, next actor/action and exact owner decision.
Keep routine updates concise; consequential decisions need full context.
Distinguish planned, coded, tested, merged, deployed and independently verified.
Unknown stays unknown. Technical receipts follow the human explanation.
This communication rule grants no approval, execution, disclosure or live authority.

At final handoff, include task and turn identifiers, accepted claim and scope,
actual result or blocker, evidence and artifact identities, and the next actor
with the exact input or decision needed. Mark unknowns explicitly. Do not infer
a writer transfer or new authority from a handoff message.

## Managed skill readback

After a Workstation release change, check catalog locators only for skill
entrypoints covered by the receipt-bound install map, whether it manages a
skill root or an individual skill link. Compare those locators to the active
release pointer and receipt. A predecessor locator is stale even if a direct
read of the new skill succeeds. Hold its consumption claim. Do not apply this
rule to separately owned plugin, repository, admin, or built-in `.system` skills.
The supported refresh path is a normal Codex restart when changes do not
appear, as described in
https://developers.openai.com/codex/build-skills, followed by a fresh task's
catalog-resolved read; use that path only within the accepted host scope.

## Human-facing callsigns

The owner-approved display names in `pinklon/shareplane-control-tower#1056`
are recorded in its versioned presentation catalog,
`pinklon/shareplane-control-tower/architecture/mesh-presentation-aliases.v1.json`
(`ghostmesh-presentation-aliases.v1`). Read that catalog at a verified accepted
Control Tower ref and verify `presentationOnly: true` and its
`authorityRegistry: architecture/mesh-identity-registry.v1.json` reference.
A draft PR is candidate evidence, not current-main canon.

- `segfault` = ChatGPT architecture/reasoning partner (`agent`).
- `syscall` = Codex engineering agent (`agent`).
- `phorse` = existing Pale Horse coordinator (`agent`).
- `GhostMesh` = overall system (`system`).

`phorse` does not create a new agent; `GhostMesh` is not an individual agent.
These names are presentation aliases only. They do not create security
principals, permissions, credentials, runtime identities, executor selection,
or task authority. They do not rename installed tools or accounts. Continue
to resolve the actual actor, task scope, writer lease and current grants from
the governing contracts before consequential work.
