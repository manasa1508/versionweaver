import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from versionweaver.config import Settings


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class Sandbox(Protocol):
    def run(
        self, workspace: Path, command: str, timeout_seconds: int, network: bool
    ) -> CommandResult:
        pass


def _tail_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")[-100_000:]
    return value[-100_000:]


def _completed_result(
    command: str, started: float, process: subprocess.CompletedProcess[str]
) -> CommandResult:
    return CommandResult(
        command=command,
        exit_code=process.returncode,
        stdout=process.stdout[-100_000:],
        stderr=process.stderr[-100_000:],
        duration_ms=int((time.monotonic() - started) * 1000),
    )


class ContainerSandbox:
    def __init__(self, engine: str, image: str) -> None:
        if not shutil.which(engine):
            raise RuntimeError(f"sandbox engine is unavailable: {engine}")
        self.engine = engine
        self.image = image

    def run(
        self, workspace: Path, command: str, timeout_seconds: int, network: bool
    ) -> CommandResult:
        args = [
            self.engine,
            "run",
            "--rm",
            "--init",
            "--cpus",
            "1.0",
            "--memory",
            "1g",
            "--pids-limit",
            "256",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=256m",
            "--network",
            "bridge" if network else "none",
            "--volume",
            f"{workspace.resolve()}:/workspace:rw",
            "--workdir",
            "/workspace",
            self.image,
            "/bin/sh",
            "-lc",
            command,
        ]
        started = time.monotonic()
        try:
            process = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                exit_code=124,
                stdout=_tail_output(exc.stdout),
                stderr=_tail_output(exc.stderr),
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )
        return _completed_result(command, started, process)


class LocalSandbox:
    def run(
        self, workspace: Path, command: str, timeout_seconds: int, network: bool
    ) -> CommandResult:
        del network
        started = time.monotonic()
        try:
            process = subprocess.run(
                ["/bin/sh", "-lc", command],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                exit_code=124,
                stdout=_tail_output(exc.stdout),
                stderr=_tail_output(exc.stderr),
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )
        return _completed_result(command, started, process)


def build_sandbox(settings: Settings) -> Sandbox:
    if settings.sandbox_engine == "local":
        if not settings.allow_unsafe_local_execution:
            raise RuntimeError("unsafe local execution is disabled")
        return LocalSandbox()
    return ContainerSandbox(settings.sandbox_engine, settings.sandbox_image)
