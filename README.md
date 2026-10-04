# VersionWeaver

[![CI](https://github.com/manasa1508/versionweaver/actions/workflows/ci.yml/badge.svg)](https://github.com/manasa1508/versionweaver/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

VersionWeaver is an open-source change-intelligence and migration-reliability platform for
software dependencies and AI model changes. It gives individual developers a CLI and gives
platform teams a shared API, durable job queue, approval workflow, and evidence ledger.

The core safety rule is simple: **the hosted control plane never executes arbitrary repository
code**. A self-hosted runner leases approved jobs, creates an isolated Docker/Podman workspace,
runs baseline and candidate verification, and returns checksummed evidence.

## What is implemented

- FastAPI control plane with role-scoped developer/admin/runner tokens, health endpoints, projects,
  approvals, durable jobs, runner leases, heartbeats, evidence, and audit events.
- Typer CLI for local scanning, project registration, change creation, approval, status, and
  runner operation.
- PostgreSQL production storage and SQLite development storage.
- Database-backed, lease-based job queue with retry and dead-letter behavior.
- Python dependency discovery for `pyproject.toml`, requirements files, and Poetry.
- Python model-usage discovery for model keyword arguments, common configuration variables, and
  environment-backed model identifiers.
- Deterministic dependency and model-string migrations.
- Baseline/candidate verification in Docker or Podman with explicit resource and network limits.
- OpenAI-compatible model evaluation, including Ollama, with deterministic contracts.
- Local or S3-compatible evidence storage.
- Idempotent commands, optimistic concurrency, transactional outbox, circuit breaker/retry,
  keyset pagination, Prometheus metrics, graceful shutdown, and controlled cancellation.
- Docker Compose and Render deployment descriptors.
- Unit and API integration tests, CI, threat model, architecture decisions, and runbook.

## Quick start

```bash
cp .env.example .env
uv sync --extra dev
uv run versionweaver init-db
uv run versionweaver serve
```

In another terminal, register and scan the example repository:

```bash
export VERSIONWEAVER_API_TOKEN=change-me-before-hosting
uv run versionweaver scan ./examples/python-ai-app
uv run versionweaver project create demo ./examples/python-ai-app
```

Copy the returned project ID, create a dependency change, approve it, and then run one job:

```bash
uv run versionweaver change create PROJECT_ID ./examples/dependency-change.json \
  --title "Upgrade pydantic"
uv run versionweaver change approve CHANGE_ID --actor local-developer
uv run versionweaver runner --once
```

Or start the PostgreSQL, MinIO, and API control plane with containers, then run the trusted
runner from the host as shown above:

```bash
docker compose up --build
```

The runner requires Docker or Podman and Git on its host. It polls outbound; no runner port needs
to be exposed.

## Product workflow

```text
discover -> baseline -> analyze -> plan -> approve -> execute -> verify -> evidence
```

Dependency and model changes share the same `ChangeSpec`, state machine, policy decisions, runner,
and evidence format. See [architecture](docs/architecture.md) and
[requirements](docs/requirements.md).

## Hosting

The API and PostgreSQL database can run on Render, Railway, Fly.io, Koyeb, or any container host.
Static documentation or a future frontend can run on Netlify. Migration jobs run on registered
self-hosted runners because they require a general-purpose container sandbox.

Free tiers change frequently and often sleep, limit background workers, or provide ephemeral disks.
Use PostgreSQL plus S3-compatible storage for any durable hosted deployment.

See the [deployment guide](docs/deployment.md) and [operator runbook](docs/runbook.md).
For a concept-by-concept learning path, read the
[production system-design patterns guide](docs/system-design-patterns.md).

## Security

Do not expose the development token or enable unsafe local execution on a public server. Read
[the threat model](docs/threat-model.md) before connecting untrusted repositories.

## License

Apache-2.0.

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md) before opening a pull request or reporting a vulnerability.
