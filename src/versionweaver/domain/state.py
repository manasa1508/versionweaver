from versionweaver.domain.enums import ChangeStatus

ALLOWED_TRANSITIONS: dict[ChangeStatus, set[ChangeStatus]] = {
    ChangeStatus.DRAFT: {ChangeStatus.PLANNED, ChangeStatus.CANCELLED},
    ChangeStatus.PLANNED: {ChangeStatus.APPROVED, ChangeStatus.CANCELLED},
    ChangeStatus.APPROVED: {ChangeStatus.QUEUED, ChangeStatus.CANCELLED},
    ChangeStatus.QUEUED: {ChangeStatus.RUNNING, ChangeStatus.CANCELLED},
    ChangeStatus.RUNNING: {
        ChangeStatus.VERIFYING,
        ChangeStatus.FAILED,
        ChangeStatus.BLOCKED,
        ChangeStatus.CANCELLED,
    },
    ChangeStatus.VERIFYING: {
        ChangeStatus.SUCCEEDED,
        ChangeStatus.FAILED,
        ChangeStatus.BLOCKED,
        ChangeStatus.CANCELLED,
    },
    ChangeStatus.SUCCEEDED: set(),
    ChangeStatus.FAILED: set(),
    ChangeStatus.BLOCKED: set(),
    ChangeStatus.CANCELLED: set(),
}


class InvalidStateTransition(ValueError):
    pass


def ensure_transition(current: ChangeStatus, target: ChangeStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransition(f"cannot transition change from {current} to {target}")
