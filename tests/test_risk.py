from versionweaver.domain.enums import ChangeKind
from versionweaver.domain.risk import assess_risk


def test_major_dependency_without_verification_is_high_risk() -> None:
    assessment = assess_risk(
        ChangeKind.DEPENDENCY,
        {"from_version": "1.4.0", "to_version": "2.0.0", "verification_commands": []},
    )
    assert assessment.level == "high"
    assert assessment.score >= 70


def test_model_change_with_evals_has_lower_risk_than_without() -> None:
    base = {
        "from_model": "old",
        "to_model": "new",
        "from_provider": "ollama",
        "to_provider": "ollama",
        "verification_commands": ["python -m compileall -q ."],
    }
    without = assess_risk(ChangeKind.MODEL, base)
    with_evals = assess_risk(ChangeKind.MODEL, {**base, "evaluation_cases": [{"id": "x"}]})
    assert without.score > with_evals.score
