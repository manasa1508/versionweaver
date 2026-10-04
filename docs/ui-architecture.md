# Operations console architecture

## Purpose and scope

The React console is an operator-facing projection of the VersionWeaver control plane. It is not a
second source of truth and it cannot lease jobs, receive runner secrets, execute repositories, or
modify evidence. All invariants remain in FastAPI and PostgreSQL so CLI, CI, and UI clients behave
consistently.

## Runtime topology

```text
Browser
  |  immutable JS/CSS + authenticated JSON
  v
FastAPI same-origin web/API process
  |-- SPA files (cacheable by edge/CDN)
  |-- command endpoints (no-store)
  |-- dashboard read model and keyset pages
  v
PostgreSQL source of truth ---- S3-compatible evidence
          ^
          | outbound lease/heartbeat/completion
trusted self-hosted runners ---- isolated Docker/Podman jobs
```

The default deployment keeps UI and API on one origin. This avoids broad CORS rules, removes an
extra availability dependency, and lets one container be demonstrated on free hosting. Immutable
hashed assets can still be cached by a reverse proxy or CDN. A separately hosted static UI is
supported through an exact CORS allowlist.

## Frontend modules

| Module | Responsibility |
|---|---|
| `context/AuthContext` | Session-scoped endpoint, developer/admin tokens, and audit identity |
| `lib/api` | Timeouts, request IDs, typed contracts, pagination cursors, and normalized errors |
| React Query | Bounded caching, stale-while-revalidate behavior, GET retries, invalidation |
| Router/layout | Deep links, responsive navigation, connection health, route code splitting |
| Overview | Aggregate read model, pipeline distribution, reliability signals, recent activity |
| Projects | Search, keyset pagination, repository registration, inventory visibility |
| Changes | Filters, typed dependency/model plans, risk, approval, cancellation, version conflicts |
| Jobs | Queue state, attempts, owners, lease expiry, dead-letter visibility |
| Evidence/audit | Immutable evidence retrieval and admin-scoped traceability |

Mutations are never retried automatically because replay safety differs by command. Change creation
does send an idempotency key. Approval and cancellation send the current optimistic-concurrency
version; a `409` makes the operator refresh rather than overwriting newer state.

## Backend read paths

The dashboard summary performs grouped SQL counts instead of downloading every row. Projects,
changes, jobs, and audit events use descending `(created_at, id)` keyset cursors. Composite indexes
match these access paths, avoiding large `OFFSET` scans and duplicate/missing records while new data
is arriving. Filters are evaluated in PostgreSQL. Evidence bodies remain lazy-loaded because they
can be much larger than metadata.

## Reliability behavior

- React Query refreshes volatile summary, job, and change state every 10–20 seconds and also on
  window focus.
- Safe GET requests retry twice only for network and server failures; authorization and validation
  errors fail immediately.
- Every request has a client timeout and correlation ID. API errors expose the returned request ID.
- Route chunks load independently, reducing initial bundle cost and limiting failure blast radius.
- Loading, empty, degraded, and retry states are explicit; stale server state remains authoritative.
- The UI never infers completion from elapsed time. It displays the durable job/change state.

Polling is deliberate for the MVP: the update rate is low and polling survives proxies and sleeping
free-tier services. At sustained high concurrency, add server-sent events for invalidation hints,
not as the source of truth; clients should refetch the authoritative resource after each event.

## Security model and production evolution

The console stores demo tokens in `sessionStorage`, never URLs or persistent local storage. The
runner credential is intentionally unsupported. FastAPI sets CSP, frame denial, MIME sniffing,
referrer, permissions, and no-store headers. Same-origin is the default.

Static tokens are not a multi-user identity system. Production promotion requires:

1. OIDC Authorization Code + PKCE through a backend-for-frontend.
2. Short-lived opaque sessions in `Secure`, `HttpOnly`, `SameSite` cookies.
3. User, organization, role, token-expiry, revocation, and tenant filters enforced server-side.
4. CSRF protection for cookie-authenticated commands and an exact CORS allowlist.
5. Edge rate limits, WAF/body limits, dependency scanning, CSP reporting, and security telemetry.

## Scale and fault-tolerance path

The UI is stateless and horizontally cacheable. The API remains horizontally scalable because
session state lives in PostgreSQL and artifacts. Start with the modular monolith; split only when
measurements justify it:

- add API replicas and a connection pooler when request concurrency grows;
- add PostgreSQL read replicas for dashboards only after accepting replica lag semantics;
- move aggregates to asynchronously refreshed projections if grouped-count latency breaches the
  dashboard SLO;
- use SSE invalidation when polling traffic becomes material;
- partition audit history by time and apply retention/export policies at very high volume;
- replace the PostgreSQL job adapter with a managed queue when lease scans contend with OLTP.

Kafka, Kubernetes, Redis, micro-frontends, and a separate dashboard database are not prerequisites.
They introduce operational cost and should be adopted against observed throughput, isolation, team,
or deployment requirements rather than included as portfolio decoration.

## Suggested service objectives

| Signal | Initial objective |
|---|---|
| Console asset availability | 99.9% monthly |
| Control-plane read p95 | under 500 ms |
| Command p95 excluding execution | under 750 ms |
| Freshness while tab is active | under 20 seconds |
| Dashboard query budget | under 250 ms at expected cardinality |
| Error correlation | 100% of API responses carry a request ID |

Alert on API error rate, readiness failure, p95 latency, queue age, dead-letter growth, outbox age,
runner heartbeat loss, and artifact upload failures. Client JavaScript errors can be sent to an
OpenTelemetry-compatible collector after applying privacy and secret-redaction controls.
