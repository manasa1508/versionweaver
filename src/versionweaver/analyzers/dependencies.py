import re
import tomllib
from pathlib import Path
from typing import Any

REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[(?P<extras>[^]]+)\])?\s*(?P<constraint>.*)$"
)
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_entry(line: str, path: Path, line_number: int) -> dict[str, Any] | None:
    value = line.strip()
    if not value or value.startswith(("#", "-r", "--", "git+", "http://", "https://")):
        return None
    value = value.split(";", 1)[0].strip()
    match = REQUIREMENT_RE.match(value)
    if not match:
        return None
    return {
        "name": _normalized(match.group("name")),
        "constraint": match.group("constraint").strip() or "*",
        "source": str(path),
        "line": line_number,
        "group": "requirements",
    }


def _pyproject_entries(path: Path, root: Path) -> list[dict[str, Any]]:
    try:
        data = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return []
    entries: list[dict[str, Any]] = []

    project = data.get("project", {})
    for group, requirements in (
        ("main", project.get("dependencies", [])),
        *[
            (f"optional:{name}", values)
            for name, values in project.get("optional-dependencies", {}).items()
        ],
    ):
        for requirement in requirements:
            parsed = _requirement_entry(str(requirement), path.relative_to(root), 0)
            if parsed:
                parsed["group"] = group
                entries.append(parsed)

    poetry = data.get("tool", {}).get("poetry", {})
    for group, dependencies in (
        ("poetry:main", poetry.get("dependencies", {})),
        ("poetry:dev", poetry.get("group", {}).get("dev", {}).get("dependencies", {})),
    ):
        for name, constraint in dependencies.items():
            if name.lower() == "python":
                continue
            entries.append(
                {
                    "name": _normalized(name),
                    "constraint": constraint if isinstance(constraint, str) else constraint,
                    "source": str(path.relative_to(root)),
                    "line": 0,
                    "group": group,
                }
            )
    return entries


def scan_dependencies(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    entries: list[dict[str, Any]] = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        entries.extend(_pyproject_entries(pyproject, root))

    for path in root.rglob("requirements*.txt"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        try:
            lines = path.read_text().splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            parsed = _requirement_entry(line, path.relative_to(root), number)
            if parsed:
                entries.append(parsed)
    return sorted(entries, key=lambda item: (item["name"], item["source"], item["group"]))
