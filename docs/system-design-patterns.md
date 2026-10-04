# Production system-design patterns in VersionWeaver

This guide explains the patterns implemented in the project, the problem each solves, the code path
to study, its trade-offs, and how to discuss it in an interview. The goal is not to collect every
named pattern. It is to use the patterns that materially improve this system.

## Pattern map

| Area | Implemented pattern | Why it exists here |
|---|---|---|
| Architecture | Modular monolith, ports and adapters | Simple deployment with replaceable infrastructure |
| API correctness | Idempotency key plus request hash | Safe client retries without duplicate changes |
| Concurrency | Optimistic version plus row locks | Detect stale human actions and serialize job completion |
| Workflow | Explicit state machine | Make legal and illegal lifecycle changes testable |
| Async work | Database lease queue | Durable background work without another broker |
| Delivery | At-least-once plus idempotent completion | Recover from runner/network failure |
| Integration | Transactional outbox | Avoid state/event dual-write inconsistency |
| Failure isolation | Retry/backoff/jitter and circuit breaker | Handle transient model-provider failure without storms |
| Security | Trust boundaries and role-scoped tokens | Prevent a runner from approving its own job |
| Isolation | Docker/Podman sandbox and resource limits | Bound untrusted repository execution |
| Observability | Structured logs, correlation IDs, Prometheus metrics | Diagnose requests and build SLOs |
| Data access | Keyset/cursor pagination | Stable large-table scans without deep offsets |
| Storage integrity | Canonical JSON and SHA-256 evidence | Detect evidence changes and support content addressing |
| Operations | Health/readiness, migrations, graceful shutdown | Safe orchestration and deploys |
| Governance | Approval, audit trail, cancellation | Human control over consequential changes |
| Scalability | Stateless API plus competing runners | Scale control plane and execution independently |

## 1. Modular monolith and ports/adapters

VersionWeaver is one Python package deployed as separate API and runner processes. Domain and
application code do not depend directly on Render, MinIO, Ollama, or a specific queue product.
Adapters handle SQLAlchemy, S3-compatible storage, model HTTP, Git, and sandbox execution.

Why this is useful:

- One repository, release, and local setup while the product is small.
- Transactional workflows remain straightforward.
- Interfaces preserve an extraction path if a component needs independent scaling later.

Trade-off: modules can still become coupled because process boundaries do not enforce separation.
Use dependency rules, tests, and code ownership before assuming microservices will fix coupling.

Interview answer: “I chose a modular monolith because team size and traffic did not justify
distributed operations. I separated API and runner privileges physically and kept infrastructure
behind adapters, so we can extract the queue, provider, or evidence service when measurements—not
fashion—justify it.”

## 2. Idempotent command handling

`POST /api/v1/changes` accepts `Idempotency-Key`. The application hashes the canonical request and
stores the key/hash on the created change.

- Same key and same request: return the original change.
- Same key and different request: return conflict.
- Concurrent duplicate insert: the database unique constraint arbitrates the race.

This handles a common failure: the server commits, the response is lost, and the client retries.
Without idempotency the retry creates a second migration.

Important boundary: idempotency is scoped globally in this MVP. A multi-tenant system should use a
unique key such as `(organization_id, idempotency_key)` and retain keys for a documented period.

Code: `application/service.py:create_change`, `change_requests.idempotency_key`, API header parsing.

## 3. Optimistic concurrency and pessimistic locking

These are complementary, not competing, techniques.

- The `version` column is optimistic concurrency. An approver or canceller can send
  `expected_version`; a stale UI receives `409 Conflict` instead of overwriting newer state.
- `SELECT ... FOR UPDATE` is pessimistic locking for short critical sections such as job completion
  and cancellation.
- SQLAlchemy's `version_id_col` catches concurrent updates made through independent sessions.

Use optimistic concurrency when collisions are rare and user-visible. Use a row lock when a short
server-side invariant must be serialized. Do not hold a database lock while calling a model, Git,
or object store.

## 4. Explicit state machine

Allowed change transitions live in `domain/state.py`; statuses live in `domain/enums.py`. This avoids
scattered `if status == ...` rules and makes invalid transitions fail centrally.

Benefits:

- Lifecycle behavior is reviewable.
- Terminal states cannot accidentally re-enter execution.
- Cancellation policy is explicit.
- Tests can cover the transition graph independently.

For a much larger workflow, consider a workflow engine such as Temporal. It is unnecessary while
the state fits one database transaction and one bounded runner job.

## 5. Durable lease queue and competing consumers

Jobs are rows in PostgreSQL. Runners use `FOR UPDATE SKIP LOCKED` to compete for work without taking
the same row. A lease records owner, unguessable token, expiry, attempt count, and maximum attempts.
Heartbeats extend active work. Expired leases can be recovered; exhausted jobs become dead letters.

Guarantee: at-least-once execution, not exactly once. Exactly-once processing across a database,
Git provider, object store, and model endpoint is generally not realistic. The design instead uses
fresh workspaces and idempotent completion.

When to replace it:

- Use RabbitMQ/NATS/SQS when queue throughput, routing, or independent operations justify a broker.
- Use Kafka when ordered, replayable event streams and multiple consumer groups are requirements.
- Do not add Kafka only to execute a modest number of migration jobs.

## 6. Transactional outbox

A database update and an event publish are a dual write. If the database commits and Kafka fails,
or Kafka succeeds and the database rolls back, downstream systems disagree with the source of truth.

VersionWeaver inserts `outbox_events` in the same transaction as create, approve, lease, complete,
and cancel. A dispatcher later locks unpublished rows, invokes an `EventPublisher`, and marks success.
The included `LoggingPublisher` is a development adapter; Kafka, NATS, SNS, or webhooks implement the
same protocol.

Delivery is at least once: a crash after publishing but before marking can redeliver. Consumers must
deduplicate by outbox event ID. For high scale, use partitioning, CDC/Debezium, or archive published
rows instead of polling an ever-growing table.

## 7. Retry, exponential backoff, jitter, and circuit breaker

The OpenAI-compatible provider retries only likely transient failures: transport errors, HTTP 429,
and HTTP 5xx. Delay grows exponentially and adds jitter, reducing synchronized retry storms.

The circuit breaker has three logical states:

```text
CLOSED --failure threshold--> OPEN --cooldown--> HALF_OPEN
   ^                                             |
   +---------------- successful probe -----------+
```

When open, calls fail fast instead of consuming threads and amplifying an unhealthy dependency.
Non-transient 4xx responses are not retried. Every call and retry remains bounded by explicit
attempt and timeout limits.

Trade-off: an in-process breaker is per instance. A distributed breaker is usually unnecessary;
instances independently shedding load often behaves better than adding shared coordination.

## 8. Least privilege and trust boundaries

There are three credentials:

- Developer: projects, change creation, approval, cancellation, evidence.
- Runner: lease, heartbeat, completion only.
- Administrator: audit/outbox streams and metrics; also allowed across operational APIs.

Production startup rejects missing or identical role tokens. Development can intentionally use one
token. A per-job lease token provides capability-style authorization after a runner leases work.

This is educational scoped authentication, not full identity management. Before multi-tenant use,
replace it with OIDC, organizations, user/service principals, RBAC/ABAC, token expiry, rotation,
revocation, and authorization tests at every resource boundary.

## 9. Bulkhead and sandbox isolation

The API never executes repository code. A separate runner processes one job at a time, naturally
forming a bulkhead: a slow build cannot consume API worker capacity. The child container limits CPU,
memory, process count, duration, filesystem and network access.

Docker is not a perfect hostile multi-tenant boundary. Stronger deployments use ephemeral VMs,
Kubernetes runtime classes, gVisor, Kata Containers, Firecracker, dedicated runner pools, and egress
policies according to threat level.

## 10. Observability

- `X-Request-ID` correlates client and server activity.
- Structured JSON logs carry job/change/runner context.
- `/metrics` exposes request counts and latency histograms using bounded route-template labels.
- `/health/live` checks process life; `/health/ready` checks database readiness.

Avoid putting raw IDs, URLs, or error text in metric labels because unbounded cardinality can exhaust
the monitoring system. Build alerts from user impact: error rate, latency, queue age, dead-letter
count, runner availability, and evidence-upload failure.

## 11. Keyset pagination

The audit API orders by `(created_at, id)` and returns an opaque `X-Next-Cursor`. The next query uses
the last tuple instead of `OFFSET N`.

Keyset pagination remains efficient for deep pages and is stable while new rows arrive. Its trade-off
is that arbitrary page-number jumps are not natural. Offset pagination remains fine for small admin
tables where simplicity matters more than deep-page performance.

## 12. Evidence integrity and object storage

Evidence JSON is canonicalized and hashed with SHA-256. PostgreSQL stores metadata and the body goes
to local or S3-compatible storage. This separates transactional querying from large immutable data.

A hash detects change but does not prove who created evidence. Higher-assurance systems add signed
attestations, workload identity, immutable bucket retention, provenance standards such as SLSA, and
independent verification.

## 13. Patterns intentionally not forced into the MVP

| Pattern/technology | Why it is not currently implemented | Trigger to add it |
|---|---|---|
| Redis cache | Most reads are small/control-plane reads; invalidation adds risk | Proven database read bottleneck |
| Kafka | No event-stream replay or massive throughput requirement | Multiple durable consumers and replay requirements |
| Kubernetes | One API plus trusted runners works locally/Render | Many ephemeral runners, scheduling and isolation needs |
| Database sharding | Data volume is nowhere near a single PostgreSQL limit | Measured storage/write/tenant isolation pressure |
| CQRS/event sourcing | Current state plus immutable audit/outbox is sufficient | Temporal reconstruction is a core product requirement |
| Saga orchestration | One main transaction and bounded worker job | Multiple independently committed services need compensation |
| Service mesh | No large service fleet | Many services need uniform mTLS, traffic policy and telemetry |
| CDN | No public static frontend or large public assets | Global frontend latency/static delivery requirement |
| Distributed lock service | PostgreSQL row locks and leases already coordinate work | Coordination leaves the database domain |

Good system design is selective. Adding all popular components would make this project more fragile,
more expensive, and harder to explain without solving a demonstrated requirement.

## Interview walkthrough

Use this sequence:

1. Problem: dependency and model upgrades are easy to edit but hard to verify and govern.
2. Constraints: untrusted repository code, private source, cheap hosting, human approval, recoverable
   jobs, provider portability.
3. Architecture: stateless control plane, PostgreSQL source of truth/lease queue, outbound trusted
   runner, sandbox, object evidence.
4. Hardest decision: separate control and execution trust boundaries instead of running an agent in
   the public API.
5. Failure design: idempotency, leases, heartbeats, retries, dead letters, outbox, circuit breaker.
6. Consistency: transactions and row locks for invariants; eventual consistency for published events.
7. Security: scoped identities, lease capability, network-off sandbox, secret redaction.
8. Scale: API replicas and runner replicas independently; replace adapters only after metrics.
9. Measurement: API latency/error rate, queue age, job success, retry count, dead letters, evidence
   durability, model-evaluation pass/regression rate.
10. Limitations: Python-first, token auth rather than OIDC, no PR adapter/UI, no hardened multi-tenant
    runner fleet.

That answer demonstrates requirement-driven system design, consistency choices, failure semantics,
security boundaries, operability, and honest trade-offs—the areas interviewers usually probe.
