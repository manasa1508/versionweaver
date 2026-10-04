from pathlib import Path

from versionweaver.analyzers.repository import scan_repository


def test_repository_scan_finds_dependencies_and_models() -> None:
    root = Path(__file__).parents[1] / "examples" / "python-ai-app"
    inventory = scan_repository(root)

    names = {item["name"] for item in inventory["dependencies"]}
    models = {item["model"] for item in inventory["models"]}

    assert {"httpx", "pydantic"}.issubset(names)
    assert "qwen2.5:0.5b" in models
    assert inventory["summary"]["dependency_count"] == 2
