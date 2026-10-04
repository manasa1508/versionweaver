# Contributing to VersionWeaver

Thank you for improving VersionWeaver.

## Development setup

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run pytest
```

Run the complete quality gate before submitting a pull request:

```bash
make check
docker compose config --quiet
docker build -t versionweaver:local .
```

## Change expectations

- Add tests for behavior and failure paths.
- Keep domain rules independent of infrastructure adapters.
- Preserve the rule that hosted API processes never execute repository code.
- Document new configuration and migration steps.
- Never commit credentials, private repository URLs, customer data, or proprietary model inputs.
- Explain operational and security trade-offs in the pull request.

Use conventional, imperative commit messages where practical. Small, reviewable changes are easier
to validate than broad refactors mixed with features.

## Reporting security issues

Do not open a public issue for a suspected vulnerability. Follow [SECURITY.md](SECURITY.md).
