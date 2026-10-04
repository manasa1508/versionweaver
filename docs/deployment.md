# Deployment guide

## Recommended starter topology

Use Render for the API and PostgreSQL, an S3-compatible object store for evidence, and one trusted
developer machine or CI agent as the runner. Netlify can host a later static frontend, but it is
not part of the execution trust boundary.

```text
Browser / CLI
      |
      v
Render HTTPS -> VersionWeaver API -> PostgreSQL
                    |                 metadata, queue, audit
                    +-----------> S3-compatible evidence store
                    ^
                    |
          outbound polling over HTTPS
                    |
       trusted host -> Docker/Podman sandbox -> Git repository
```

This split is intentional. The public API schedules and records work but cannot execute repository
commands. The runner has that privilege but exposes no inbound service.

## Open-source component policy

| Capability | Default | License/portability note |
|---|---|---|
| API and CLI | Python, FastAPI, Typer | Open-source; runs on any container host |
| Database and queue | PostgreSQL | Open-source; no hosted-provider API in domain code |
| ORM and migrations | SQLAlchemy, Alembic | Open-source |
| Evidence | MinIO or another S3-compatible store | Interface is portable; local storage is for development |
| Sandbox | Docker Engine or Podman | Podman is the daemonless/open-source-first option |
| Local inference | Ollama-compatible endpoint | Runtime is replaceable through standard HTTP |
| Model weights | User-selected | Check each model's weight/data license before commercial use |
| Hosting | Render initially | A deployment target, not an application dependency |

No proprietary model SDK is required. `OpenAICompatibleProvider` describes an HTTP shape and can
point to Ollama or another compatible open-source inference server. Hosted model APIs remain an
optional configuration, not a hard dependency.

## Local container deployment

1. Copy `.env.example` to `.env` and replace the development token.
2. Run `docker compose up --build`.
3. Confirm `http://localhost:8000/health/ready` returns `database: ok`.
4. On the trusted host, run `uv sync`, configure the runner token (the development API token is a
   deliberate local fallback), and start
   `uv run versionweaver runner`.
5. Keep `VERSIONWEAVER_SANDBOX_ENGINE=docker` or `podman`. Never enable local execution on a shared
   or public machine.

The Compose stack intentionally does not mount the host container socket into the API or another
container. That socket is effectively host-admin access.

## Render deployment

The root `render.yaml` creates a Docker web service and PostgreSQL in Singapore. Before applying
the Blueprint:

1. Push this repository to a Git provider Render can read.
2. Choose **New Blueprint** and select the repository.
3. Supply S3-compatible endpoint, bucket, region, access key, and secret when prompted.
4. Let Render generate distinct developer, administrator, and runner tokens; copy only
   `VERSIONWEAVER_RUNNER_API_TOKEN` into the trusted runner's secret store.
5. Deploy and check `/health/live` and `/health/ready`.
6. Set the runner's `VERSIONWEAVER_SERVER_URL` to the Render HTTPS URL and start it.

Render's free web service is suitable for a portfolio demo, not production: it can sleep after
idle time and its filesystem is ephemeral. Its free PostgreSQL offering also expires, has no
managed backups, and is capacity-limited. Export data or use a durable PostgreSQL provider before
real use.

## Netlify placement

Use Netlify only for a static React/Astro/Vite frontend or generated documentation. Configure that
frontend with the public API URL and keep the API token out of browser code. Before a public UI is
added, replace the single service token with an OAuth/OIDC backend-for-frontend flow. The current
API is intended for CLI/CI and trusted demos.

## Production promotion checklist

- Replace static scoped tokens with OIDC, users, organizations, tenant-aware RBAC, expiry and
  revocation.
- Add edge request limits, body-size limits, TLS, CORS allowlists, and security monitoring.
- Use durable PostgreSQL with point-in-time recovery and tested restore procedures.
- Use versioned/object-lock capable artifact storage and lifecycle policies.
- Pin sandbox images by digest; scan images and dependencies in CI.
- Run dedicated ephemeral runners; do not share developer credentials with jobs.
- Restrict repository and model egress with allowlists and short-lived credentials.
- Export metrics and traces; alert on queue age, dead letters, lease loss, and error rate.
- Complete tenant-isolation review, threat modeling, dependency/license review, and penetration test.
