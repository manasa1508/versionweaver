from enum import StrEnum


class ChangeKind(StrEnum):
    DEPENDENCY = "dependency"
    MODEL = "model"


class ChangeStatus(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    APPROVED = "approved"
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


TERMINAL_CHANGE_STATUSES = {
    ChangeStatus.SUCCEEDED,
    ChangeStatus.FAILED,
    ChangeStatus.BLOCKED,
    ChangeStatus.CANCELLED,
}
