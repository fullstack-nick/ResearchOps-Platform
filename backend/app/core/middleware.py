import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.observability import record_counter, record_histogram

logger = structlog.get_logger(__name__)


async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    clear_contextvars()
    bind_contextvars(correlation_id=correlation_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _record_request_metrics(request, 500, duration_ms)
        logger.exception("request.failed", method=request.method, path=request.url.path)
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Correlation-ID"] = correlation_id
    _record_request_metrics(request, response.status_code, duration_ms)
    logger.info(
        "request.completed",
        method=request.method,
        path=_route_path(request),
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


def _record_request_metrics(request: Request, status_code: int, duration_ms: float) -> None:
    attributes = {
        "http.method": request.method,
        "http.route": _route_path(request),
        "http.status_code": status_code,
        "http.status_class": f"{status_code // 100}xx",
    }
    record_counter("researchops.http.server.requests", 1, attributes)
    record_histogram("researchops.http.server.duration_ms", duration_ms, attributes)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path or request.url.path)
