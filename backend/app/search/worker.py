from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import configure_observability, record_queue_backlog
from app.database.models import IndexingRun
from app.database.session import AsyncSessionLocal
from app.search.service import process_next_pending_indexing_run

logger = structlog.get_logger(__name__)


async def run_worker() -> None:
    configure_logging()
    settings = get_settings()
    configure_observability(settings, "researchops-indexer")
    logger.info("indexing.worker.started")
    while True:
        async with AsyncSessionLocal() as session:
            await record_queue_backlog(session, "indexing", IndexingRun)
            processed = await process_next_pending_indexing_run(session)
        if not processed:
            await asyncio.sleep(settings.indexing_worker_poll_seconds)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
