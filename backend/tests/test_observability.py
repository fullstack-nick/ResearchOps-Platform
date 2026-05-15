from __future__ import annotations

from typing import Any

from httpx import AsyncClient


def test_observability_disabled_without_flag() -> None:
    from app.core.config import Settings
    from app.core.observability import configure_observability, reset_observability_for_tests

    reset_observability_for_tests()
    settings = Settings(observability_enabled=False)

    assert configure_observability(settings, "researchops-test") is False

    reset_observability_for_tests()


def test_observability_enabled_requires_connection_string() -> None:
    from app.core.config import Settings
    from app.core.observability import configure_observability, reset_observability_for_tests

    reset_observability_for_tests()
    settings = Settings(
        observability_enabled=True,
        applicationinsights_connection_string=None,
    )

    assert configure_observability(settings, "researchops-test") is False

    reset_observability_for_tests()


def test_record_event_sanitizes_attributes(monkeypatch: Any) -> None:
    from app.core import observability

    captured: list[dict[str, object]] = []

    def fake_counter(
        name: str, value: int = 1, attributes: observability.Attributes | None = None
    ) -> None:
        captured.append(dict(attributes or {}))

    monkeypatch.setattr(observability, "record_counter", fake_counter)

    observability.record_event(
        "document.uploaded",
        {"document.id": object(), "none.value": None, "count": 3},
    )

    assert captured == [
        {
            "event.name": "document.uploaded",
            "document.id": captured[0]["document.id"],
            "count": 3,
        }
    ]
    assert isinstance(captured[0]["document.id"], str)


async def test_queue_backlog_metrics(
    client: AsyncClient, pdf_bytes: bytes, monkeypatch: Any
) -> None:
    from app.core import observability
    from app.database.models import ExtractionRun, IndexingRun
    from app.database.session import AsyncSessionLocal

    response = await client.post(
        "/api/documents?workflow_type=procurement",
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201, response.text

    captured: list[tuple[str, int | float, dict[str, object]]] = []

    def fake_histogram(
        name: str,
        value: int | float,
        attributes: observability.Attributes | None = None,
    ) -> None:
        captured.append((name, value, dict(attributes or {})))

    monkeypatch.setattr(observability, "record_histogram", fake_histogram)

    async with AsyncSessionLocal() as session:
        await observability.record_queue_backlog(session, "extraction", ExtractionRun)
        await observability.record_queue_backlog(session, "indexing", IndexingRun)

    assert (
        "researchops.queue.backlog",
        1,
        {"queue.name": "extraction", "queue.status": "pending"},
    ) in captured
    assert (
        "researchops.queue.backlog",
        1,
        {"queue.name": "indexing", "queue.status": "pending"},
    ) in captured
    assert any(name == "researchops.queue.oldest_pending_age_seconds" for name, _, _ in captured)
