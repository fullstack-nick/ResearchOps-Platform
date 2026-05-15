# ResearchOps Azure Agent Platform

An Azure-native AI operations platform for research institutes.

Phase 2 adds Azure-backed document extraction: upload a synthetic procurement invoice, store it in Azure Blob Storage, queue an extraction run, process it with Azure AI Document Intelligence `prebuilt-invoice`, and review extracted fields, confidence, missing fields, line items, corrections, workflow state, and audit events in a React + TypeScript dashboard.

Phase 3 adds document Q&A: every upload also queues an indexing run that calls Azure AI Document Intelligence `prebuilt-read`, chunks the document text with page references, generates embeddings with Azure OpenAI, and persists the chunks both in PostgreSQL and in an Azure AI Search index. Users can then ask questions in the document workspace; the platform runs a hybrid keyword + vector query against Azure AI Search, asks an Azure OpenAI chat model to answer using only the retrieved chunks, and shows the grounded answer with source citations in the dashboard's Q&A panel.

## Local Stack

- Frontend: React 19.2.6, TypeScript 6.0.3, Vite 8.0.13, TanStack Query 5.100.10
- Backend: Python 3.14.5 container, FastAPI 0.136.1, SQLAlchemy 2.0.49, Alembic 1.18.4
- Azure SDK: `azure-ai-documentintelligence==1.0.2`, `azure-storage-blob==12.28.0`, `azure-identity==1.25.3`, `azure-core==1.41.0`, `azure-search-documents==12.0.0`, `openai==2.36.0`
- Database: PostgreSQL 18.3
- Local orchestration: Docker Compose with `backend`, `worker`, `indexer`, `frontend`, and `postgres`

## Azure Configuration

Phase 2 runtime is Azure-only for new uploads. Configure these before uploading documents through the local app:

```powershell
$env:AZURE_STORAGE_CONTAINER="researchops-documents"
$env:AZURE_STORAGE_CONNECTION_STRING="<storage connection string>"
$env:AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://<resource-name>.cognitiveservices.azure.com/"
$env:AZURE_DOCUMENT_INTELLIGENCE_KEY="<document intelligence key>"
```

Alternatively, omit the two key/connection-string values and use `AZURE_STORAGE_ACCOUNT_URL` plus Azure Identity environment variables for `DefaultAzureCredential`.

Phase 3 additionally needs Azure AI Search and Azure OpenAI:

```powershell
$env:AZURE_SEARCH_ENDPOINT="https://<search-service>.search.windows.net"
$env:AZURE_SEARCH_API_KEY="<search admin key>"
$env:AZURE_SEARCH_INDEX_NAME="researchops-document-chunks"
$env:AZURE_OPENAI_ENDPOINT="https://<openai-resource>.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY="<openai key>"
$env:AZURE_OPENAI_API_VERSION="2024-10-21"
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-small"
$env:AZURE_OPENAI_EMBEDDING_DIMENSIONS="1536"
$env:AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4o-mini"
```

The `indexer` worker service polls `indexing_runs` and runs Document Intelligence `prebuilt-read`, chunking, embeddings, and Azure AI Search uploads; the `/api/documents/{id}/questions` endpoint then performs hybrid retrieval and chat-completion answering. Without these values the indexer fails the run and the Q&A endpoint returns `503`.

## Run

```powershell
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/healthz
- OpenAPI: http://localhost:8000/docs

Use `sample-documents/procurement/invoice_helix_lab_supplies.pdf` for the main Phase 2 demo upload. Procurement documents are extracted automatically; other workflow types remain upload/review only until later phases.

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

The Playwright test mocks Azure-facing API calls by default so it can run without live Azure credentials:

```powershell
cd frontend
npm run test:e2e
```

## Why Azure-managed services?

This project intentionally avoids rebuilding commodity infrastructure such as OCR, vector search, queues, identity, and generic monitoring. Later phases compose managed Azure services into the workflow platform while keeping custom engineering focused on orchestration, review, RBAC, auditability, MCP tools, and the React product UI.
