# VersionWeaver architecture

## Context

The platform must work for an individual developer and a platform team without trusting a low-cost
host with arbitrary repository execution. It must support dependency and AI-model changes through
one workflow and remain deployable on any container platform.

## Final MVP architecture

```text
CLI / CI / future UI
        |
        v
FastAPI control plane ---------------------- PostgreSQL
  auth, policy, audit                         source of truth
        |                                          |
        +--------------- job lease table ----------+
                              |
                     self-hosted runner
                              |
              isolated Docker/Podman sandbox
                    /                    \
          dependency strategy       model strategy
                    \                    /
                     verification engine
                              |
                  checksummed evidence bundle
                              |
                local or S3-compatible storage
```

## Architectural style

The codebase is a modular monolith with ports and adapters:

- **Domain:** statuses, change specifications, risk, and invariants.
- **Application:** workflows and transaction boundaries.
- **Adapters:** SQLAlchemy, artifact storage, HTTP model providers, Git, and sandbox engines.
- **Delivery:** FastAPI and Typer.
- **Runner:** a separately deployable process using the same package.

This keeps deployment simple while preserving boundaries that can later become services.

## High-level component design

| Component | Responsibility | Explicitly does not do |
|---|---|---|
| CLI | Scan a local repository and call authenticated API workflows | Persist authoritative state |
| FastAPI control plane | Validate requests, assess risk, enforce approval, lease jobs, expose evidence | Clone repositories or run their code |
| PostgreSQL | Projects, typed change specs, status, job leases, evidence metadata, audit events | Store source repositories |
| Artifact adapter | Persist canonical evidence JSON in local or S3-compatible storage | Decide whether a change passed |
| Runner | Poll for one approved job, heartbeat its lease, coordinate execution, upload evidence | Accept inbound public traffic or self-approve |
| Source adapter | Copy an allowed local path or shallow-clone an explicit Git URL | Discover credentials from repository files |
| Sandbox adapter | Run bounded verification in Docker/Podman | Grant the child a host socket or default network access |
| Migration strategies | Make deterministic dependency or model-reference edits | Merge, deploy, or silently repair arbitrary code |
| Verification engine | Compare baseline and candidate command/model contracts | Treat an LLM opinion as a test result |
| Model provider adapter | Call an OpenAI-compatible HTTP endpoint such as Ollama | Bind domain logic to one vendor SDK |

## End-to-end sequence

```text
Developer       API            PostgreSQL       Runner        Sandbox       Artifacts
    | register   |                  |                |              |              |
    |----------->| save project     |                |              |              |
    | propose    |----------------->|                |              |              |
    |----------->| risk + PLANNED   |                |              |              |
    | approve    |----------------->| QUEUED job     |              |              |
    |----------->|                  |                |              |              |
    |            |<--- lease poll -------------------|              |              |
    |            | atomically lease|--------------->|              |              |
    |            |                  |                | baseline ---->|              |
    |            |                  |                | deterministic edit           |
    |            |                  |                | candidate --->|              |
    |            |                  |                | evidence hash |------------->|
    |            |<---------------- completion + lease token -----------------------|
    |            | terminal state + audit -------->|              |              |
    | status     |                  |                |              |              |
    |----------->|<-----------------|                |              |              |
```

The baseline matters: if checks fail before the edit, VersionWeaver blocks by default rather than
claiming the candidate introduced or fixed that failure. Model changes can additionally execute the
same deterministic evaluation cases against old and new model identifiers.

## Trust boundaries

1. Internet to API: authenticated and rate-limited by the hosting edge.
2. API to database/artifacts: service credentials with least privilege.
3. API to runner: a runner-scoped API token plus per-job lease token; no inbound runner port.
4. Runner to repository: untrusted content.
5. Runner to sandbox: explicit command, mount, network, and resource policy.
6. Runner to model endpoint: opt-in egress and environment-supplied secret.

## State machines

```text
Change: DRAFT -> PLANNED -> APPROVED -> QUEUED -> RUNNING -> VERIFYING
             \            \          \          \          |-> SUCCEEDED
              --------------------------------------------->|-> FAILED
                                                           |-> BLOCKED
                                                           |-> CANCELLED

Job:    QUEUED -> LEASED -> RUNNING -> SUCCEEDED
                    ^          |       FAILED
                    |          |       DEAD_LETTER
                    +-- expired lease / attempts remain
```

Change transitions are validated. Creation, approval, leasing, and completion write audit events.
The API moves an active change through `VERIFYING` when it accepts completion evidence.

## Low-level module design

```text
versionweaver/
  domain/        enums, state-transition rules, deterministic risk scoring
  schemas.py     boundary DTOs and per-change validation
  application/   transactional create/approve/lease/heartbeat/complete use cases
  persistence/   SQLAlchemy entities, sessions, URL normalization
  api/           HTTP authentication, routes, health, request correlation
  cli/           developer and runner commands
  analyzers/     dependency and model inventory
  migrators/     scoped deterministic source transformations
  sandbox/       Docker, Podman, and explicitly unsafe local adapter
  providers/     replaceable model inference clients
  verifiers/     deterministic model-evaluation contracts
  evidence/      canonical JSON, SHA-256, local/S3 adapters
  workers/       source materialization, execution orchestration, lease heartbeats
```

The application layer depends on abstractions or domain values, while API and CLI code translate
external input into those values. The API process imports no runner execution path in a request
handler. API and runner share a package for simplicity but are separate processes with different
privileges.

## Data model

- `projects`: name, source URI, default branch, latest discovered inventory.
- `change_requests`: typed spec snapshot, kind, risk score/reasons, lifecycle, requester/approver.
- `jobs`: one idempotent execution record per change, attempt count, owner/token/expiry, last error.
- `evidence`: immutable metadata, content URI, SHA-256, and queryable outcome summary.
- `audit_events`: actor, action, related change, timestamp, and structured details.
- `outbox_events`: integration events committed atomically with domain changes and published later.

Foreign keys keep change, job, evidence, and audit provenance connected. The execution job has a
unique idempotency key, and completion locks the job row before validating the lease and writing a
terminal result.

## Queue semantics

Jobs live in PostgreSQL. A runner atomically leases a queued job. A lease has an owner and expiry.
Heartbeats extend it. Expired running jobs become eligible for recovery until `max_attempts` is
reached, after which they become dead-lettered. This is intentionally less infrastructure than
Redis/Celery or Kafka and is sufficient for the MVP.

Delivery is at-least-once: a runner can finish locally and lose connectivity before reporting. A
stale lease can therefore execute again. Safe completion is protected by the owner/token and active
status check; migration work happens in a fresh temporary copy. Future external side effects must
also be idempotent.

## Evidence design

Evidence is content-addressed. The JSON document is canonicalized and SHA-256 hashed before it is
stored. PostgreSQL records metadata; the body lives in a local or S3-compatible artifact store.

The evidence schema includes inventories, command exit codes and bounded output, model evaluation
results, diff, reason, error, and timestamps. Secrets configured as model keys are recursively
redacted before upload. A hash detects alteration; object versioning or lock provides retention.

## Key decisions and trade-offs

### Modular monolith over microservices

One package and two processes are easier to understand, test, and host for free. Module boundaries
retain a later extraction path. The cost is shared release cadence and one control-plane scaling
unit, acceptable before measured load requires separation.

### PostgreSQL lease queue over Kafka, Redis, or Celery

The database is already required, transactions make approval-to-queue atomic, and `FOR UPDATE SKIP
LOCKED` supports competing runners. This minimizes operations. It is not intended for event-stream
replay or extremely high throughput; move to NATS/RabbitMQ/a managed queue only when queue latency,
database contention, or independent scaling demonstrates the need. Kafka would add partitions,
consumer-group operations, and delivery semantics without an MVP requirement for event streaming.

### Self-hosted runner over hosted execution

It protects the public low-cost host from untrusted builds and lets private repositories/models stay
inside a developer or company network. The trade-off is runner installation and availability. An
organization can later create ephemeral runner pools without changing the API contract.

### Deterministic edits before AI repair

Exact manifest and recognized model-configuration rewrites are reviewable and reproducible. They
cover fewer cases than a general coding agent, but they avoid prompt injection and broad accidental
changes. An AI repair strategy can be added behind the same evidence and approval gates later.

### OpenAI-compatible HTTP over model SDKs

This works with Ollama and several serving stacks while keeping provider code isolated. Compatibility
details differ among servers, so advanced vendor features need explicit adapters rather than hidden
conditionals in the domain.

## Failure behavior

- API restart: queued and leased state survives in PostgreSQL; an expired lease becomes recoverable.
- Runner crash: heartbeat stops; another runner can lease after expiry and remaining attempts.
- Database unavailable: readiness fails and no state-changing operation should be considered done.
- Artifact upload failure: completion transaction does not write terminal evidence; the lease can
  expire and retry.
- Baseline command failure: change becomes blocked unless an explicit override was recorded.
- Candidate command/evaluation failure: evidence is stored and change/job become failed.
- Model endpoint timeout: bounded provider call yields failed execution evidence; no silent fallback.
- Malicious repository: commands remain in a resource-limited, network-off-by-default child
  container, but hard multi-tenant isolation still requires dedicated ephemeral runners.

## Capacity model

The API is mostly I/O-bound and can scale horizontally once migrations are single-owner. Runner
capacity is approximately `runner_count / average_job_duration`; each runner currently processes one
job at a time. PostgreSQL queue scans are indexed by status and creation time. Artifact volume grows
with command logs and diffs, so output is bounded and object lifecycle rules should age old bundles.

## Scaling path

1. Add runner replicas; database leasing already supports concurrency.
2. Move artifacts to S3-compatible object storage.
3. Add read replicas and a connection pooler when metrics justify them.
4. Replace the job adapter with NATS, RabbitMQ, or a managed queue without changing the domain.
5. Add a frontend against the existing API.
6. Replace static scoped tokens with OIDC workload/user identities and tenant-aware RBAC before
   multiple organizations share one control plane.
