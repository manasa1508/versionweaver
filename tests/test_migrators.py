import shutil
from pathlib import Path

from versionweaver.migrators.dependency import migrate_dependency
from versionweaver.migrators.model import migrate_model


def _copy_example(tmp_path: Path) -> Path:
    source = Path(__file__).parents[1] / "examples" / "python-ai-app"
    target = tmp_path / "app"
    shutil.copytree(source, target)
    return target


def test_dependency_migration_changes_only_requested_package(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    result = migrate_dependency(root, "pydantic", "2.10.0")
    content = (root / "pyproject.toml").read_text()

    assert result["replacements"] == 1
    assert "pydantic==2.10.0" in content
    assert "httpx>=0.27,<1" in content


def test_model_migration_rewrites_exact_literal(tmp_path: Path) -> None:
    root = _copy_example(tmp_path)
    result = migrate_model(root, "qwen2.5:0.5b", "qwen3:0.6b")

    assert result["replacements"] == 1
    assert "qwen3:0.6b" in (root / "app.py").read_text()


def test_poetry_dependency_migration_preserves_toml_assignment(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text('[tool.poetry.dependencies]\npython = "^3.12"\npydantic = "^2.9"\n')

    result = migrate_dependency(tmp_path, "pydantic", "2.10.0")

    assert result["replacements"] == 1
    assert 'pydantic = "2.10.0"' in manifest.read_text()


def test_model_migration_preserves_format_and_ignores_unrelated_literals(tmp_path: Path) -> None:
    source = tmp_path / "settings.py"
    source.write_text(
        'MODEL_NAME = "old-model"  # retain this comment\n'
        'documentation = "old-model"\n'
        'payload = {"model": "old-model"}\n'
    )

    result = migrate_model(tmp_path, "old-model", "new-model")
    content = source.read_text()

    assert result["replacements"] == 2
    assert "# retain this comment" in content
    assert 'documentation = "old-model"' in content
    assert content.count("new-model") == 2
