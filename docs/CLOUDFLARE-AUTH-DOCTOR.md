# Cloudflare offline observation classifier

Authority: Workstation issue #6. This tranche replaces the old exit-code-only
Cloudflare doctor with an offline classifier. It executes no Wrangler command,
subprocess probe, network request or credential discovery. It creates no
provider resource or credential mechanism.

The previous wrapper treated human-format `wrangler whoami` exit zero as healthy
authentication and read access. Upstream human whoami can instead print that the
user is unauthenticated and return normally. Moreover, its API/account path can
invoke login/refresh behavior, conflicting with #6's no-automatic-refresh rule.
A local double reproduced the false-success behavior; no real provider probe was
needed. The relevant upstream source was pinned at
`d8899ac4c85ff839d73daa9055a76a36248cd2e3`:

- [Human/JSON whoami semantics](https://github.com/cloudflare/workers-sdk/blob/d8899ac4c85ff839d73daa9055a76a36248cd2e3/packages/wrangler/src/user/whoami.ts)
- [Credential resolution before API calls](https://github.com/cloudflare/workers-sdk/blob/d8899ac4c85ff839d73daa9055a76a36248cd2e3/packages/wrangler/src/cfetch/internal.ts)
- [Account lookup and login/refresh](https://github.com/cloudflare/workers-sdk/blob/d8899ac4c85ff839d73daa9055a76a36248cd2e3/packages/workers-auth/src/core/factory.ts)

## Use and status

```sh
bash bin/cloudflare-auth-doctor --format json
bash bin/cloudflare-auth-doctor --input observations.json --format json
```

With no input, every capability is UNKNOWN and no tool is executed, even when
Wrangler is installed or credential environment variables exist. Existing
no-argument callers still work, but they now receive a nonready exit instead of
an unproved success. This changes readiness reporting and is intentional; a
future installation requires its own reviewed rollout decision.

An explicit input is a regular UTF-8 JSON file no larger than 64 KiB. Devices,
FIFOs, final-component symlinks, changed inputs, duplicate object keys and invalid
schemas are refused. No input path is discovered automatically. Supply only
observations captured under an existing authorized route, never a credential
store. The classifier does not establish provenance, freshness or authority for
supplied content.

Example synthetic envelope:

```json
{
  "schemaVersion": 1,
  "observations": [
    {
      "capability": "authentication",
      "format": "wrangler-json",
      "exitCode": 0,
      "stdout": "{\"loggedIn\":false}",
      "stderr": ""
    }
  ]
}
```

Each capability may appear once. Supported capability names are
`authentication`, `r2-bucket-list`, `pages-project-list` and
`worker-deployments`. Formats are `wrangler-human`, `wrangler-json` and
`cloudflare-api-json`. An optional `reason` is `completed`, `missing-tool`,
`timeout`, `output-limit` or `launch-failed`.

Human text plus exit zero is always ambiguous. Wrangler JSON authentication
requires an exact boolean `loggedIn`; `false` reports unauthenticated and only
`true` plus exit zero reports ready. A successful Pages/Workers JSON list can
report list-read readiness. Cloudflare API JSON requires exact boolean success
and the supported result shape (R2 `result.buckets`, Pages `result`, Workers
`result.deployments`, each an array of objects). Empty arrays are healthy reported
read observations. R2 structured error code 10042 is provider-not-enabled and
10003 is insufficient-permission; contradictory or generic errors remain
unknown. Codes appearing only in free text, or in another capability's response,
do not establish R2 entitlement. See the [official R2 error mapping](https://developers.cloudflare.com/r2/api/error-codes/).

All results remain **unverified offline evidence**. `reportedState` describes
only the supplied observation. Each row's actual `state` stays `unknown`;
root `ready` and `authorityGranted` remain false. `classifiedAt` is the time of
classification, not the time of a runtime probe. `inputSha256` identifies input
bytes without asserting their origin. Raw text, account names, email addresses,
tokens, paths and provider response details are never forwarded into receipts.

Exit 1 means current runtime readiness is unverified, including when every
supplied observation reports ready. Exit 2 means invalid arguments or unsafe /
invalid input. This tranche never returns healthy exit 0. An accepted observer
with a no-refresh contract and independently bound fresh evidence is required
before runtime readiness can be qualified. This closes the false-green report;
it does not complete #6's live multi-provider capability profiles.

## Qualification and rollback

Both commands are required; the shared validation dispatcher does not include
the focused fixture and is outside this source scope:

```sh
python3 -B validation/cloudflare-auth-doctor-fixtures.py
make validate
```

The dedicated workflow runs focused tests on macOS/Linux. Fixtures trap every
potential provider command with local doubles and use only synthetic files.
They verify input guards, separate reported/runtime states, secret-free output,
repeatability and invocation from an extracted package layout containing spaces.
Native Windows file guards remain unqualified and fail closed. Source rollback
is a reviewed revert. Any future host installation uses the existing managed
activation/rollback receipt; no host is activated by these tests.
