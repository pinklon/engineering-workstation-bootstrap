# GitHub readiness observations

Authority: Workstation issue #6. This is the GitHub portion of provider readiness;
Cloudflare, Supabase and complete capability profiles remain separate work.

`bash bin/github-auth-doctor` retains a human-readable, no-argument entry point for
`make auth-doctor` and `workstation-doctor`. It reads the selected host's Git
protocol through `gh config get git_protocol`. HTTPS selection does not require an
SSH identity. Select a transport explicitly when the configuration is unknown:

```sh
bash bin/github-auth-doctor --transport https --format json
bash bin/github-auth-doctor --hostname code.example.test --transport ssh
bash bin/github-auth-doctor --repository example/project --require-admin --check-webhooks --format json
```

The doctor observes the installed CLI version and authenticated API user using a
GET request. With an explicit repository it separately observes repository read
access and the boolean admin permission. Admin absence is blocking only with
`--require-admin`. `--check-webhooks` performs a GET of at most one webhook; an
empty list is healthy read access. It neither creates a webhook nor proves
webhook write authority. The doctor never invokes login, token, refresh, install,
resource creation or permission-changing commands. Authentication status is not
used as a blanket capability check. In particular, GitHub CLI JSON auth status
can exit zero even when authentication fails ([upstream documentation](https://cli.github.com/manual/gh_auth_status)).

SSH uses existing host trust, agent/default keys, strict host-key checking and
`UpdateHostKeys=no`. It ignores SSH configuration to avoid ProxyCommand,
LocalCommand and connection-sharing side effects. A host alias, proxy or custom
identity that depends on that configuration is not qualified by this check.
The SSH greeting must match the observed API identity. Neither a missing host key
nor a mismatch enrolls trust or edits configuration; it remains unknown and
requires separate diagnosis.

Every subprocess has a five-second total deadline (configurable with `--timeout`,
0.1–30 seconds) and a 64 KiB combined stdout/stderr ceiling. Timeout or output
excess kills the subprocess group. Captured output stays in memory and is never
forwarded, logged to disk or included verbatim in the receipt. JSON fields are
projected explicitly; identity and CLI version have strict syntax checks.
Arguments are validated before any probe. Errors do not echo rejected arguments.

The JSON receipt includes observation time, selected transport, version, validated
identity, capability state, sanitized evidence command, remediation, human-action
certainty and blocking selected checks. `ready` means only that the selected
checks passed. It is not task authority or a preview/production readiness grant.
The receipt explicitly leaves HTTPS Git transport, keyring custody, token scope
summary, GitHub App operator authority and provider write authority unverified.
An environment token presence is reported as a custody type, never its value.
No credential file is inspected to infer keyring custody. A 401 is unauthenticated;
403/404 remain unknown because rate limits, SSO and hidden repositories can produce
those responses. Ambiguous or malformed output never becomes ready.

Exit status is 0 for passing selected checks, 1 for nonready observations and 2
for invalid options. No arguments still select human output and configured
transport. macOS and Linux execution use POSIX process groups. Native Windows
execution is unqualified and fails closed; it needs its own bounded-process
implementation and fixtures before acceptance.

## Deterministic qualification

Both commands below are required. `make validate` currently does **not** include
the GitHub doctor fixtures; it cannot replace the first command. The shared
validation dispatcher is outside this change's accepted writer scope.

```sh
python3 -B validation/github-auth-doctor-fixtures.py
make validate
```

The focused fixtures use an isolated PATH with local command doubles and a
throwaway home. They check positive identity, selected HTTPS/SSH, mismatch,
secret-like and malformed output, missing tools, hung and flooding processes,
repository permissions, empty/nonempty webhook responses, enterprise host
selection, unchanged home contents and invocation from an extracted-package
layout containing spaces. They never use real credentials, SSH or provider APIs.
The dedicated workflow runs the focused fixture on macOS and Linux, independently
of the existing shared validation dispatcher. A passing source fixture is not an
installed workstation or live credential receipt. Roll back the source change
with a reviewed revert; any future managed installation uses its own existing
activation and rollback contract.
