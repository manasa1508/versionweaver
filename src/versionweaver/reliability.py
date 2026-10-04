import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


class CircuitOpenError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0
    multiplier: float = 2.0
    jitter_ratio: float = 0.2


class CircuitBreaker:
    """Small thread-safe closed/open/half-open circuit breaker."""

    def __init__(self, failure_threshold: int = 5, recovery_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open_in_flight = False
        self._lock = threading.Lock()

    def before_call(self) -> None:
        with self._lock:
            if self._opened_at is None:
                return
            if time.monotonic() - self._opened_at < self.recovery_seconds:
                raise CircuitOpenError("dependency circuit is open")
            if self._half_open_in_flight:
                raise CircuitOpenError("dependency circuit is half-open")
            self._half_open_in_flight = True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._half_open_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._half_open_in_flight = False
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()


def call_with_retry[T](
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    should_retry: Callable[[Exception], bool],
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry transient failures with bounded exponential backoff and full operation limits."""
    delay = policy.initial_delay_seconds
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt == policy.max_attempts or not should_retry(exc):
                raise
            jitter = delay * policy.jitter_ratio * random.random()
            sleep(min(policy.max_delay_seconds, delay + jitter))
            delay = min(policy.max_delay_seconds, delay * policy.multiplier)
    raise AssertionError("retry loop exhausted unexpectedly")
