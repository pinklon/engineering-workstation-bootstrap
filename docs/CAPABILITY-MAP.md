# Capability map (generated)

Generated from `manifests/connector-capabilities.json#route_observation`.
Do not edit this view. The projection is descriptive and its review evidence
is pending source receipts. A candidate route is not a permission grant.

| Route | Observation | Availability | Read | Write | Admin | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| surface.dot-cloud | tested | observed_available | tested | tested_local_scratch_only | unknown | Workstation #18; Cloud #11 qualification |
| surface.mac-studio | discovered | connected_metadata | unknown | unknown | unknown | Workstation #18 / Mac custodian |
| surface.hyperion | discovered | directory_online | unknown | unknown | unknown | Workstation #34; Skills #323 |
| surface.ghostmesh-vps | discovered | directory_online | unknown | unknown | unknown | Control Tower #1023 / existing fleet runner |
| surface.bootstrap-cloud | discovered | saved_configuration_only | unknown | unknown | unknown | Cloud #11 |
| surface.mc-cloud | discovered | saved_configuration_only | unknown | unknown | unknown | Cloud #11 / Mission Control incumbent |
| route.dc-directory | discovered | observed_available | tested_metadata_only | unknown | unknown | Desktop Commander connector custodian |
| route.dc-command | unknown | unknown | unknown | unknown | unknown | Device/task custodian |
| connector.github | tested | observed_available | tested | unknown | unknown | Portfolio Agent Bootstrap #15 auth; Workstation #18 contract |
| connector.slack | tested | observed_available | parent_verified | unknown | unknown | Slack connector custodian |
| connector.cloudflare | unknown | unknown | unknown | unknown | unknown | Cloudflare provider custodian; Workstation #18 |
| connector.netlify | tested | historical_success | unknown | historical_parent_verified | unknown | Netlify publication owner |
| service.reasonpack | unknown | unknown | unknown | unknown | unknown | Existing service custodian; unresolved |
| service.brain | unknown | unknown | unknown | unknown | unknown | Existing service custodian; unresolved |
| service.atlas | unknown | unknown | unknown | unknown | unknown | Existing service custodian; unresolved |
| service.mission-control | discovered | parent_reported_legacy_active | unknown | unknown | unknown | Mission Control source/runtime incumbents |
| service.slack-ingestion | tested | historical_success | historical_parent_verified | unknown | unknown | Service ingestion custodian |
| service.gmail-ingestion | tested | historical_success | historical_parent_verified | unknown | unknown | Service ingestion custodian |

## Route detail

### surface.dot-cloud

- Task classes: stdlib-computation, portable-source-test, connector-read
- Hardware: none declared
- Dependencies: OpenAI task runtime, platform connector custody, authorized scratch
- Failure domains (inferred): openai-task-control-plane, platform-connectors, workspace-scratch
- Evidence: cloud-probe, cloud-probe-local
- Limits: Python 3.12.14; Node 24.19.0; Git 2.52.0; Not linux-cloud-core Python 3.13; Allowlisted shell network; Restart and failover unproven; No GPU or private-network readiness established

### surface.mac-studio

- Task classes: desktop-local
- Hardware: macos
- Dependencies: Mac power/network, task transport
- Failure domains (inferred): mac-host, task-transport
- Evidence: mac
- Limits: Connected status is not execution proof; Task-specific grant required

### surface.hyperion

- Task classes: host-specific, gpu
- Hardware: hyperion
- Dependencies: Hyperion power/network, scoped host authentication
- Failure domains (inferred): hyperion-host, task-transport, scoped-host-auth
- Evidence: dc, fleet-handoff
- Limits: Directory online only; GPU tool use, restore and role qualification unproven

### surface.ghostmesh-vps

- Task classes: admitted-service
- Hardware: vps
- Dependencies: VPS, existing runner control plane
- Failure domains (inferred): vps-host, runner-control-plane
- Evidence: dc, services
- Limits: No new command witness; Scratch admission and recovery unproven; Task 15 privileged executor unassigned

### surface.bootstrap-cloud

- Task classes: fresh-cloud-task
- Hardware: none declared
- Dependencies: OpenAI cloud provisioner, repository binding, task-scoped source access
- Failure domains (inferred): openai-task-control-plane, repository-binding, task-scoped-source-auth
- Evidence: cloud-gap
- Limits: Saved configuration is not a running executor; Cold exact-artifact review and skill consumption unproven

### surface.mc-cloud

- Task classes: fresh-cloud-task
- Hardware: none declared
- Dependencies: OpenAI cloud provisioner, repository binding, task-scoped source access
- Failure domains (inferred): openai-task-control-plane, repository-binding, task-scoped-source-auth
- Evidence: cloud-gap
- Limits: Saved configuration is not a running executor; Task 15 source and PR 131 executor are separate

### route.dc-directory

- Task classes: device-inventory
- Hardware: none declared
- Dependencies: none declared
- Failure domains (inferred): desktop-commander-service
- Evidence: dc
- Limits: Not an executable command route; Online does not prove shell, auth or tools

### route.dc-command

- Task classes: none qualified
- Hardware: none declared
- Dependencies: none declared
- Failure domains (inferred): desktop-commander-service, device-task-auth
- Evidence: dc
- Limits: Directory result does not qualify command route

### connector.github

- Task classes: repository-read, issue-read
- Hardware: none declared
- Dependencies: GitHub, platform connector auth
- Failure domains (inferred): github-service, platform-connectors
- Evidence: github, contract
- Limits: Mutation tool names do not prove hard read-only enforcement; Exact source review needs pinned commit and bytes

### connector.slack

- Task classes: owner-conversation-read
- Hardware: none declared
- Dependencies: Slack, platform connector auth
- Failure domains (inferred): slack-service, platform-connectors
- Evidence: slack
- Limits: No standing send grant; Resolve exact conversation at use time

### connector.cloudflare

- Task classes: none qualified
- Hardware: none declared
- Dependencies: Cloudflare, surface-specific credentials
- Failure domains (inferred): cloudflare-service, surface-specific-auth
- Evidence: contract
- Limits: Direct connector absent on observed surface; Local authentication unknown; no global outage inference

### connector.netlify

- Task classes: none qualified
- Hardware: none declared
- Dependencies: Mac route, Netlify auth, exact site/release authority
- Failure domains (inferred): netlify-service, mac-host, site-grant
- Evidence: netlify
- Limits: Historical deploy is not current grant or connection proof

### service.reasonpack

- Task classes: none qualified
- Hardware: none declared
- Dependencies: service-specific host/auth/data sources unresolved
- Failure domains (inferred): service-host-unknown, service-auth-unknown
- Evidence: services
- Limits: No per-service health or invocation witness

### service.brain

- Task classes: none qualified
- Hardware: none declared
- Dependencies: service-specific host/auth/data sources unresolved
- Failure domains (inferred): service-host-unknown, service-auth-unknown
- Evidence: services
- Limits: No per-service health or invocation witness

### service.atlas

- Task classes: none qualified
- Hardware: none declared
- Dependencies: service-specific host/auth/data sources unresolved
- Failure domains (inferred): service-host-unknown, service-auth-unknown
- Evidence: services
- Limits: No per-service health or invocation witness

### service.mission-control

- Task classes: none qualified
- Hardware: none declared
- Dependencies: existing MC service/data pipeline, separate privileged execution custody
- Failure domains (inferred): mission-control-runtime, privileged-executor
- Evidence: services, merges
- Limits: Task 15 source prep is not privileged executor assignment; Merged MC 77 is not runtime deployment proof; Preserve PR 131 incumbent

### service.slack-ingestion

- Task classes: none qualified
- Hardware: none declared
- Dependencies: existing bounded ingestion service
- Failure domains (inferred): service-ingestion-runtime
- Evidence: service-slack
- Limits: Checkpoint 819649 is historical; no full coverage or latency proof

### service.gmail-ingestion

- Task classes: none qualified
- Hardware: none declared
- Dependencies: existing bounded ingestion service
- Failure domains (inferred): service-ingestion-runtime
- Evidence: service-slack
- Limits: Checkpoint 1309 is historical; no full coverage or latency proof

Freshness: availability 300 seconds, authenticated read 900 seconds,
inventory 86400 seconds. These intervals are proposed, not an installed
monitor. Null or expired time and indirect evidence block route selection.
Task authority, exact target, current grants and required hardware are
checked separately. Historical success cannot authorize a write or admin action.

Installed fleet adoption, automatic failover and physical-outage recovery
remain separate, unproven gates. Cloud #11 owns real hosted qualification;
Skills #323 owns versioned skill bindings and actual consumption.
