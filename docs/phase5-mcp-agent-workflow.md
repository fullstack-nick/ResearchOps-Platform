# Phase 5 MCP Agent Workflow

The Phase 5 MCP server exposes controlled ResearchOps tools at:

```text
http://localhost:8002/mcp
```

Development-mode MCP requests must include both the agent service token and the
delegated user identity:

```http
X-MCP-Agent-Token: local-dev-agent-token
X-Dev-User-Email: admin.frank@example.test
MCP-Protocol-Version: 2025-11-25
```

## Example: Why Is This Invoice Blocked?

An agent can answer an invoice-blocking question without direct database access:

1. `search_documents(query="Helix invoice blocked", workflow_type="procurement")`
2. `get_document_summary(document_id="...")`
3. `get_document_fields(document_id="...")`
4. `list_missing_fields(document_id="...")`
5. `get_workflow_status(workflow_id="...")`
6. `create_approval_request(workflow_id="...", reason="Invoice is missing required procurement fields.")`
7. Optionally `approve_request(...)` or `reject_request(...)` when the delegated user has permission.

Expected answer shape:

```text
This invoice is blocked because the latest extraction is missing the purchase
order number and the workflow is still waiting for intake review. The extracted
gross total, VAT, due date, and line items are available for Finance review, but
the missing PO number must be clarified before approval can proceed.
```

Every tool call records an `agent_actions` row. Side-effecting tools also write
regular `audit_events` with `actor_type='agent'`.
