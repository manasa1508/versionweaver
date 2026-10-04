import time
from dataclasses import dataclass
from typing import Any

import httpx

from versionweaver.reliability import CircuitBreaker, RetryPolicy, call_with_retry


@dataclass(frozen=True)
class ModelResponse:
    content: str
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    raw_model: str | None


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        timeout_seconds: int = 120,
        retry_policy: RetryPolicy | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    @staticmethod
    def _transient(exc: Exception) -> bool:
        if isinstance(exc, httpx.TransportError):
            return True
        return isinstance(exc, httpx.HTTPStatusError) and (
            exc.response.status_code == 429 or exc.response.status_code >= 500
        )

    def complete(self, model: str, messages: list[dict[str, str]]) -> ModelResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        def request() -> httpx.Response:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json={"model": model, "messages": messages, "temperature": 0},
                )
                response.raise_for_status()
                return response

        started = time.monotonic()
        self.circuit_breaker.before_call()
        try:
            response = call_with_retry(
                request,
                policy=self.retry_policy,
                should_retry=self._transient,
            )
        except Exception:
            self.circuit_breaker.record_failure()
            raise
        self.circuit_breaker.record_success()
        latency_ms = int((time.monotonic() - started) * 1000)
        body: dict[str, Any] = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise ValueError("model response contains no choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("model response content is not text")
        usage = body.get("usage") or {}
        return ModelResponse(
            content=content,
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            raw_model=body.get("model"),
        )
