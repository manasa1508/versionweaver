from typing import Any

import pytest
from fastapi.testclient import TestClient

from versionweaver.application.outbox import dispatch_outbox
from versionweaver.config import get_settings
from versionweaver.persistence.database import SessionLocal
from versionweaver.reliability import (
    CircuitBreaker,
    CircuitOpenError,
    RetryPolicy,
    call_with_retry,
)


def _project(client: TestClient, headers: dict[str, str], name: str = "patterns") -> str:
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": name, "source_uri": "/tmp/example", "default_branch": "main"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _change_payload(project_id: str, title: str = "Upgrade pydantic") -> dict[str, Any]:
    return {
        "project_id": project_id,
        "title": title,
        "requested_by": "developer@example.com",
        "spec": {
            "kind": "dependency",
            "dependency_name": "pydantic",
            "from_version": "2.9.0",
            "to_version": "2.10.0",
            "verification_commands": ["python -m compileall -q ."],
        },
    }


def test_idempotency_replays_same_result_and_rejects_key_reuse(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    project_id = _project(client, auth_headers)
    headers = {**auth_headers, "Idempotency-Key": "change-request-123"}

    first = client.post("/api/v1/changes", headers=headers, json=_change_payload(project_id))
    replay = client.post("/api/v1/changes", headers=headers, json=_change_payload(project_id))
    conflict = client.post(
        "/api/v1/changes",
        headers=headers,
        json=_change_payload(project_id, title="A different request"),
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert conflict.status_code == 409


def test_optimistic_version_and_cancellation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    project_id = _project(client, auth_headers)
    created = client.post(
        "/api/v1/changes", headers=auth_headers, json=_change_payload(project_id)
    ).json()

    stale = client.post(
        f"/api/v1/changes/{created['id']}/approve",
        headers=auth_headers,
        json={"actor": "approver", "expected_version": 99},
    )
    cancelled = client.post(
        f"/api/v1/changes/{created['id']}/cancel",
        headers=auth_headers,
        json={
            "actor": "developer",
            "reason": "Superseded by another migration",
            "expected_version": created["version"],
        },
    )

    assert stale.status_code == 409
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["version"] == created["version"] + 1


def test_cursor_pagination_metrics_and_outbox_dispatch(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    project_id = _project(client, auth_headers)
    client.post("/api/v1/changes", headers=auth_headers, json=_change_payload(project_id))
    client.post(
        "/api/v1/changes",
        headers=auth_headers,
        json=_change_payload(project_id, title="Upgrade another dependency"),
    )

    first_page = client.get("/api/v1/audit-events?limit=1", headers=auth_headers)
    cursor = first_page.headers.get("X-Next-Cursor")
    assert first_page.status_code == 200
    assert len(first_page.json()) == 1
    assert cursor
    second_page = client.get(
        "/api/v1/audit-events", headers=auth_headers, params={"limit": 1, "cursor": cursor}
    )
    assert second_page.status_code == 200
    assert first_page.json()[0]["id"] != second_page.json()[0]["id"]

    class RecordingPublisher:
        def __init__(self) -> None:
            self.events: list[str] = []

        def publish(self, event_type: str, payload: dict[str, object]) -> None:
            del payload
            self.events.append(event_type)

    publisher = RecordingPublisher()
    with SessionLocal() as session:
        published, failed = dispatch_outbox(session, publisher)
    assert published == 2
    assert failed == 0
    assert publisher.events == ["change.created", "change.created"]

    metrics = client.get("/metrics", headers=auth_headers)
    assert metrics.status_code == 200
    assert "versionweaver_http_requests_total" in metrics.text


def test_retry_and_circuit_breaker() -> None:
    attempts = 0
    delays: list[float] = []

    def unreliable() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary")
        return "ok"

    result = call_with_retry(
        unreliable,
        policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0.01, jitter_ratio=0),
        should_retry=lambda exc: isinstance(exc, ConnectionError),
        sleep=delays.append,
    )
    assert result == "ok"
    assert attempts == 3
    assert delays == [0.01, 0.02]

    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=60)
    breaker.record_failure()
    breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        breaker.before_call()


def test_runner_role_cannot_be_replaced_by_developer_token(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VERSIONWEAVER_RUNNER_API_TOKEN", "runner-token")
    monkeypatch.setenv("VERSIONWEAVER_ADMIN_API_TOKEN", "admin-token")
    get_settings.cache_clear()
    try:
        denied = client.get(
            "/api/v1/jobs/lease",
            headers=auth_headers,
            params={"runner_id": "wrong-role", "lease_seconds": 120},
        )
        allowed = client.get(
            "/api/v1/jobs/lease",
            headers={"Authorization": "Bearer runner-token"},
            params={"runner_id": "runner", "lease_seconds": 120},
        )
        assert denied.status_code == 403
        assert allowed.status_code == 204
    finally:
        get_settings.cache_clear()
