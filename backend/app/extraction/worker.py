from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import configure_observability, record_queue_backlog
from app.database.models import ExtractionRun
from app.database.session import AsyncSessionLocal
from app.extraction.service import process_next_pending_run

logger = structlog.get_logger(__name__)


async def run_worker() -> None:
    configure_logging()
    settings = get_settings()
    configure_observability(settings, "researchops-worker")
    logger.info("extraction.worker.started")
    while True:
        async with AsyncSessionLocal() as session:
            await record_queue_backlog(session, "extraction", ExtractionRun)
            processed = await process_next_pending_run(session)
        if not processed:
            await asyncio.sleep(settings.extraction_worker_poll_seconds)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
