import shutil
import subprocess
from pathlib import Path


def materialize_source(source_uri: str, destination: Path, default_branch: str = "main") -> Path:
    source_path = Path(source_uri).expanduser()
    if source_path.exists():
        shutil.copytree(
            source_path.resolve(),
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".venv", "venv", "node_modules", "__pycache__"),
        )
        return destination
    process = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            default_branch,
            "--",
            source_uri,
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"git clone failed: {process.stderr[-4000:]}")
    return destination


def git_diff(workspace: Path) -> str:
    if not (workspace / ".git").exists():
        return ""
    process = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--binary"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return process.stdout[-500_000:]
