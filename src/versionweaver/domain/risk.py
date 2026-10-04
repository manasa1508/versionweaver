import re
from dataclasses import dataclass
from typing import Any

from versionweaver.domain.enums import ChangeKind


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    level: str
    reasons: list[str]


def _major(version: str | None) -> int | None:
    if not version:
        return None
    match = re.search(r"(?<!\d)(\d+)(?:\.\d+)?", version)
    return int(match.group(1)) if match else None


def assess_risk(kind: ChangeKind, spec: dict[str, Any]) -> RiskAssessment:
    score = 20
    reasons: list[str] = []
    source = spec.get("from_version") or spec.get("from_model")
    target = spec.get("to_version") or spec.get("to_model")

    if kind == ChangeKind.DEPENDENCY:
        old_major = _major(str(source) if source else None)
        new_major = _major(str(target) if target else None)
        if old_major is not None and new_major is not None and new_major > old_major:
            score += 35
            reasons.append("major dependency version increase")
        else:
            score += 10
            reasons.append("dependency version change")
    else:
        score += 35
        reasons.append("model behavior can change without API schema changes")
        if spec.get("from_provider") != spec.get("to_provider"):
            score += 15
            reasons.append("model provider changes")

    commands = spec.get("verification_commands", [])
    if not commands:
        score += 20
        reasons.append("no verification commands configured")
    if kind == ChangeKind.MODEL and not spec.get("evaluation_cases"):
        score += 15
        reasons.append("no model evaluation cases configured")
    if spec.get("allow_network"):
        score += 5
        reasons.append("sandbox network access requested")

    score = min(score, 100)
    level = "low" if score < 35 else "medium" if score < 70 else "high"
    return RiskAssessment(score=score, level=level, reasons=reasons or ["standard change"])
