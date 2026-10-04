import logging
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from versionweaver.persistence.models import OutboxEvent

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        """Publish one event or raise so it can be retried."""


class LoggingPublisher:
    """Development publisher; replace with Kafka, NATS, SNS, or a webhook adapter."""

    def publish(self, event_type: str, payload: dict[str, object]) -> None:
        logger.info("integration event published", extra={"event_type": event_type, **payload})


def dispatch_outbox(
    session: Session,
    publisher: EventPublisher,
    *,
    batch_size: int = 100,
) -> tuple[int, int]:
    """Dispatch one locked batch with at-least-once delivery semantics."""
    events = list(
        session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        )
    )
    published = 0
    failed = 0
    for event in events:
        event.attempts += 1
        try:
            publisher.publish(event.event_type, event.payload)
        except Exception as exc:
            event.last_error = f"{type(exc).__name__}: {exc}"[:20_000]
            failed += 1
        else:
            event.published_at = datetime.now(UTC)
            event.last_error = None
            published += 1
    session.commit()
    return published, failed
