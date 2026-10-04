# Operator runbook

## Health checks

- Liveness: `GET /health/live` proves the process responds.
- Readiness: `GET /health/ready` proves the API can query its database.
- A healthy API with no runner can accept changes but jobs remain queued.

## Common incidents

### API does not start

Check the database URL and production token first. Render supplies a `postgresql://` URL; the app
normalizes it to the installed psycopg driver. Run `alembic upgrade head` against the same URL and
inspect the first exception, not later health-check noise.

### Jobs remain queued

Confirm the trusted runner is running, points to the right HTTPS URL, and has the same token.
Check outbound network access and the runner log for lease errors. A sleeping free API may take
about a minute to wake.

### Job repeatedly returns to the queue

The runner probably stopped or lost connectivity before completion. Leases expire and are retried
up to `max_attempts`; afterward the job is dead-lettered. Preserve the failed host logs, fix the
runner or repository issue, and create a new change request rather than editing audit history.

### Baseline is blocked

This means the configured verification command already failed before migration. Fix the repository
baseline. Use `allow_baseline_failure` only when the failure is understood and separately evidenced;
otherwise candidate results cannot be attributed to the migration.

### Candidate verification fails

Fetch `/api/v1/changes/{id}/evidence`, then retrieve the evidence content. Compare baseline and
candidate command results, model evaluation cases, and diff. Do not approve or merge outside the
tool merely to bypass a failed contract.

### Evidence cannot be retrieved

Check object-store credentials, bucket policy, endpoint, and whether the stored URI belongs to the
configured bucket. The database SHA-256 must match a canonicalized downloaded document. Treat a
mismatch as possible corruption or tampering.

## Backup and recovery

Back up PostgreSQL and the evidence bucket together because database rows reference object URIs.
Test restoration into an isolated environment. Free Render PostgreSQL has no managed backups, so it
must never be the only copy of important records.

## Token rotation

1. Pause new approvals.
2. Generate distinct high-entropy developer, administrator, and runner tokens.
3. Update the API and restart it.
4. Update each runner with only the new runner token and restart runners.
5. Verify readiness and one non-destructive scan/change flow.
6. Resume approvals and invalidate the old secret everywhere.

Static role tokens still require coordinated rotation. OIDC identities with short-lived credentials
and independent revocation are required before multi-team production use.

## Safe shutdown

Stop approving work, wait for active runner leases to complete, then stop runners and the API. If a
runner terminates unexpectedly, do not manually change its job row; lease recovery will requeue or
dead-letter the job according to attempts.
