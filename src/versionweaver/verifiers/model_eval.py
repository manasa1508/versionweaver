import json
from dataclasses import asdict
from typing import Any

from versionweaver.providers.openai_compatible import OpenAICompatibleProvider
from versionweaver.schemas import EvaluationCase


def _evaluate_content(content: str, case: EvaluationCase) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    lowered = content.lower()
    for expected in case.expected_contains:
        checks.append(
            {
                "contract": "contains",
                "value": expected,
                "passed": expected.lower() in lowered,
            }
        )
    for forbidden in case.forbidden_contains:
        checks.append(
            {
                "contract": "forbidden",
                "value": forbidden,
                "passed": forbidden.lower() not in lowered,
            }
        )
    if case.required_json_keys:
        try:
            parsed = json.loads(content)
            keys = set(parsed) if isinstance(parsed, dict) else set()
            passed = set(case.required_json_keys).issubset(keys)
            error = None
        except (json.JSONDecodeError, TypeError) as exc:
            passed = False
            error = str(exc)
        checks.append(
            {
                "contract": "required_json_keys",
                "value": case.required_json_keys,
                "passed": passed,
                "error": error,
            }
        )
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def evaluate_model(
    provider: OpenAICompatibleProvider, model: str, cases: list[EvaluationCase]
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        try:
            response = provider.complete(model=model, messages=case.messages)
            contract = _evaluate_content(response.content, case)
            results.append(
                {
                    "case_id": case.id,
                    "passed": contract["passed"],
                    "checks": contract["checks"],
                    "response": asdict(response),
                }
            )
        except Exception as exc:  # Provider failures are evaluation evidence, not runner crashes.
            results.append(
                {
                    "case_id": case.id,
                    "passed": False,
                    "checks": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    passed = sum(1 for item in results if item["passed"])
    latencies = [
        item["response"]["latency_ms"] for item in results if item.get("response") is not None
    ]
    return {
        "model": model,
        "passed": passed == len(results),
        "case_count": len(results),
        "passed_count": passed,
        "success_rate": passed / len(results) if results else 1.0,
        "average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "results": results,
    }
