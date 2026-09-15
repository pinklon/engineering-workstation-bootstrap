# Connector capability contract

`manifests/connector-capabilities.json` extends the existing bootstrap. It is the
capability authority; `manifests/mcp.yaml` retains the older activation policy for
compatibility. A legacy doctor pass does not qualify connector parity.

This is an incomplete qualification implementation. The HTTP, native Codex client,
and scoped GitHub canary adapters are implemented. Desktop restart and hosted
execution still require independent evidence. The doctor
keeps incomplete rows unhealthy. Do not close issue #18
or claim `MESH_CONNECTOR_FABRIC_PARITY_ACTIVE_V1` from these changes.

The contract includes every connector discovered during issue #18 inventory,
including cached plugins with no active tools. The explicit issue #18
OWNER_SCOPE_AMENDMENT makes Figma and Canva OPTIONAL while retaining their
NOT_CONFIGURED / UNAVAILABLE inventory rows. Higgsfield remains REQUIRED.
Tier and health are independent fields; unavailable OPTIONAL connectors do not
block admission. The amendment and previous manifest digest remain in the manifest.
UNQUALIFIED describes an unresolved surface realization; its health is UNAVAILABLE.
Only documented platform limitations justify UNSUPPORTED_ON_SURFACE. Neither state
passes required-profile admission.

## Commands

```bash
bash bin/connector-doctor inventory --output .local/connectors-inventory.json
bash bin/connector-doctor probe --surface local-shell --output .local/connectors-health.json
bash bin/connector-doctor matrix --output .local/connectors-matrix.json
bash bin/render-codex-config --source config/codex/config.toml.template --output .local/candidate-config.toml --connector-profile ghostmesh-core
```

Inventory projects metadata only: connector names, plugin versions and digests,
auth reference names, endpoint hosts and origin paths. It does not open OAuth
databases, Keychain, PEM files, or cloud credential stores. Supply a sanitized
runtime tool-name catalog with `--session-tools` to inventory platform-managed
apps, which cannot be inferred from local configuration. Cached is distinct from
configured, and configured is distinct from authenticated. The inventory explicitly
lists surfaces it cannot inspect. Never treat it as a complete hosted inventory.

Rendering preserves existing config and adds required canonical remote MCP entries
with auth references only. Conflicting endpoint identities stop rendering. Existing
GitHub read-only uses the short-lived `GH_TOKEN` reference supplied by the
existing repository-scoped App launcher; this code does not create a PAT.
Its canary reads issue #18 and verifies its number. The prior `get_me` requirement
was removed because a user-profile operation is not necessary to prove an
authenticated installation-token read. Existing evidence is retained.
Provider OAuth enrollment stays with the client. Do not activate a live home to
test repository changes. Review the candidate through the existing activation and
rollback contract. Repository validation exercises disposable targets only.

The HTTP adapter performs real initialization, paginated tool discovery, a bounded
read, rejection of an absent mutation tool with no target resource, reconnect, and
a read in a fresh login shell. It refuses redirects and credential-bearing URLs,
limits response sizes and timeouts, and suppresses provider response/error bodies.
Credentials remain in memory. Secret checks cover known formats and inherited
secret values. Public documentation authentication is explicitly inapplicable.
Write capability, write canaries and forbidden-write canaries apply only when
the canonical connector declares them. Read-only connectors do not acquire
artificial write requirements; the explicit GitHub hard read-only boundary still
requires mutation-tool exclusion. Receipts expose `check_applicability` separately
from check outcomes so an inapplicable check is never presented as an executed
canary. All applicable checks, including restart, must pass.

These checks establish local shell evidence only. MCP reconnect does not prove a
Desktop restart. MCP-client-managed OAuth is not exported to a shell adapter;
missing supported auth custody leaves that adapter unhealthy.

## Governed GitHub development canary

`connector-doctor github-canary --write-contract FILE --output RECEIPT` invokes the
existing `agent-codex` launcher. The contract contains `repository`, `authority`
(that repository's issue #18 URL), `environment: development`, and a unique
`branch` beginning `codex/issue-18-canary-`. It proves the App installation token
can access exactly one repository, creates an isolated branch, writes a fixed
secret-free file, reads its exact bytes back, and deletes only the branch it
created. Failed cleanup fails the command. It never writes the default branch,
changes repository settings, or substitutes another credential. A canary receipt
is evidence of that operation; it does not independently prove all surface checks.

## Repository admission

`connector-doctor client-probe --surface codex-cli` starts two independent installed
Codex client processes, uses their native MCP transport and platform-managed app
credentials, then compares read identity, server identity and tool inventory.
The same adapter can be invoked independently from `local-shell`, or with
`--surface fresh-repository --repository DIR` after profile initialization. It
never exports the client's OAuth state, runs a model turn, or accepts an imported
healthy receipt. It rejects server approval/authentication requests and records
missing write or forbidden-canary evidence as unhealthy. A native client process
is not a GUI restart or a hosted task; this command refuses those surface labels.

For a targeted GitHub read-only run, use the existing App launcher:

```bash
agent-codex pinklon/engineering-workstation-bootstrap bash bin/connector-doctor client-probe --connector github-readonly --surface codex-cli --output .local/github-readonly.json
```

The adapter verifies a future short-lived expiry and exactly one repository in
`/installation/repositories` before starting the native client. Its temporary
command-line override supplies only the canonical MCP URL and `GH_TOKEN` reference.
It changes no installed configuration. Each targeted run still starts two separate
client processes. Untested rows remain unavailable in that run's complete matrix.

The installed client protocol must expose `mcpServerStatus/list` and
`mcpServer/tool/call`; missing methods fail closed. Every receipt retains the two
process/task identities and actual tool inventory. Configuration-only auth status
does not establish authentication: the canonical provider read must succeed.

```bash
bash bin/connector-doctor init-repository --repository . --profile ghostmesh-core
bash bin/connector-doctor admit --repository . --surface local-shell
```

New repositories receive only `.mesh-profile.json`: a profile name, contract ID,
schema version, and manifest digest. They inherit endpoints from the installed
bootstrap; credentials are never copied. Run admission before consequential work.
Digest drift, extra repository config keys, unknown profiles, missing evidence,
or any failed required check stops admission. A profile declaration alone does
not prove a freshly bootstrapped repository can operate. There is no flag to
accept caller-asserted healthy receipts.

## Hosted realization and evidence

`manifests/connector-hosted-template.json` is the hosted template contract. An
environment ID records provisioning only; `commissioned` remains false until
qualification succeeds. Reuse the existing Linux runtime setup and maintenance
commands from a pinned bootstrap release. The repository checkout supplies the
same capability manifest, skills, and commands; provider credential realizations
belong to the hosted platform. Bind actual environment settings and an exact
source digest before commissioning. Store neither local OAuth databases nor
workstation tokens in the hosted setup.

Use the supported `codex cloud exec --env` interface for hosted canaries and retain
task/environment IDs, exact source identity, cold/warm session evidence and the
returned matrix. [Official CLI documentation](https://learn.chatgpt.com/docs/developer-commands#codex-cloud)
describes `exec`, `list`, and their authentication. A local Linux fixture is not
Codex Cloud proof. Until independent client/hosted adapters and actual execution
evidence exist, their matrix rows remain UNAVAILABLE and admission fails closed.

Receipts are sanitized JSON projections suitable for a runtime control dashboard.
They report health and last-tested facts; the dashboard owns no credentials.
The terminal target cannot be asserted until every required surface is independently
qualified, with explicit unsupported gaps reviewed. This implementation does not
infer parity from matching configuration files or from successful session reads.

## Rollback

No live activation is necessary for these commands. Delete disposable candidates
and repository profile declarations to undo preparation. Existing activated
releases keep using `workstation-rollback --receipt` with their original transaction
receipt. Development canary branches are removed by the canary operation; if
cleanup fails, retain the contract's exact repository/branch for bounded recovery.
