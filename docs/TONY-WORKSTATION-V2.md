# Tony Workstation Bootstrap v2

The committed package stays portable and secret-free. Endpoint-specific skill
sources, utility implementations, aliases, functions, optional MCP names, and
non-secret paths are captured by `workstation-private-profile` into an ignored
JSON profile plus a sibling asset bundle. The profile records environment names,
classes, and origins but never secret values.

## Transaction boundary

`workstation-activate` refuses to run without a JSON activation contract bound to
the physical target home, exact version, authority reference, and private-profile
checksum when a private profile is selected. A live home additionally requires
`allowLiveHome: true`.

Before any managed path changes, activation creates:

- a versioned release under `~/.local/share/engineering-workstation-bootstrap/versions/`;
- a pre-state inventory and backup manifest under `~/.local/state/engineering-workstation-bootstrap/backups/`;
- recoverable copies of every replaced file, directory, and symlink;
- an activation receipt whose state advances from `applying` to `active` only after doctor passes.

The stable `current` symlink is the atomic version boundary. Shell fragments and
named utility wrappers resolve through it. User `.zshrc` content is retained and
receives exactly one managed source line.

If the post-activation doctor fails, activation invokes `workstation-rollback`.
Rollback restores every manifest-listed pre-state path, the preceding version
pointer, and the preceding transaction identity. Backups and receipts remain for
audit.

## Skill discovery

The private-profile generator inventories only valid skill entrypoints. During
activation it copies full source packages to `skill-library`, outside both active
discovery roots, and generates one frontmatter-valid wrapper per enabled skill.
Internal layers remain available to their loader but are never scanned as
standalone skills. Duplicate names are canonicalized during inventory.

## Codex and optional MCP state

The renderer preserves unrelated existing Codex settings and routes routine
workspace-sandbox approval requests through Codex automatic review. The managed
global instructions permit already-authorized routine work while retaining
explicit stops for destructive, credential, permission, production/public-release,
settings, and unresolved semantic boundaries.

An unhealthy optional MCP is rendered with `enabled = false` and `auth-required`
state in the private profile. Its URL, bearer-token environment-variable name,
OAuth store, and credentials are preserved. Required MCP failures remain hard
doctor failures rather than being silently removed.

## Endpoint reconciliation

The generator resolves aliases and functions from the login shell, inventories
their concrete utility sources and dependencies, and leaves unresolved commands
unresolved rather than inventing implementations. Generate the local bundle with:

```bash
make private-profile
```

The default output is `.local/tony-private-profile.json` plus
`.local/tony-private-profile.assets/`. Both are ignored by Git.

## Drive publication

`workstation-publish-drive` requires a publication contract bound to the Drive
root, version, archive checksum, and private-profile checksum when present. It
creates immutable `releases/<version>/`, durable `receipts/`, and an atomically
replaced `current` symlink. The current release contains the launcher, archive,
manifest, checksums, version, read-first instructions, and optional private
profile bundle.

Repository validation and Drive fixture tests use temporary paths. They never
write the effective home, Keychain/OAuth stores, active command links, or a real
Drive `current` location.
