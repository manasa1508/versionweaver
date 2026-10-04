import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from versionweaver.analyzers.repository import scan_repository
from versionweaver.config import Settings
from versionweaver.domain.enums import ChangeKind
from versionweaver.migrators.dependency import migrate_dependency
from versionweaver.migrators.model import migrate_model
from versionweaver.providers.openai_compatible import OpenAICompatibleProvider
from versionweaver.sandbox.runner import Sandbox
from versionweaver.schemas import ChangeSpec
from versionweaver.verifiers.model_eval import evaluate_model
from versionweaver.workers.source import git_diff, materialize_source

JobOutcome = Literal["succeeded", "failed", "blocked"]


def _verify(sandbox: Sandbox, workspace: Path, spec: ChangeSpec) -> dict[str, Any]:
    results = [
        sandbox.run(
            workspace=workspace,
            command=command,
            timeout_seconds=spec.timeout_seconds,
            network=spec.allow_network,
        ).as_dict()
        for command in spec.verification_commands
    ]
    return {"passed": all(result["exit_code"] == 0 for result in results), "commands": results}


def _model_eval(settings: Settings, spec: ChangeSpec, model: str) -> dict[str, Any] | None:
    if not spec.evaluation_cases:
        return None
    base_url = spec.model_base_url or settings.model_base_url
    api_key = None
    if spec.model_api_key_env:
        api_key = os.getenv(spec.model_api_key_env)
    api_key = api_key or settings.model_api_key
    provider = OpenAICompatibleProvider(
        base_url=base_url, api_key=api_key, timeout_seconds=spec.timeout_seconds
    )
    return evaluate_model(provider, model, spec.evaluation_cases)


def _redact(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    return value


def execute_change(
    *,
    source_uri: str,
    default_branch: str,
    spec: ChangeSpec,
    sandbox: Sandbox,
    settings: Settings,
    change_id: str,
    job_id: str,
) -> tuple[JobOutcome, dict[str, Any], str | None]:
    started_at = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix="versionweaver-") as temporary:
        workspace = materialize_source(source_uri, Path(temporary) / "workspace", default_branch)
        inventory_before = scan_repository(workspace)
        baseline_verification = _verify(sandbox, workspace, spec)
        baseline_model = None
        if spec.kind == ChangeKind.MODEL and spec.from_model:
            baseline_model = _model_eval(settings, spec, spec.from_model)

        if not baseline_verification["passed"] and not spec.allow_baseline_failure:
            evidence = {
                "schema_version": "1.0",
                "change_id": change_id,
                "job_id": job_id,
                "outcome": "blocked",
                "reason": "baseline verification failed",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "inventory_before": inventory_before,
                "baseline": {
                    "verification": baseline_verification,
                    "model_evaluation": baseline_model,
                },
            }
            return "blocked", _redact(evidence, [settings.model_api_key or ""]), None

        try:
            if spec.kind == ChangeKind.DEPENDENCY:
                migration = migrate_dependency(
                    workspace,
                    dependency_name=spec.dependency_name or "",
                    to_version=spec.to_version or "",
                    manifest_paths=spec.manifest_paths,
                )
            else:
                migration = migrate_model(
                    workspace, from_model=spec.from_model or "", to_model=spec.to_model or ""
                )
        except Exception as exc:
            evidence = {
                "schema_version": "1.0",
                "change_id": change_id,
                "job_id": job_id,
                "outcome": "failed",
                "reason": "deterministic migration failed",
                "error": f"{type(exc).__name__}: {exc}",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "inventory_before": inventory_before,
                "baseline": {
                    "verification": baseline_verification,
                    "model_evaluation": baseline_model,
                },
            }
            return "failed", _redact(evidence, [settings.model_api_key or ""]), str(exc)

        candidate_verification = _verify(sandbox, workspace, spec)
        candidate_model = None
        if spec.kind == ChangeKind.MODEL and spec.to_model:
            candidate_model = _model_eval(settings, spec, spec.to_model)
        model_passed = candidate_model is None or candidate_model["passed"]
        outcome: JobOutcome = (
            "succeeded" if candidate_verification["passed"] and model_passed else "failed"
        )
        evidence = {
            "schema_version": "1.0",
            "change_id": change_id,
            "job_id": job_id,
            "outcome": outcome,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "inventory_before": inventory_before,
            "inventory_after": scan_repository(workspace),
            "migration": migration,
            "diff": git_diff(workspace),
            "baseline": {
                "verification": baseline_verification,
                "model_evaluation": baseline_model,
            },
            "candidate": {
                "verification": candidate_verification,
                "model_evaluation": candidate_model,
            },
        }
        secrets = [settings.model_api_key or ""]
        if spec.model_api_key_env:
            secrets.append(os.getenv(spec.model_api_key_env, ""))
        error = None if outcome == "succeeded" else "candidate verification failed"
        return outcome, _redact(evidence, secrets), error
