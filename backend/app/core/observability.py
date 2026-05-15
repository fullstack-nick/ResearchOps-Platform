from __future__ import annotations

import logging
import os
import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import import_module
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings

logger = structlog.get_logger(__name__)

AttributeValue = str | bool | int | float
Attributes = Mapping[str, object | None]

_configured = False
_enabled = False
_instrument_cache: dict[tuple[str, str], Any] = {}


def configure_observability(settings: Settings, default_service_name: str) -> bool:
    global _configured, _enabled
    if _configured:
        return _enabled

    service_name = settings.otel_service_name or default_service_name
    if not settings.observability_enabled:
        _configured = True
        logger.info("observability.disabled", reason="OBSERVABILITY_ENABLED is false")
        return False
    if not settings.applicationinsights_connection_string:
        _configured = True
        logger.info(
            "observability.disabled",
            reason="APPLICATIONINSIGHTS_CONNECTION_STRING is not configured",
        )
        return False

    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
        logging.WARNING,
    )
    logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(
        logging.WARNING,
    )

    os.environ.setdefault(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        settings.applicationinsights_connection_string,
    )
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    os.environ.setdefault("OTEL_TRACES_SAMPLER", "traceidratio")
    os.environ.setdefault("OTEL_TRACES_SAMPLER_ARG", str(settings.observability_sample_rate))
    if settings.otel_resource_attributes:
        os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", settings.otel_resource_attributes)

    try:
        module = import_module("azure.monitor.opentelemetry")
        configure = module.configure_azure_monitor

        configure(
            connection_string=settings.applicationinsights_connection_string,
        )
    except Exception as exc:
        _configured = True
        _enabled = False
        logger.warning("observability.configure_failed", error=str(exc))
        return False

    _configured = True
    _enabled = True
    logger.info("observability.enabled", service_name=service_name)
    return True


def is_observability_enabled() -> bool:
    return _enabled


def record_counter(name: str, value: int = 1, attributes: Attributes | None = None) -> None:
    try:
        counter = _instrument("counter", name)
        counter.add(value, attributes=_clean_attributes(attributes))
    except Exception as exc:
        logger.debug("observability.counter_failed", metric=name, error=str(exc))


def record_histogram(name: str, value: int | float, attributes: Attributes | None = None) -> None:
    try:
        histogram = _instrument("histogram", name)
        histogram.record(value, attributes=_clean_attributes(attributes))
    except Exception as exc:
        logger.debug("observability.histogram_failed", metric=name, error=str(exc))


def record_event(name: str, attributes: Attributes | None = None) -> None:
    cleaned = _clean_attributes(attributes)
    record_counter("researchops.events", 1, {"event.name": name, **cleaned})
    logging.getLogger("researchops.telemetry").info(
        name,
        extra={"custom_dimensions": {"event.name": name, **cleaned}},
    )
    try:
        from opentelemetry import trace

        trace.get_current_span().add_event(name, cleaned)
    except Exception as exc:
        logger.debug("observability.event_failed", event=name, error=str(exc))


@contextmanager
def observe_span(name: str, attributes: Attributes | None = None) -> Generator[None]:
    cleaned = _clean_attributes(attributes)
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("researchops")
        with tracer.start_as_current_span(name) as span:
            for key, value in cleaned.items():
                span.set_attribute(key, value)
            yield
    except Exception:
        yield


@contextmanager
def observe_dependency(name: str, attributes: Attributes | None = None) -> Generator[None]:
    cleaned = _clean_attributes(attributes)
    started = time.perf_counter()
    status_value = "completed"
    try:
        with observe_span(name, cleaned):
            yield
    except Exception:
        status_value = "failed"
        raise
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        metric_attributes = {"dependency.name": name, "status": status_value, **cleaned}
        record_counter("researchops.dependencies.calls", 1, metric_attributes)
        record_histogram(
            "researchops.dependencies.duration_ms",
            duration_ms,
            metric_attributes,
        )


async def record_queue_backlog(
    session: AsyncSession,
    queue_name: str,
    model: Any,
) -> None:
    result = await session.execute(
        select(model.status, func.count(model.id)).group_by(model.status)
    )
    seen_pending = False
    for status_value, count in result.all():
        if status_value == "pending":
            seen_pending = True
        record_histogram(
            "researchops.queue.backlog",
            int(count),
            {"queue.name": queue_name, "queue.status": str(status_value)},
        )
    if not seen_pending:
        record_histogram(
            "researchops.queue.backlog",
            0,
            {"queue.name": queue_name, "queue.status": "pending"},
        )

    oldest_pending = await session.scalar(
        select(func.min(model.created_at)).where(model.status == "pending")
    )
    age_seconds = 0.0
    if oldest_pending is not None:
        age_seconds = max(
            0.0,
            (datetime.now(UTC) - oldest_pending).total_seconds(),
        )
    record_histogram(
        "researchops.queue.oldest_pending_age_seconds",
        age_seconds,
        {"queue.name": queue_name},
    )


def reset_observability_for_tests() -> None:
    global _configured, _enabled
    _configured = False
    _enabled = False
    _instrument_cache.clear()


def _instrument(kind: str, name: str) -> Any:
    key = (kind, name)
    existing = _instrument_cache.get(key)
    if existing is not None:
        return existing

    from opentelemetry import metrics

    meter = metrics.get_meter("researchops")
    if kind == "counter":
        instrument = meter.create_counter(name)
    elif kind == "histogram":
        instrument = meter.create_histogram(name)
    else:
        raise ValueError(f"Unsupported metric instrument kind: {kind}")
    _instrument_cache[key] = instrument
    return instrument


def _clean_attributes(attributes: Attributes | None) -> dict[str, AttributeValue]:
    clean: dict[str, AttributeValue] = {}
    for key, value in (attributes or {}).items():
        if value is None:
            continue
        if isinstance(value, bool | int | float | str):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean
