import logging
import threading

from versionweaver.client import VersionWeaverClient
from versionweaver.config import Settings
from versionweaver.sandbox.runner import build_sandbox
from versionweaver.schemas import JobCompletion
from versionweaver.workers.executor import execute_change

logger = logging.getLogger(__name__)


def _heartbeat_loop(
    *,
    stop: threading.Event,
    client: VersionWeaverClient,
    job_id: str,
    runner_id: str,
    lease_token: str,
    lease_seconds: int,
) -> None:
    interval = max(10, lease_seconds // 3)
    while not stop.wait(interval):
        try:
            client.heartbeat(job_id, runner_id, lease_token, lease_seconds)
        except Exception:
            logger.exception(
                "job heartbeat failed",
                extra={"job_id": job_id, "runner_id": runner_id},
            )


def run_once(settings: Settings) -> bool:
    client = VersionWeaverClient(
        settings.server_url, settings.runner_api_token or settings.api_token, timeout=60
    )
    job = client.lease_job(settings.runner_id, settings.runner_lease_seconds)
    if job is None:
        return False
    logger.info(
        "leased migration job",
        extra={"job_id": job.job_id, "change_id": job.change_id, "runner_id": settings.runner_id},
    )
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat_loop,
        kwargs={
            "stop": stop,
            "client": client,
            "job_id": job.job_id,
            "runner_id": settings.runner_id,
            "lease_token": job.lease_token,
            "lease_seconds": settings.runner_lease_seconds,
        },
        daemon=True,
    )
    heartbeat.start()
    try:
        sandbox = build_sandbox(settings)
        outcome, evidence, error = execute_change(
            source_uri=job.source_uri,
            default_branch=job.default_branch,
            spec=job.spec,
            sandbox=sandbox,
            settings=settings,
            change_id=job.change_id,
            job_id=job.job_id,
        )
    except Exception as exc:
        logger.exception("runner execution crashed", extra={"job_id": job.job_id})
        outcome = "failed"
        error = f"{type(exc).__name__}: {exc}"
        evidence = {
            "schema_version": "1.0",
            "change_id": job.change_id,
            "job_id": job.job_id,
            "outcome": outcome,
            "reason": "runner execution crashed",
            "error": error,
        }
    finally:
        stop.set()
        heartbeat.join(timeout=2)

    client.complete_job(
        job.job_id,
        JobCompletion(
            runner_id=settings.runner_id,
            lease_token=job.lease_token,
            outcome=outcome,
            evidence=evidence,
            error=error,
        ),
    )
    logger.info(
        "completed migration job",
        extra={"job_id": job.job_id, "change_id": job.change_id, "runner_id": settings.runner_id},
    )
    return True


def run_forever(settings: Settings, stop: threading.Event | None = None) -> None:
    shutdown = stop or threading.Event()
    while not shutdown.is_set():
        worked = run_once(settings)
        if not worked:
            shutdown.wait(settings.runner_poll_seconds)
