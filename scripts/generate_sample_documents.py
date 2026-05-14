from __future__ import annotations

import json
from pathlib import Path
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]


DOCUMENTS = [
    {
        "path": "sample-documents/procurement/invoice_helix_lab_supplies.pdf",
        "title": "Invoice - Helix Lab Supplies GmbH",
        "subtitle": "Synthetic procurement document",
        "sections": [
            ("Vendor", ["Helix Lab Supplies GmbH", "Fictional Strasse 42, 10115 Berlin, Germany", "VAT ID: DE123456789"]),
            ("Invoice", ["Invoice number: HLS-2026-0142", "Issue date: 2026-05-01", "Due date: 2026-05-15", "Payment terms: Net 14"]),
            ("Internal routing", ["Requester: Dr. Mira Novak", "Research group: Neurodata Operations", "Project code: BIO-OPS-2026-014", "Cost center: CC-4812"]),
        ],
        "table": [
            ["Line item", "Qty", "Unit price", "Net"],
            ["Sequencing reagent kit", "4", "EUR 680.00", "EUR 2,720.00"],
            ["Cryobox storage set", "12", "EUR 45.00", "EUR 540.00"],
            ["Cold-chain delivery", "1", "EUR 110.00", "EUR 110.00"],
            ["Net total", "", "", "EUR 3,370.00"],
            ["VAT 19 percent", "", "", "EUR 640.30"],
            ["Gross total", "", "", "EUR 4,010.30"],
        ],
    },
    {
        "path": "sample-documents/procurement/quote_microscope_maintenance.pdf",
        "title": "Quote - Microscope Maintenance",
        "subtitle": "Synthetic procurement quote",
        "sections": [
            ("Supplier", ["OpticCare Instruments GmbH", "Quote number: OCI-Q-2026-0088"]),
            ("Scope", ["Annual preventive maintenance for two confocal microscope systems.", "Valid until: 2026-06-30"]),
            ("Commercials", ["Net amount: EUR 3,260.00", "VAT: EUR 619.40", "Gross total: EUR 3,879.40"]),
        ],
    },
    {
        "path": "sample-documents/procurement/purchase_order_001.pdf",
        "title": "Purchase Order PO-2026-001",
        "subtitle": "Synthetic internal purchase order",
        "sections": [
            ("Purchase order", ["PO number: PO-2026-001", "Requester: Dr. Mira Novak", "Approved amount: EUR 3,879.40"]),
            ("Approver", ["Group lead: Prof. Anton Keller", "Approval date: 2026-04-28"]),
        ],
    },
    {
        "path": "sample-documents/procurement/delivery_note_001.pdf",
        "title": "Delivery Note DN-2026-001",
        "subtitle": "Synthetic delivery confirmation",
        "sections": [
            ("Delivery", ["Supplier: Helix Lab Supplies GmbH", "Delivery date: 2026-05-04", "Received by: Lab Admin Team"]),
            ("Items", ["Sequencing reagent kit: 4 units", "Cryobox storage set: 12 units"]),
        ],
    },
    {
        "path": "sample-documents/hr/onboarding_form_research_assistant.pdf",
        "title": "Onboarding Form - Research Assistant",
        "subtitle": "Synthetic HR onboarding document",
        "sections": [
            ("Person", ["Name: Alex Weber", "Email: alex.weber@example.test", "Role: Research Assistant"]),
            ("Start details", ["Research group: Neurodata Operations", "Supervisor: Dr. Mira Novak", "Start date: 2026-06-01"]),
            ("Required access", ["IT account: standard researcher", "Software: Python, RStudio, Git client", "Hardware: laptop, docking station"]),
        ],
    },
    {
        "path": "sample-documents/hr/synthetic_cv_data_scientist.pdf",
        "title": "Synthetic CV - Data Scientist",
        "subtitle": "Synthetic HR review document",
        "sections": [
            ("Candidate", ["Name: Sam Rivera", "Email: sam.rivera@example.test"]),
            ("Experience", ["Data analysis for imaging workflows", "Python, SQL, statistics, reproducible reporting"]),
            ("Education", ["MSc Computational Biology, Fictional University"]),
        ],
    },
    {
        "path": "sample-documents/hr/it_account_request.pdf",
        "title": "IT Account Request",
        "subtitle": "Synthetic IT onboarding form",
        "sections": [
            ("Requester", ["Name: Alex Weber", "Start date: 2026-06-01"]),
            ("Accounts", ["Email mailbox", "Git repository access", "Shared drive: Neurodata Operations"]),
            ("Approvals", ["Supervisor approval: pending", "IT security training: required"]),
        ],
    },
    {
        "path": "sample-documents/grants/grant_award_letter_neurodata_2026.pdf",
        "title": "Grant Award Letter - Neurodata 2026",
        "subtitle": "Synthetic grant administration document",
        "sections": [
            ("Grant", ["Grant title: Neurodata Infrastructure 2026", "Grant ID: ND-2026-771", "Funder: European Research Demo Fund"]),
            ("Project", ["Principal investigator: Prof. Anton Keller", "Start date: 2026-07-01", "End date: 2028-06-30"]),
            ("Budget", ["Total budget: EUR 480,000", "Personnel: EUR 260,000", "Equipment: EUR 120,000", "Travel: EUR 35,000"]),
            ("Reporting", ["First report due: 2027-01-31", "Deliverables due this quarter: data management plan"]),
        ],
    },
    {
        "path": "sample-documents/grants/funder_reporting_instructions.pdf",
        "title": "Funder Reporting Instructions",
        "subtitle": "Synthetic grant guidance",
        "sections": [
            ("Reporting cadence", ["Financial report every six months", "Scientific progress report every twelve months"]),
            ("Acknowledgement", ["All outputs must mention European Research Demo Fund grant ND-2026-771."]),
        ],
    },
    {
        "path": "sample-documents/grants/budget_table.pdf",
        "title": "Budget Table - Neurodata Infrastructure",
        "subtitle": "Synthetic budget document",
        "sections": [
            ("Eligible costs", ["Personnel, equipment, travel, consumables"]),
            ("Ineligible costs", ["Entertainment, late payment fees, unsupported subscriptions"]),
        ],
    },
    {
        "path": "sample-documents/contracts/software_subscription_agreement.pdf",
        "title": "Software Subscription Agreement",
        "subtitle": "Synthetic contract document",
        "sections": [
            ("Parties", ["ResearchOps Institute", "CloudLab Tools Ltd."]),
            ("Term", ["Effective date: 2026-05-01", "Expiry date: 2027-04-30", "Auto-renewal: yes, annual"]),
            ("Notice", ["Termination notice period: 60 days before renewal", "Governing law: Germany"]),
        ],
    },
    {
        "path": "sample-documents/contracts/equipment_service_contract.pdf",
        "title": "Equipment Service Contract",
        "subtitle": "Synthetic service agreement",
        "sections": [
            ("Service", ["Annual maintenance for freezer monitoring equipment", "SLA response time: two business days"]),
            ("Term", ["Effective date: 2026-03-01", "Expiry date: 2027-02-28", "Renewal reminder: 2026-12-30"]),
        ],
    },
    {
        "path": "sample-documents/reports/monthly_operations_report.pdf",
        "title": "Monthly Operations Report",
        "subtitle": "Synthetic internal report",
        "sections": [
            ("Decisions", ["Continue procurement intake pilot for Neurodata Operations."]),
            ("Risks", ["Two supplier invoices are missing purchase order numbers."]),
            ("Actions", ["Finance to review flagged invoices by 2026-05-20", "IT to prepare laptop image for new hire."]),
        ],
    },
    {
        "path": "sample-documents/reports/meeting_minutes_lab_admin.pdf",
        "title": "Meeting Minutes - Lab Administration",
        "subtitle": "Synthetic meeting notes",
        "sections": [
            ("Attendees", ["Mira Novak", "Jonas Feld", "Elena Fischer"]),
            ("Decisions", ["Use shared intake queue for supplier invoices.", "Create checklist for onboarding hardware requests."]),
            ("Action items", ["Jonas to confirm delivery notes by 2026-05-18", "Elena to update training checklist by 2026-05-22"]),
        ],
    },
]

EXPECTED_RESULTS = {
    "invoice_helix_lab_supplies.json": {
        "document_type": "invoice",
        "vendor_name": "Helix Lab Supplies GmbH",
        "invoice_number": "HLS-2026-0142",
        "issue_date": "2026-05-01",
        "due_date": "2026-05-15",
        "currency": "EUR",
        "net_amount": 3370.00,
        "vat_amount": 640.30,
        "gross_total": 4010.30,
        "project_code": "BIO-OPS-2026-014",
        "missing_fields": ["purchase_order_number"],
    },
    "onboarding_form_research_assistant.json": {
        "document_type": "hr_onboarding",
        "person_name": "Alex Weber",
        "email": "alex.weber@example.test",
        "role": "Research Assistant",
        "research_group": "Neurodata Operations",
        "supervisor": "Dr. Mira Novak",
        "start_date": "2026-06-01",
        "required_it_accounts": ["standard researcher"],
        "required_hardware": ["laptop", "docking station"],
    },
    "grant_award_letter_neurodata_2026.json": {
        "document_type": "grant_award_letter",
        "grant_title": "Neurodata Infrastructure 2026",
        "grant_id": "ND-2026-771",
        "funder": "European Research Demo Fund",
        "principal_investigator": "Prof. Anton Keller",
        "start_date": "2026-07-01",
        "end_date": "2028-06-30",
        "total_budget": 480000,
        "next_report_due": "2027-01-31",
    },
    "software_subscription_agreement.json": {
        "document_type": "software_subscription_agreement",
        "parties": ["ResearchOps Institute", "CloudLab Tools Ltd."],
        "effective_date": "2026-05-01",
        "expiry_date": "2027-04-30",
        "auto_renewal": True,
        "termination_notice_days": 60,
    },
    "meeting_minutes_lab_admin.json": {
        "document_type": "meeting_minutes",
        "decisions": [
            "Use shared intake queue for supplier invoices.",
            "Create checklist for onboarding hardware requests.",
        ],
        "action_items": [
            {"owner": "Jonas", "task": "Confirm delivery notes", "deadline": "2026-05-18"},
            {"owner": "Elena", "task": "Update training checklist", "deadline": "2026-05-22"},
        ],
    },
}


def build_pdf(document: dict[str, object]) -> None:
    output = ROOT / str(document["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(str(document["title"]), styles["Title"]),
        Paragraph(str(document["subtitle"]), styles["Normal"]),
        Spacer(1, 8 * mm),
    ]

    for heading, lines in document["sections"]:  # type: ignore[index]
        story.append(Paragraph(str(heading), styles["Heading2"]))
        for line in lines:
            wrapped = "<br/>".join(wrap(str(line), width=95))
            story.append(Paragraph(wrapped, styles["BodyText"]))
        story.append(Spacer(1, 4 * mm))

    table_data = document.get("table") if isinstance(document, dict) else None
    if table_data:
        table = Table(table_data, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172033")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9aa8bc")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=str(document["title"]),
        author="ResearchOps synthetic fixture generator",
    )
    doc.build(story)


def write_expected_results() -> None:
    output_dir = ROOT / "expected-results"
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in EXPECTED_RESULTS.items():
        (output_dir / filename).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    for document in DOCUMENTS:
        build_pdf(document)
    write_expected_results()


if __name__ == "__main__":
    main()
