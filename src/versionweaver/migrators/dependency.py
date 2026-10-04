import re
from pathlib import Path
from typing import Any


class DependencyNotFoundError(ValueError):
    pass


def _name_pattern(name: str) -> str:
    parts = re.split(r"[-_.]+", name)
    return r"[-_.]+".join(re.escape(part) for part in parts)


def migrate_dependency(
    root: Path, dependency_name: str, to_version: str, manifest_paths: list[str] | None = None
) -> dict[str, Any]:
    root = root.resolve()
    candidates = [root / path for path in manifest_paths or []]
    if not candidates:
        candidates = [root / "pyproject.toml", *root.glob("requirements*.txt")]
    changed: list[str] = []
    replacements = 0
    package = _name_pattern(dependency_name)

    patterns = [
        (
            # Poetry table entries: package = "constraint".
            re.compile(
                rf"(?im)^(?P<prefix>\s*{package}\s*=\s*[\"'])"
                rf"(?P<constraint>[^\"']+)(?P<suffix>[\"']\s*(?:#.*)?)$"
            ),
            False,
        ),
        (
            # PEP 508 list entries and requirements files. A lone '=' is deliberately excluded
            # so Poetry/TOML assignments cannot become invalid requirement expressions.
            re.compile(
                rf"(?im)^(?P<prefix>\s*[\"']?{package}(?:\[[^]]+\])?\s*)"
                rf"(?P<constraint>(?:(?:===|==|~=|!=|>=|<=|>|<).*?)?)"
                rf"(?P<suffix>[\"']?\s*,?\s*(?:#.*)?)$"
            ),
            True,
        ),
    ]

    for path in candidates:
        if not path.is_file() or root not in path.resolve().parents:
            continue
        original = path.read_text()
        updated = original
        for pattern, add_pep508_operator in patterns:

            def replacement(match: re.Match[str], add_operator: bool = add_pep508_operator) -> str:
                return (
                    f"{match.group('prefix')}=={to_version}{match.group('suffix')}"
                    if add_operator
                    else f"{match.group('prefix')}{to_version}{match.group('suffix')}"
                )

            updated, count = pattern.subn(replacement, updated)
            replacements += count
        if updated != original:
            path.write_text(updated)
            changed.append(str(path.relative_to(root)))

    if replacements == 0:
        raise DependencyNotFoundError(f"dependency {dependency_name!r} not found in manifests")
    return {"changed_files": changed, "replacements": replacements}
