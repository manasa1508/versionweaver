import ast
from pathlib import Path
from typing import Any

from versionweaver.analyzers.models import MODEL_VARIABLES

IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}


class ModelLiteralCollector(ast.NodeVisitor):
    """Collect exact literals only when they configure a recognized model field."""

    def __init__(self, old: str) -> None:
        self.old = old
        self.nodes: dict[tuple[int, int, int, int], ast.Constant] = {}

    def _collect(self, value: ast.AST) -> None:
        for node in ast.walk(value):
            if isinstance(node, ast.Constant) and node.value == self.old:
                key = (node.lineno, node.col_offset, node.end_lineno or 0, node.end_col_offset or 0)
                self.nodes[key] = node

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(
            isinstance(target, ast.Name) and target.id.lower() in MODEL_VARIABLES
            for target in node.targets
        ):
            self._collect(node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            isinstance(node.target, ast.Name)
            and node.target.id.lower() in MODEL_VARIABLES
            and node.value is not None
        ):
            self._collect(node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if keyword.arg and keyword.arg.lower() in MODEL_VARIABLES:
                self._collect(keyword.value)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value.lower() in MODEL_VARIABLES
            ):
                self._collect(value)
        self.generic_visit(node)


def _byte_offset(lines: list[bytes], line: int, column: int) -> int:
    return sum(len(item) for item in lines[: line - 1]) + column


def _rewrite_literals(source: str, nodes: list[ast.Constant], value: str) -> str:
    encoded = source.encode("utf-8")
    lines = encoded.splitlines(keepends=True)
    locations: list[tuple[int, int]] = []
    for node in nodes:
        if node.end_lineno is None or node.end_col_offset is None:
            continue
        locations.append(
            (
                _byte_offset(lines, node.lineno, node.col_offset),
                _byte_offset(lines, node.end_lineno, node.end_col_offset),
            )
        )

    replacement = repr(value).encode("utf-8")
    for start, end in sorted(locations, reverse=True):
        encoded = encoded[:start] + replacement + encoded[end:]
    return encoded.decode("utf-8")


def migrate_model(root: Path, from_model: str, to_model: str) -> dict[str, Any]:
    root = root.resolve()
    changed: list[str] = []
    replacements = 0
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        try:
            source = path.read_text()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue
        collector = ModelLiteralCollector(from_model)
        collector.visit(tree)
        nodes = list(collector.nodes.values())
        if nodes:
            path.write_text(_rewrite_literals(source, nodes, to_model))
            changed.append(str(path.relative_to(root)))
            replacements += len(nodes)
    if replacements == 0:
        raise ValueError(
            f"model literal {from_model!r} not found in recognized model configuration"
        )
    return {"changed_files": changed, "replacements": replacements}
