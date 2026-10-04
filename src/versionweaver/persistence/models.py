import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from versionweaver.domain.enums import ChangeStatus, JobStatus
from versionweaver.persistence.database import Base


def uuid_string() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_uri: Mapped[str] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(120), default="main")
    inventory: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    changes: Mapped[list["ChangeRequest"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ChangeRequest(Base):
    __tablename__ = "change_requests"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_change_requests_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default=ChangeStatus.PLANNED, index=True)
    title: Mapped[str] = mapped_column(String(240))
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_reasons: Mapped[list[str]] = mapped_column(JSON)
    requested_by: Mapped[str] = mapped_column(String(200), default="unknown")
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    project: Mapped[Project] = relationship(back_populates="changes")
    jobs: Mapped[list["Job"]] = relationship(back_populates="change", cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="change", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"version_id_col": version}


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_lease", "status", "lease_expires_at", "created_at"),
        UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    lease_owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )

    change: Mapped[ChangeRequest] = relationship(back_populates="jobs")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80), default="migration-report")
    storage_uri: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    change: Mapped[ChangeRequest] = relationship(back_populates="evidence")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    change_id: Mapped[str | None] = mapped_column(
        ForeignKey("change_requests.id"), nullable=True, index=True
    )
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(120), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    aggregate_type: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
