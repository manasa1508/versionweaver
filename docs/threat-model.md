# Threat model

## Protected assets

- Source code and Git credentials
- Model-provider credentials
- Evaluation datasets
- Migration patches and evidence
- Approval identity and audit history
- Control-plane database

## Primary threats and controls

| Threat | Initial controls |
|---|---|
| Malicious repository executes host commands | Hosted API never executes repos; runner uses Docker/Podman isolation |
| Prompt injection in repository text | Repository content is data; deterministic migration runs first; no repository instruction becomes a system instruction |
| Model emits a dangerous patch | Patch is scoped, parsed, diffed, tested, and never self-approved |
| Secret leakage in logs | Environment references instead of secret values; recursive redaction before evidence upload |
| Duplicate job delivery | Idempotency key, transactional status checks, single active lease |
| Compromised runner | Scoped API token, outbound-only polling, least-privilege project access |
| Artifact tampering | SHA-256 content hash, versioned/object-lock capable store |
| Cross-tenant access | Organization/project ownership checks before multi-tenant launch |
| Dependency confusion | Index configuration is explicit; lockfiles and hashes are preferred |
| Denial of service | Request size limits at proxy; sandbox CPU/memory/process/time limits |

## Non-goals

The MVP is not a hardened multi-tenant SaaS and must not be advertised as one. A public deployment
requires an external TLS proxy, rate limiting, managed secret injection, database TLS, backups,
tenant authorization review, and a penetration test.

