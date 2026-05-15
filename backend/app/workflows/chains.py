from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowStepSpec:
    step_name: str
    assigned_role: str


# Ordered approval chains per workflow type. The first step always represents
# operations intake. Subsequent steps fan out into the right-of-access roles
# (group lead for procurement/grants, finance for procurement, HR/IT for
# onboarding) so review queues mirror the project plan in section 8.3.
WORKFLOW_CHAINS: dict[str, tuple[WorkflowStepSpec, ...]] = {
    "procurement": (
        WorkflowStepSpec("intake_review", "operations_admin"),
        WorkflowStepSpec("group_lead_approval", "group_lead"),
        WorkflowStepSpec("finance_approval", "finance"),
    ),
    "hr_onboarding": (
        WorkflowStepSpec("intake_review", "operations_admin"),
        WorkflowStepSpec("hr_review", "hr"),
        WorkflowStepSpec("it_provisioning", "it"),
    ),
    "grants": (
        WorkflowStepSpec("intake_review", "operations_admin"),
        WorkflowStepSpec("group_lead_approval", "group_lead"),
    ),
    "contracts": (
        WorkflowStepSpec("intake_review", "operations_admin"),
        WorkflowStepSpec("legal_review", "operations_admin"),
    ),
    "reports": (WorkflowStepSpec("intake_review", "operations_admin"),),
}


def chain_for(workflow_type: str) -> tuple[WorkflowStepSpec, ...]:
    return WORKFLOW_CHAINS.get(workflow_type, ())
