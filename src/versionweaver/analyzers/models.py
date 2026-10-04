import ast
from pathlib import Path
from typing import Any

MODEL_VARIABLES = {
    "model",
    "model_id",
    "model_name",
    "llm_model",
    "embedding_model",
    "chat_model",
}
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}


def _string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"getenv", "get"}
        and node.args
    ):
        env_name = _string_value(node.args[0])
        fallback = _string_value(node.args[1]) if len(node.args) > 1 else None
        return f"env:{env_name}" + (f"|default:{fallback}" if fallback else "")
    return None


class ModelUsageVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.usages: list[dict[str, Any]] = []

    def visit_Call(self, node: ast.Call) -> None:
        for keyword in node.keywords:
            if (
                keyword.arg
                and keyword.arg.lower() in MODEL_VARIABLES
                and (value := _string_value(keyword.value))
            ):
                self.usages.append(
                    {
                        "model": value,
                        "source": str(self.path),
                        "line": node.lineno,
                        "kind": keyword.arg.lower(),
                    }
                )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        value = _string_value(node.value)
        if value:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.lower() in MODEL_VARIABLES:
                    self.usages.append(
                        {
                            "model": value,
                            "source": str(self.path),
                            "line": node.lineno,
                            "kind": target.id.lower(),
                        }
                    )
        self.generic_visit(node)


def scan_models(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    usages: list[dict[str, Any]] = []
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        visitor = ModelUsageVisitor(path.relative_to(root))
        visitor.visit(tree)
        usages.extend(visitor.usages)
    return sorted(usages, key=lambda item: (item["model"], item["source"], item["line"]))
