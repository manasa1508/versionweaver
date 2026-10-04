# Security policy

## Supported version

This project is pre-1.0. Security fixes apply to the latest commit on the default branch.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature for this repository. Do not include secrets,
private source code, customer data, or active exploit details in a public issue.

Include the affected component, reproducible conditions, impact, and suggested mitigation when
available. Maintainers should acknowledge a report before discussing disclosure timing.

## Security scope

VersionWeaver is not yet a hardened multi-tenant SaaS. Public deployments must follow the threat
model and production-promotion checklist. In particular, run repository jobs only on trusted,
isolated runners; use distinct role credentials; and keep unsafe local execution disabled.
