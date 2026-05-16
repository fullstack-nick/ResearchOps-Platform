# Phase 7 Observability

Phase 7 adds production telemetry and Azure Managed Grafana dashboards around the live Azure deployment.

## Runtime Telemetry

The Python services initialize Azure Monitor OpenTelemetry only when both values are present:

```text
OBSERVABILITY_ENABLED=true
APPLICATIONINSIGHTS_CONNECTION_STRING=<connection string>
```

Each Container App sets a distinct service name:

```text
researchops-backend
researchops-worker
researchops-indexer
researchops-mcp
```

The application keeps JSON stdout logging and correlation IDs. OpenTelemetry metrics and events are emitted for:

- HTTP request rate, latency, status class, and exceptions.
- Azure Blob, Document Intelligence, Azure AI Search, Azure OpenAI, and PostgreSQL-backed worker dependencies.
- Document uploads, extraction runs, indexing runs, Q&A, field corrections, workflow approvals, and MCP tool calls.
- PostgreSQL-backed extraction and indexing queue backlog.

Service Bus backlog is intentionally out of scope until the pipeline moves from PostgreSQL polling to Service Bus.

## Dashboards

Repo-managed dashboards live in `grafana/dashboards/`:

```text
researchops-system-health.json
researchops-document-pipeline.json
researchops-agent-tools.json
```

They query the existing Log Analytics workspace through the Azure Monitor data source in Azure Managed Grafana.

## Import

Use the import helper after Terraform has provisioned Grafana:

```powershell
python scripts/import_grafana_dashboards.py `
  --resource-group researchops-vt1zhh-rg `
  --grafana-name researchops-vt1zhh-gfn `
  --workspace-resource-id /subscriptions/d87e9e4d-034d-40ad-a622-e71bac89da94/resourceGroups/researchops-vt1zhh-rg/providers/Microsoft.OperationalInsights/workspaces/researchops-vt1zhh-law
```

The GitHub deployment workflow installs the Azure Managed Grafana CLI extension and runs this import automatically after the app smoke test. The workflow is intentionally manual-only now: run `deploy`, choose **Run workflow**, and type `deploy` in the confirmation input before it will build images, update Container Apps, or import dashboards.

## Live Verification

Useful KQL checks:

```kusto
AppMetrics
| where TimeGenerated > ago(45m)
| where Name startswith "researchops."
| summarize Count=count(), Last=max(TimeGenerated) by Name
| order by Count desc
```

```kusto
AppMetrics
| where TimeGenerated > ago(45m) and Name == "researchops.events"
| extend Properties=parse_json(Properties), event_name=tostring(Properties["event.name"])
| summarize Count=sum(todouble(Sum)), Last=max(TimeGenerated) by event_name
| order by Count desc
```

```kusto
AppMetrics
| where TimeGenerated > ago(45m) and Name in ("researchops.agent.tool_calls", "researchops.agent.tool_duration_ms")
| extend Properties=parse_json(Properties), tool=tostring(Properties["mcp.tool"]), status=tostring(Properties["mcp.status"])
| summarize Count=count(), Last=max(TimeGenerated) by Name, tool, status
```
