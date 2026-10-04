# ADR 0002: PostgreSQL-backed job queue

- Status: Accepted
- Date: 2026-09-26

## Decision

Use the primary PostgreSQL database for job state and leases in the MVP.

## Rationale

It keeps deployment compatible with inexpensive hosts and removes Redis, RabbitMQ, and Kafka from
the initial failure surface. Transactions make the change, job, approval, and audit history
consistent.

## Consequences

- Workers must use short transactions and indexed lease queries.
- PostgreSQL is not the long-term answer for extremely high queue throughput.
- A queue port allows later replacement without rewriting migration logic.

