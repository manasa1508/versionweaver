from typing import Any, cast

import httpx

from versionweaver.schemas import JobCompletion, JobPayload


class VersionWeaverClient:
    def __init__(self, base_url: str, api_token: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _object(response: httpx.Response) -> dict[str, Any]:
        return cast(dict[str, Any], response.json())

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._object(self._request("POST", "/api/v1/projects", json=payload))

    def upload_inventory(self, project_id: str, inventory: dict[str, Any]) -> dict[str, Any]:
        return self._object(
            self._request(
                "PUT", f"/api/v1/projects/{project_id}/inventory", json={"inventory": inventory}
            )
        )

    def create_change(
        self, payload: dict[str, Any], idempotency_key: str | None = None
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        return self._object(self._request("POST", "/api/v1/changes", json=payload, headers=headers))

    def approve_change(
        self, change_id: str, actor: str, expected_version: int | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"actor": actor}
        if expected_version is not None:
            payload["expected_version"] = expected_version
        return self._object(
            self._request("POST", f"/api/v1/changes/{change_id}/approve", json=payload)
        )

    def cancel_change(
        self,
        change_id: str,
        actor: str,
        reason: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"actor": actor, "reason": reason}
        if expected_version is not None:
            payload["expected_version"] = expected_version
        return self._object(
            self._request("POST", f"/api/v1/changes/{change_id}/cancel", json=payload)
        )

    def get_change(self, change_id: str) -> dict[str, Any]:
        return self._object(self._request("GET", f"/api/v1/changes/{change_id}"))

    def lease_job(self, runner_id: str, lease_seconds: int) -> JobPayload | None:
        response = self._request(
            "GET",
            "/api/v1/jobs/lease",
            params={"runner_id": runner_id, "lease_seconds": lease_seconds},
        )
        if response.status_code == 204 or not response.content:
            return None
        return JobPayload.model_validate(response.json())

    def heartbeat(self, job_id: str, runner_id: str, lease_token: str, extend_seconds: int) -> None:
        self._request(
            "POST",
            f"/api/v1/jobs/{job_id}/heartbeat",
            json={
                "runner_id": runner_id,
                "lease_token": lease_token,
                "extend_seconds": extend_seconds,
            },
        )

    def complete_job(self, job_id: str, completion: JobCompletion) -> dict[str, Any]:
        return self._object(
            self._request(
                "POST",
                f"/api/v1/jobs/{job_id}/complete",
                json=completion.model_dump(mode="json"),
            )
        )
