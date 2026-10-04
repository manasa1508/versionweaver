# VersionWeaver MVP requirements

## Problem

Dependency bots can identify available versions, while generic coding agents can edit files. Teams
still lack one evidence-driven workflow that establishes a clean baseline, assesses the affected
code, migrates either a dependency or model reference, verifies behavioral contracts, and records
why the candidate should or should not be accepted.

## Users

- Individual developers migrating one repository through a CLI.
- Platform engineers governing migrations across repositories through a hosted API.
- Approvers reviewing evidence without granting an AI system merge authority.

## Primary outcome

Produce reviewable dependency and model migrations with reproducible baseline-versus-candidate
evidence while reducing manual investigation and preventing unverifiable autonomous changes.

## In scope

1. Python repository inventory.
2. Python dependency version changes.
3. Hosted-LLM and OpenAI-compatible model identifier changes.
4. Deterministic model evaluations and optional local/open-source inference through Ollama.
5. Human approval before execution.
6. Self-hosted, isolated runners.
7. Durable jobs, retries, leases, audit events, and evidence.
8. CLI and REST API.
9. PostgreSQL, local/S3-compatible artifacts, Docker Compose, and Render deployment.
10. A responsive operations console for projects, change governance, jobs, evidence, and audit data.

## Out of scope for MVP

- Automatic merge or deployment.
- JavaScript, Java, Go, and .NET package ecosystems.
- Model training or fine-tuning.
- Kubernetes and Kafka.
- Automatic interpretation of arbitrary vendor changelog prose.
- Executing untrusted repositories inside the hosted API container.

## Functional requirements

### FR-1 — Register a project

A developer can register a local path or Git URL. The service stores source metadata but never a
repository credential in the project record.

### FR-2 — Discover assets

The scanner identifies dependency declarations and AI model usages with source-file provenance.

### FR-3 — Propose a typed change

The API accepts dependency and model `ChangeSpec` objects with source, target, verification
commands, evaluation contracts, and execution limits.

### FR-4 — Assess risk

VersionWeaver produces a deterministic preliminary risk score and explanation. Risk does not replace
verification or human judgment.

### FR-5 — Require approval

A change remains non-executable until an authorized user explicitly approves it.

### FR-6 — Lease jobs safely

Registered runners lease one job for a bounded interval, heartbeat while working, and allow an
expired lease to be recovered. Duplicate delivery must not produce duplicate completion effects.

### FR-7 — Establish a baseline

The runner executes verification before editing. A failing baseline blocks the change unless the
spec explicitly allows baseline failure.

### FR-8 — Execute deterministically first

Manifest or exact model-string changes happen through deterministic code before any optional model
assistance.

### FR-9 — Verify candidate behavior

The runner repeats configured checks and model evaluation contracts under candidate configuration.

### FR-10 — Preserve evidence

Reports include inventory, baseline, candidate results, diff, decision, timestamps, hashes, and
errors. The API stores artifact metadata and an append-only audit trail.

### FR-11 — Remain provider-portable

Model evaluation uses a provider interface. The default network adapter implements the widely used
OpenAI-compatible HTTP shape and supports Ollama without proprietary SDKs.

### FR-12 — Operate through a visual console

Developers can register projects, create dependency or model changes, approve or cancel work, and
inspect verification evidence. Operators can monitor queue attempts, leases, dead-lettered jobs,
and aggregate health. Admin-scoped users can inspect keyset-paginated audit history.

## Non-functional requirements

- All state changes are transactional and auditable.
- External calls and commands have explicit timeouts.
- Standard queue behavior is at-least-once; handlers are idempotent.
- Secrets are supplied to runners through environment variables and are redacted from evidence.
- Hosted API processes never run repository commands.
- Runner containers use CPU, memory, process, timeout, and network restrictions.
- Structured logs include request, change, job, and runner correlation identifiers.
- Storage and provider implementations are replaceable through interfaces.
- Production database connections use TLS.
- Health and readiness endpoints are available without authentication.
- Growing console collections use indexed keyset pagination rather than unbounded reads.
- Static UI assets are immutable and compressible; authenticated API responses are never cached.
- The same-origin deployment is the secure default; cross-origin access requires an explicit
  allowlist.

## MVP acceptance criteria

1. A sample Python repository yields dependency and model inventories with file/line provenance.
2. A dependency change can be created, approved, leased, executed, verified, and completed.
3. A model identifier change follows the same workflow and can run deterministic evaluation cases.
4. A worker interruption leaves the job recoverable after lease expiry.
5. Duplicate completion is rejected without corrupting evidence.
6. Baseline failure prevents candidate execution by default.
7. API integration and core unit tests pass in CI.
8. TypeScript checks, frontend unit tests, production bundle generation, and the multi-stage Docker
   build pass in CI.
