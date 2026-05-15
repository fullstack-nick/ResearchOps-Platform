from __future__ import annotations

from typing import Any

from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.agents.mcp.auth import McpAuthMiddleware
from app.agents.mcp.server import create_mcp_server
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import engine


async def healthz(request: object) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def readyz(request: object) -> JSONResponse:
    async with engine.connect() as connection:
        await connection.execute(text("select 1"))
    return JSONResponse({"status": "ready"})


def create_app() -> Any:
    configure_logging()
    settings = get_settings()
    mcp = create_mcp_server()
    app = mcp.streamable_http_app()
    app.routes.append(Route("/healthz", healthz, methods=["GET"]))
    app.routes.append(Route("/readyz", readyz, methods=["GET"]))
    app.add_middleware(McpAuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.mcp_allowed_origin_values),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "authorization",
            "content-type",
            "mcp-protocol-version",
            "x-correlation-id",
            "x-dev-user-email",
            "x-mcp-agent-token",
        ],
    )
    return app


app = create_app()
