from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from versionweaver.domain.enums import ChangeKind


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]+$")
    source_uri: str = Field(min_length=1, max_length=2000)
    default_branch: str = Field(default="main", min_length=1, max_length=120)


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inventory: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class InventoryUpload(BaseModel):
    inventory: dict[str, Any]


class EvaluationCase(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    messages: list[dict[str, str]] = Field(min_length=1)
    expected_contains: list[str] = Field(default_factory=list)
    forbidden_contains: list[str] = Field(default_factory=list)
    required_json_keys: list[str] = Field(default_factory=list)


class ChangeSpec(BaseModel):
    kind: ChangeKind
    dependency_name: str | None = None
    from_version: str | None = None
    to_version: str | None = None
    from_provider: str | None = None
    to_provider: str | None = None
    from_model: str | None = None
    to_model: str | None = None
    manifest_paths: list[str] = Field(default_factory=list)
    verification_commands: list[str] = Field(
        default_factory=lambda: ["python -m compileall -q ."], max_length=20
    )
    evaluation_cases: list[EvaluationCase] = Field(default_factory=list, max_length=1000)
    model_base_url: str | None = None
    model_api_key_env: str | None = None
    allow_network: bool = False
    allow_baseline_failure: bool = False
    max_repair_attempts: int = Field(default=0, ge=0, le=5)
    timeout_seconds: int = Field(default=600, ge=10, le=7200)

    @model_validator(mode="after")
    def validate_by_kind(self) -> "ChangeSpec":
        if self.kind == ChangeKind.DEPENDENCY:
            missing = [
                name
                for name, value in {
                    "dependency_name": self.dependency_name,
                    "to_version": self.to_version,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"dependency change missing: {', '.join(missing)}")
        if self.kind == ChangeKind.MODEL:
            missing = [
                name
                for name, value in {
                    "from_model": self.from_model,
                    "to_model": self.to_model,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"model change missing: {', '.join(missing)}")
        return self


class ChangeCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=3, max_length=240)
    requested_by: str = Field(default="cli-user", min_length=1, max_length=200)
    spec: ChangeSpec


class ChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: str
    status: str
    title: str
    spec: dict[str, Any]
    risk_score: int
    risk_reasons: list[str]
    requested_by: str
    approved_by: str | None
    approved_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class ApprovalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
    expected_version: int | None = Field(default=None, ge=1)


class CancellationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=2000)
    expected_version: int | None = Field(default=None, ge=1)


class JobPayload(BaseModel):
    job_id: str
    change_id: str
    lease_token: str
    source_uri: str
    default_branch: str
    spec: ChangeSpec
    lease_expires_at: datetime


class JobHeartbeat(BaseModel):
    runner_id: str = Field(min_length=1, max_length=200)
    lease_token: str = Field(min_length=16, max_length=128)
    extend_seconds: int = Field(default=120, ge=30, le=3600)


class JobCompletion(BaseModel):
    runner_id: str = Field(min_length=1, max_length=200)
    lease_token: str = Field(min_length=16, max_length=128)
    outcome: Literal["succeeded", "failed", "blocked"]
    evidence: dict[str, Any]
    error: str | None = Field(default=None, max_length=20000)


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str
    kind: str
    storage_uri: str
    sha256: str
    summary: dict[str, Any]
    created_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str | None
    actor: str
    action: str
    details: dict[str, Any]
    created_at: datetime


class OutboxEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime
    published_at: datetime | None
    attempts: int
    last_error: str | None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    version: str
