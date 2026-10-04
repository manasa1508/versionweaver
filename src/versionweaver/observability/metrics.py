from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

HTTP_REQUESTS = Counter(
    "versionweaver_http_requests_total",
    "HTTP requests processed by the control plane",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "versionweaver_http_request_duration_seconds",
    "HTTP request duration",
    ("method", "route"),
)


def record_request(method: str, route: str, status: int, duration_seconds: float) -> None:
    HTTP_REQUESTS.labels(method=method, route=route, status=str(status)).inc()
    HTTP_DURATION.labels(method=method, route=route).observe(duration_seconds)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
