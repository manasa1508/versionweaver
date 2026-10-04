from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from versionweaver import __version__
from versionweaver.api.dependencies import (
    require_admin_token,
    require_control_token,
    require_runner_token,
)
from versionweaver.api.pagination import decode_cursor, encode_cursor
from versionweaver.application.service import (
    ConflictError,
    NotFoundError,
    approve_change,
    cancel_change,
    complete_job,
    create_change,
    heartbeat_job,
    lease_job,
)
from versionweaver.config import get_settings
from versionweaver.domain.enums import ChangeStatus, JobStatus
from versionweaver.evidence.store import build_artifact_store
from versionweaver.persistence.database import get_session
from versionweaver.persistence.models import (
    AuditEvent,
    ChangeRequest,
    Evidence,
    Job,
    OutboxEvent,
    Project,
)
from versionweaver.schemas import (
    ApprovalRequest,
    AuditEventRead,
    CancellationRequest,
    ChangeCreate,
    ChangeRead,
    DashboardSummary,
    EvidenceRead,
    HealthResponse,
    InventoryUpload,
    JobCompletion,
    JobHeartbeat,
    JobPayload,
    JobRead,
    OutboxEventRead,
    ProjectCreate,
    ProjectRead,
)

SessionDependency = Annotated[Session, Depends(get_session)]
public_router = APIRouter()
control_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_control_token)])
runner_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_runner_token)])
admin_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin_token)])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError | ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="internal error")


@public_router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@public_router.get("/health/ready", response_model=HealthResponse)
def ready(response: Response, session: SessionDependency) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="ok", version=__version__)
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="error", version=__version__)


@control_router.post("/projects", response_model=ProjectRead, status_code=201)
def create_project(request: ProjectCreate, session: SessionDependency) -> Project:
    if session.scalar(select(Project).where(Project.name == request.name)):
        raise HTTPException(status_code=409, detail="project name already exists")
    project = Project(**request.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@control_router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(session: SessionDependency) -> DashboardSummary:
    change_rows = session.execute(
        select(ChangeRequest.status, func.count(ChangeRequest.id)).group_by(ChangeRequest.status)
    ).all()
    kind_rows = session.execute(
        select(ChangeRequest.kind, func.count(ChangeRequest.id)).group_by(ChangeRequest.kind)
    ).all()
    job_rows = session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
    changes_by_status = {str(row[0]): int(row[1]) for row in change_rows}
    changes_by_kind = {str(row[0]): int(row[1]) for row in kind_rows}
    jobs_by_status = {str(row[0]): int(row[1]) for row in job_rows}

    active_statuses = {
        ChangeStatus.PLANNED.value,
        ChangeStatus.APPROVED.value,
        ChangeStatus.QUEUED.value,
        ChangeStatus.RUNNING.value,
        ChangeStatus.VERIFYING.value,
    }
    finished = sum(
        changes_by_status.get(status_value, 0)
        for status_value in (
            ChangeStatus.SUCCEEDED.value,
            ChangeStatus.FAILED.value,
            ChangeStatus.BLOCKED.value,
        )
    )
    succeeded = changes_by_status.get(ChangeStatus.SUCCEEDED.value, 0)
    queue_depth = sum(
        jobs_by_status.get(status_value, 0)
        for status_value in (
            JobStatus.QUEUED.value,
            JobStatus.LEASED.value,
            JobStatus.RUNNING.value,
        )
    )
    return DashboardSummary(
        project_count=session.scalar(select(func.count()).select_from(Project)) or 0,
        change_count=sum(changes_by_status.values()),
        active_change_count=sum(
            count
            for status_value, count in changes_by_status.items()
            if status_value in active_statuses
        ),
        evidence_count=session.scalar(select(func.count()).select_from(Evidence)) or 0,
        queue_depth=queue_depth,
        dead_letter_count=jobs_by_status.get(JobStatus.DEAD_LETTER.value, 0),
        unpublished_event_count=session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None))
        )
        or 0,
        success_rate=round((succeeded / finished) * 100, 1) if finished else 0.0,
        changes_by_status=changes_by_status,
        changes_by_kind=changes_by_kind,
        jobs_by_status=jobs_by_status,
        generated_at=datetime.now(UTC),
    )


@control_router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    response: Response,
    session: SessionDependency,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, min_length=1, max_length=120),
) -> list[Project]:
    statement = select(Project).order_by(Project.created_at.desc(), Project.id.desc())
    if search:
        statement = statement.where(Project.name.ilike(f"%{search}%"))
    if cursor:
        try:
            created_at, item_id = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        statement = statement.where(
            or_(
                Project.created_at < created_at,
                and_(Project.created_at == created_at, Project.id < item_id),
            )
        )
    items = list(session.scalars(statement.limit(limit + 1)))
    if len(items) > limit:
        last = items[limit - 1]
        response.headers["X-Next-Cursor"] = encode_cursor(last.created_at, last.id)
        items = items[:limit]
    return items


@control_router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: SessionDependency) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@control_router.put("/projects/{project_id}/inventory", response_model=ProjectRead)
def upload_inventory(
    project_id: str, request: InventoryUpload, session: SessionDependency
) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    project.inventory = request.inventory
    session.commit()
    session.refresh(project)
    return project


@control_router.post("/changes", response_model=ChangeRead, status_code=201)
def post_change(
    request: ChangeCreate,
    session: SessionDependency,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=8, max_length=160)
    ] = None,
) -> ChangeRequest:
    try:
        return create_change(session, request, idempotency_key=idempotency_key)
    except Exception as exc:
        raise _translate_error(exc) from exc


@control_router.get("/changes", response_model=list[ChangeRead])
def list_changes(
    response: Response,
    session: SessionDependency,
    project_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    kind: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, min_length=1, max_length=240),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ChangeRequest]:
    statement = select(ChangeRequest).order_by(
        ChangeRequest.created_at.desc(), ChangeRequest.id.desc()
    )
    if project_id:
        statement = statement.where(ChangeRequest.project_id == project_id)
    if status_filter:
        statement = statement.where(ChangeRequest.status == status_filter)
    if kind:
        statement = statement.where(ChangeRequest.kind == kind)
    if search:
        statement = statement.where(ChangeRequest.title.ilike(f"%{search}%"))
    if cursor:
        try:
            created_at, item_id = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        statement = statement.where(
            or_(
                ChangeRequest.created_at < created_at,
                and_(ChangeRequest.created_at == created_at, ChangeRequest.id < item_id),
            )
        )
    items = list(session.scalars(statement.limit(limit + 1)))
    if len(items) > limit:
        last = items[limit - 1]
        response.headers["X-Next-Cursor"] = encode_cursor(last.created_at, last.id)
        items = items[:limit]
    return items


@control_router.get("/changes/{change_id}", response_model=ChangeRead)
def get_change(change_id: str, session: SessionDependency) -> ChangeRequest:
    change = session.get(ChangeRequest, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="change not found")
    return change


@control_router.post("/changes/{change_id}/approve", response_model=ChangeRead)
def approve(change_id: str, request: ApprovalRequest, session: SessionDependency) -> ChangeRequest:
    try:
        change, _ = approve_change(
            session, change_id, request.actor, expected_version=request.expected_version
        )
        return change
    except Exception as exc:
        raise _translate_error(exc) from exc


@control_router.post("/changes/{change_id}/cancel", response_model=ChangeRead)
def cancel(
    change_id: str, request: CancellationRequest, session: SessionDependency
) -> ChangeRequest:
    try:
        return cancel_change(
            session,
            change_id=change_id,
            actor=request.actor,
            reason=request.reason,
            expected_version=request.expected_version,
        )
    except Exception as exc:
        raise _translate_error(exc) from exc


@runner_router.get("/jobs/lease", response_model=JobPayload | None)
def lease(
    session: SessionDependency,
    runner_id: str = Query(min_length=1, max_length=200),
    lease_seconds: int = Query(default=120, ge=30, le=3600),
) -> JobPayload | Response:
    payload = lease_job(session, runner_id=runner_id, lease_seconds=lease_seconds)
    if payload is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return payload


@runner_router.post("/jobs/{job_id}/heartbeat")
def heartbeat(job_id: str, request: JobHeartbeat, session: SessionDependency) -> dict[str, Any]:
    try:
        job = heartbeat_job(
            session,
            job_id=job_id,
            runner_id=request.runner_id,
            lease_token=request.lease_token,
            extend_seconds=request.extend_seconds,
        )
        return {"job_id": job.id, "status": job.status, "lease_expires_at": job.lease_expires_at}
    except Exception as exc:
        raise _translate_error(exc) from exc


@runner_router.post("/jobs/{job_id}/complete", response_model=EvidenceRead)
def complete(job_id: str, request: JobCompletion, session: SessionDependency) -> Evidence:
    try:
        _, evidence = complete_job(
            session,
            job_id=job_id,
            completion=request,
            artifact_store=build_artifact_store(get_settings()),
        )
        return evidence
    except Exception as exc:
        raise _translate_error(exc) from exc


@control_router.get("/changes/{change_id}/evidence", response_model=list[EvidenceRead])
def list_evidence(change_id: str, session: SessionDependency) -> list[Evidence]:
    return list(
        session.scalars(
            select(Evidence).where(Evidence.change_id == change_id).order_by(Evidence.created_at)
        )
    )


@control_router.get("/evidence/{evidence_id}/content")
def evidence_content(evidence_id: str, session: SessionDependency) -> dict[str, Any]:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    document = build_artifact_store(get_settings()).get_json(evidence.storage_uri)
    return document


@control_router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    response: Response,
    session: SessionDependency,
    change_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Job]:
    statement = select(Job).order_by(Job.created_at.desc(), Job.id.desc())
    if change_id:
        statement = statement.where(Job.change_id == change_id)
    if status_filter:
        statement = statement.where(Job.status == status_filter)
    if cursor:
        try:
            created_at, item_id = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        statement = statement.where(
            or_(Job.created_at < created_at, and_(Job.created_at == created_at, Job.id < item_id))
        )
    items = list(session.scalars(statement.limit(limit + 1)))
    if len(items) > limit:
        last = items[limit - 1]
        response.headers["X-Next-Cursor"] = encode_cursor(last.created_at, last.id)
        items = items[:limit]
    return items


@control_router.get("/jobs/{job_id}")
def get_job(job_id: str, session: SessionDependency) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "id": job.id,
        "change_id": job.change_id,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "lease_owner": job.lease_owner,
        "lease_expires_at": job.lease_expires_at,
        "last_error": job.last_error,
    }


@admin_router.get("/audit-events", response_model=list[AuditEventRead])
def list_audit_events(
    response: Response,
    session: SessionDependency,
    change_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AuditEvent]:
    statement = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    if change_id:
        statement = statement.where(AuditEvent.change_id == change_id)
    if cursor:
        try:
            created_at, item_id = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        statement = statement.where(
            or_(
                AuditEvent.created_at < created_at,
                and_(AuditEvent.created_at == created_at, AuditEvent.id < item_id),
            )
        )
    items = list(session.scalars(statement.limit(limit + 1)))
    if len(items) > limit:
        last = items[limit - 1]
        response.headers["X-Next-Cursor"] = encode_cursor(last.created_at, last.id)
        items = items[:limit]
    return items


@admin_router.get("/outbox-events", response_model=list[OutboxEventRead])
def list_outbox_events(
    session: SessionDependency,
    unpublished_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[OutboxEvent]:
    statement = select(OutboxEvent).order_by(OutboxEvent.occurred_at.desc()).limit(limit)
    if unpublished_only:
        statement = statement.where(OutboxEvent.published_at.is_(None))
    return list(session.scalars(statement))
