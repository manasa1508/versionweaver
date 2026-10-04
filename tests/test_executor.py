from pathlib import Path

from versionweaver.config import Settings
from versionweaver.sandbox.runner import LocalSandbox
from versionweaver.schemas import ChangeSpec
from versionweaver.workers.executor import execute_change


def test_dependency_executor_produces_candidate_evidence() -> None:
    source = Path(__file__).parents[1] / "examples" / "python-ai-app"
    settings = Settings(
        environment="test",
        sandbox_engine="local",
        allow_unsafe_local_execution=True,
        api_token="test-token",
    )
    spec = ChangeSpec(
        kind="dependency",
        dependency_name="pydantic",
        from_version="2.9.0",
        to_version="2.10.0",
        verification_commands=["python3 -m compileall -q ."],
    )
    outcome, evidence, error = execute_change(
        source_uri=str(source),
        default_branch="main",
        spec=spec,
        sandbox=LocalSandbox(),
        settings=settings,
        change_id="change-test",
        job_id="job-test",
    )

    assert outcome == "succeeded"
    assert error is None
    assert evidence["candidate"]["verification"]["passed"] is True
    assert evidence["migration"]["replacements"] == 1
