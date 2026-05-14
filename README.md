# ResearchOps Azure Agent Platform

An Azure-native AI operations platform for research institutes.

Phase 1 is a local foundation: upload a synthetic PDF, store it, create workflow and audit records in PostgreSQL, and review it in a React + TypeScript dashboard.

## Local Stack

- Frontend: React 19.2.6, TypeScript 6.0.3, Vite 8.0.13, TanStack Query 5.100.10
- Backend: Python 3.14.5 container, FastAPI 0.136.1, SQLAlchemy 2.0.49, Alembic 1.18.4
- Database: PostgreSQL 18.3
- Local orchestration: Docker Compose

## Run

```powershell
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/healthz
- OpenAPI: http://localhost:8000/docs

Use `sample-documents/procurement/invoice_helix_lab_supplies.pdf` for the main Phase 1 demo upload.

## Backend Checks

```powershell
cd backend
uv sync
uv run ruff check
uv run pyright
uv run pytest
```

## Frontend Checks

```powershell
cd frontend
npm install
npm run typecheck
npm run lint
npm run test
```

## E2E Check

Start the stack first, then:

```powershell
cd frontend
npm run test:e2e
```

## Why Azure-managed services?

This project intentionally avoids rebuilding commodity infrastructure such as OCR, vector search, queues, identity, and generic monitoring. Later phases compose managed Azure services into the workflow platform while keeping custom engineering focused on orchestration, review, RBAC, auditability, MCP tools, and the React product UI.
