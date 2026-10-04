from pathlib import Path

from fastapi.testclient import TestClient


def test_full_control_plane_flow(client: TestClient, auth_headers: dict[str, str]) -> None:
    source = str(Path(__file__).parents[1] / "examples" / "python-ai-app")
    project_response = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "api-flow", "source_uri": source, "default_branch": "main"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    change_response = client.post(
        "/api/v1/changes",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "title": "Upgrade pydantic",
            "requested_by": "developer@example.com",
            "spec": {
                "kind": "dependency",
                "dependency_name": "pydantic",
                "from_version": "2.9.0",
                "to_version": "2.10.0",
                "verification_commands": ["python -m compileall -q ."],
            },
        },
    )
    assert change_response.status_code == 201
    assert change_response.json()["status"] == "planned"
    change_id = change_response.json()["id"]

    approve_response = client.post(
        f"/api/v1/changes/{change_id}/approve",
        headers=auth_headers,
        json={"actor": "approver@example.com"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "queued"

    lease_response = client.get(
        "/api/v1/jobs/lease",
        headers=auth_headers,
        params={"runner_id": "test-runner", "lease_seconds": 120},
    )
    assert lease_response.status_code == 200
    lease = lease_response.json()

    heartbeat_response = client.post(
        f"/api/v1/jobs/{lease['job_id']}/heartbeat",
        headers=auth_headers,
        json={
            "runner_id": "test-runner",
            "lease_token": lease["lease_token"],
            "extend_seconds": 120,
        },
    )
    assert heartbeat_response.status_code == 200

    evidence_document = {
        "schema_version": "1.0",
        "change_id": change_id,
        "job_id": lease["job_id"],
        "outcome": "succeeded",
        "completed_at": "2026-09-26T00:00:00+00:00",
    }
    complete_response = client.post(
        f"/api/v1/jobs/{lease['job_id']}/complete",
        headers=auth_headers,
        json={
            "runner_id": "test-runner",
            "lease_token": lease["lease_token"],
            "outcome": "succeeded",
            "evidence": evidence_document,
        },
    )
    assert complete_response.status_code == 200
    assert len(complete_response.json()["sha256"]) == 64

    final_change = client.get(f"/api/v1/changes/{change_id}", headers=auth_headers)
    assert final_change.json()["status"] == "succeeded"

    duplicate = client.post(
        f"/api/v1/jobs/{lease['job_id']}/complete",
        headers=auth_headers,
        json={
            "runner_id": "test-runner",
            "lease_token": lease["lease_token"],
            "outcome": "succeeded",
            "evidence": evidence_document,
        },
    )
    assert duplicate.status_code == 409


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_console_read_models_are_paginated_and_aggregated(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    source = str(Path(__file__).parents[1] / "examples" / "python-ai-app")
    project_ids: list[str] = []
    for index in range(2):
        response = client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={
                "name": f"console-project-{index}",
                "source_uri": source,
                "default_branch": "main",
            },
        )
        assert response.status_code == 201
        project_ids.append(response.json()["id"])

    first_page = client.get("/api/v1/projects?limit=1", headers=auth_headers)
    assert first_page.status_code == 200
    assert len(first_page.json()) == 1
    cursor = first_page.headers["X-Next-Cursor"]
    second_page = client.get(
        "/api/v1/projects", headers=auth_headers, params={"limit": 1, "cursor": cursor}
    )
    assert second_page.status_code == 200
    assert len(second_page.json()) == 1
    assert second_page.json()[0]["id"] != first_page.json()[0]["id"]

    change_response = client.post(
        "/api/v1/changes",
        headers=auth_headers,
        json={
            "project_id": project_ids[0],
            "title": "Upgrade console dependency",
            "requested_by": "console-user",
            "spec": {
                "kind": "dependency",
                "dependency_name": "pydantic",
                "to_version": "2.10.0",
            },
        },
    )
    assert change_response.status_code == 201
    change = change_response.json()

    summary = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["project_count"] == 2
    assert summary.json()["change_count"] == 1
    assert summary.json()["changes_by_status"] == {"planned": 1}

    approval = client.post(
        f"/api/v1/changes/{change['id']}/approve",
        headers=auth_headers,
        json={"actor": "console-approver", "expected_version": change["version"]},
    )
    assert approval.status_code == 200

    jobs = client.get("/api/v1/jobs?status=queued", headers=auth_headers)
    assert jobs.status_code == 200
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["change_id"] == change["id"]
    assert "lease_token" not in jobs.json()[0]

    filtered = client.get(
        "/api/v1/changes",
        headers=auth_headers,
        params={"kind": "dependency", "search": "console"},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [change["id"]]

    invalid_cursor = client.get(
        "/api/v1/jobs", headers=auth_headers, params={"cursor": "not-a-cursor"}
    )
    assert invalid_cursor.status_code == 400
