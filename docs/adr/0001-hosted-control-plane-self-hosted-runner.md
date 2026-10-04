# ADR 0001: Hosted control plane and self-hosted runner

- Status: Accepted
- Date: 2026-09-26

## Decision

Run the API, durable state, policy, and evidence metadata on a portable container host. Run repository
commands only on an outbound-polling, self-hosted runner using Docker or Podman.

## Rationale

Low-cost web hosts are designed for application code, not adversarial repository builds. Separating
the runner prevents a compromised migration from obtaining control-plane database credentials and
allows organizations to keep private source code in their own network.

## Consequences

- Users must operate at least one runner for execution.
- Analysis and approval remain available when no runner is online.
- Runner availability and trust become explicit operational concerns.
- The same protocol can later support managed runners.

