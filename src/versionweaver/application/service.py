import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from versionweaver.domain.enums import ChangeStatus, JobStatus
from versionweaver.domain.risk import assess_risk
from versionweaver.domain.state import ensure_transition
from versionweaver.evidence.store import ArtifactStore, canonical_json, digest_document
from versionweaver.persistence.models import (
    AuditEvent,
    ChangeRequest,
    Evidence,
    Job,
    OutboxEvent,
    Project,
)
from versionweaver.schemas import ChangeCreate, JobCompletion, JobPayload


class NotFoundError(LookupError):
    pass


class ConflictError(ValueError):
    pass


def _audit(
    session: Session,
    *,
    actor: str,
    action: str,
    change_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            change_id=change_id,
            details=details or {},
        )
    )


def _event(
    session: Session,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Write an integration event in the same transaction as domain state."""
    session.add(
        OutboxEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
    )


def create_change(
    session: Session, request: ChangeCreate, idempotency_key: str | None = None
) -> ChangeRequest:
    request_document = request.model_dump(mode="json")
    request_hash = sha256(canonical_json(request_document)).hexdigest()
    if idempotency_key:
        existing = session.scalar(
            select(ChangeRequest).where(ChangeRequest.idempotency_key == idempotency_key)
        )
        if existing:
            if existing.request_hash != request_hash:
                raise ConflictError("idempotency key was already used with a different request")
            return existing
    project = session.get(Project, request.project_id)
    if project is None:
        raise NotFoundError("project not found")
    spec = request.spec.model_dump(mode="json")
    assessment = assess_risk(request.spec.kind, spec)
    change = ChangeRequest(
        project_id=request.project_id,
        kind=request.spec.kind.value,
        status=ChangeStatus.PLANNED.value,
        title=request.title,
        spec=spec,
        risk_score=assessment.score,
        risk_reasons=assessment.reasons,
        requested_by=request.requested_by,
        idempotency_key=idempotency_key,
        request_hash=request_hash if idempotency_key else None,
    )
    session.add(change)
    session.flush()
    _audit(
        session,
        actor=request.requested_by,
        action="change.created",
        change_id=change.id,
        details={"risk_score": assessment.score, "risk_level": assessment.level},
    )
    _event(
        session,
        aggregate_type="change",
        aggregate_id=change.id,
        event_type="change.created",
        payload={"change_id": change.id, "project_id": change.project_id, "kind": change.kind},
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if idempotency_key:
            existing = session.scalar(
                select(ChangeRequest).where(ChangeRequest.idempotency_key == idempotency_key)
            )
            if existing and existing.request_hash == request_hash:
                return existing
        raise ConflictError("change could not be created due to a uniqueness conflict") from exc
    session.refresh(change)
    return change


def approve_change(
    session: Session,
    change_id: str,
    actor: str,
    expected_version: int | None = None,
) -> tuple[ChangeRequest, Job]:
    change = session.get(ChangeRequest, change_id)
    if change is None:
        raise NotFoundError("change not found")
    if expected_version is not None and change.version != expected_version:
        raise ConflictError(
            f"change version conflict: expected {expected_version}, current {change.version}"
        )
    current = ChangeStatus(change.status)
    ensure_transition(current, ChangeStatus.APPROVED)
    change.status = ChangeStatus.APPROVED.value
    change.approved_by = actor
    change.approved_at = datetime.now(UTC)
    ensure_transition(ChangeStatus.APPROVED, ChangeStatus.QUEUED)
    change.status = ChangeStatus.QUEUED.value
    job = Job(
        change_id=change.id,
        idempotency_key=f"execute:{change.id}",
        status=JobStatus.QUEUED.value,
        max_attempts=3,
    )
    session.add(job)
    session.flush()
    _audit(session, actor=actor, action="change.approved", change_id=change.id)
    _event(
        session,
        aggregate_type="change",
        aggregate_id=change.id,
        event_type="change.approved",
        payload={"change_id": change.id, "job_id": job.id, "approved_by": actor},
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("change already has an execution job") from exc
    session.refresh(change)
    session.refresh(job)
    return change, job


def lease_job(session: Session, *, runner_id: str, lease_seconds: int) -> JobPayload | None:
    now = datetime.now(UTC)
    session.execute(
        update(Job)
        .where(
            Job.status.in_([JobStatus.LEASED.value, JobStatus.RUNNING.value]),
            Job.lease_expires_at < now,
            Job.attempts >= Job.max_attempts,
        )
        .values(status=JobStatus.DEAD_LETTER.value, lease_owner=None, lease_token=None)
    )
    statement = (
        select(Job)
        .options(joinedload(Job.change).joinedload(ChangeRequest.project))
        .where(
            or_(
                Job.status == JobStatus.QUEUED.value,
                (
                    Job.status.in_([JobStatus.LEASED.value, JobStatus.RUNNING.value])
                    & (Job.lease_expires_at < now)
                    & (Job.attempts < Job.max_attempts)
                ),
            )
        )
        .order_by(Job.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = session.scalar(statement)
    if job is None:
        session.commit()
        return None
    token = secrets.token_urlsafe(32)
    job.status = JobStatus.LEASED.value
    job.lease_owner = runner_id
    job.lease_token = token
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempts += 1
    job.change.status = ChangeStatus.RUNNING.value
    _audit(
        session,
        actor=runner_id,
        action="job.leased",
        change_id=job.change_id,
        details={"job_id": job.id, "attempt": job.attempts},
    )
    _event(
        session,
        aggregate_type="job",
        aggregate_id=job.id,
        event_type="job.leased",
        payload={
            "job_id": job.id,
            "change_id": job.change_id,
            "runner_id": runner_id,
            "attempt": job.attempts,
        },
    )
    session.commit()
    return JobPayload(
        job_id=job.id,
        change_id=job.change_id,
        lease_token=token,
        source_uri=job.change.project.source_uri,
        default_branch=job.change.project.default_branch,
        spec=job.change.spec,
        lease_expires_at=job.lease_expires_at,
    )


def heartbeat_job(
    session: Session,
    *,
    job_id: str,
    runner_id: str,
    lease_token: str,
    extend_seconds: int,
) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise NotFoundError("job not found")
    if job.lease_owner != runner_id or not secrets.compare_digest(
        job.lease_token or "", lease_token
    ):
        raise ConflictError("runner does not hold this lease")
    if job.status not in {JobStatus.LEASED.value, JobStatus.RUNNING.value}:
        raise ConflictError("job is not active")
    job.status = JobStatus.RUNNING.value
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=extend_seconds)
    session.commit()
    session.refresh(job)
    return job


def complete_job(
    session: Session,
    *,
    job_id: str,
    completion: JobCompletion,
    artifact_store: ArtifactStore,
) -> tuple[Job, Evidence]:
    job = session.scalar(
        select(Job).options(joinedload(Job.change)).where(Job.id == job_id).with_for_update()
    )
    if job is None:
        raise NotFoundError("job not found")
    if job.lease_owner != completion.runner_id or not secrets.compare_digest(
        job.lease_token or "", completion.lease_token
    ):
        raise ConflictError("runner does not hold this lease")
    if job.status not in {JobStatus.LEASED.value, JobStatus.RUNNING.value}:
        raise ConflictError("job is already complete or inactive")

    digest = digest_document(completion.evidence)
    key = f"changes/{job.change_id}/attempt-{job.attempts}/{digest}.json"
    uri = artifact_store.put_json(key, completion.evidence)
    summary = {
        "outcome": completion.outcome,
        "reason": completion.evidence.get("reason"),
        "completed_at": completion.evidence.get("completed_at"),
    }
    evidence = Evidence(
        change_id=job.change_id,
        kind="migration-report",
        storage_uri=uri,
        sha256=digest,
        summary=summary,
    )
    session.add(evidence)

    target_change = {
        "succeeded": ChangeStatus.SUCCEEDED,
        "failed": ChangeStatus.FAILED,
        "blocked": ChangeStatus.BLOCKED,
    }[completion.outcome]
    current = ChangeStatus(job.change.status)
    if current == ChangeStatus.RUNNING:
        job.change.status = ChangeStatus.VERIFYING.value
        current = ChangeStatus.VERIFYING
    ensure_transition(current, target_change)
    job.change.status = target_change.value
    job.status = (
        JobStatus.SUCCEEDED.value if completion.outcome == "succeeded" else JobStatus.FAILED.value
    )
    job.last_error = completion.error
    job.lease_expires_at = None
    _audit(
        session,
        actor=completion.runner_id,
        action="job.completed",
        change_id=job.change_id,
        details={"job_id": job.id, "outcome": completion.outcome, "evidence_sha256": digest},
    )
    _event(
        session,
        aggregate_type="job",
        aggregate_id=job.id,
        event_type=f"job.{completion.outcome}",
        payload={
            "job_id": job.id,
            "change_id": job.change_id,
            "outcome": completion.outcome,
            "evidence_sha256": digest,
        },
    )
    session.commit()
    session.refresh(job)
    session.refresh(evidence)
    return job, evidence


def cancel_change(
    session: Session,
    *,
    change_id: str,
    actor: str,
    reason: str,
    expected_version: int | None = None,
) -> ChangeRequest:
    change = session.scalar(
        select(ChangeRequest).where(ChangeRequest.id == change_id).with_for_update()
    )
    if change is None:
        raise NotFoundError("change not found")
    if expected_version is not None and change.version != expected_version:
        raise ConflictError(
            f"change version conflict: expected {expected_version}, current {change.version}"
        )
    ensure_transition(ChangeStatus(change.status), ChangeStatus.CANCELLED)
    change.status = ChangeStatus.CANCELLED.value
    for job in change.jobs:
        if job.status == JobStatus.QUEUED.value:
            job.status = JobStatus.CANCELLED.value
    _audit(
        session,
        actor=actor,
        action="change.cancelled",
        change_id=change.id,
        details={"reason": reason},
    )
    _event(
        session,
        aggregate_type="change",
        aggregate_id=change.id,
        event_type="change.cancelled",
        payload={"change_id": change.id, "actor": actor, "reason": reason},
    )
    session.commit()
    session.refresh(change)
    return change
