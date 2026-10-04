from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from versionweaver.analyzers.dependencies import scan_dependencies
from versionweaver.analyzers.models import scan_models


def scan_repository(root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ValueError(f"repository path does not exist: {resolved}")
    dependencies = scan_dependencies(resolved)
    models = scan_models(resolved)
    return {
        "schema_version": "1.0",
        "scanned_at": datetime.now(UTC).isoformat(),
        "repository": str(resolved),
        "dependencies": dependencies,
        "models": models,
        "summary": {
            "dependency_count": len(dependencies),
            "model_usage_count": len(models),
        },
    }
