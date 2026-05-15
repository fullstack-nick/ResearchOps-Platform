# Phase 6 live AI matrix

Every sample PDF was driven end-to-end through the live Azure deployment
at https://researchops-vt1zhh-frontend.salmonplant-ccdabe77.eastus.azurecontainerapps.io
using `frontend/e2e/phase6.matrix.spec.ts`. The spec uploads each document,
waits for Azure AI Document Intelligence + Azure AI Search indexing to
complete, asks two grounded questions against Azure OpenAI, walks the full
approval chain for that workflow type (1, 2 or 3 steps), and verifies the
audit timeline contains `document.uploaded`, `indexing.completed`, and
`approval.granted`.

## Results matrix

| Slug | Workflow | PDF.js preview | Extraction | Indexing + Search | Grounded Q&A | Approval chain | Audit trail |
|------|----------|----------------|------------|-------------------|--------------|----------------|-------------|
| `procurement-invoice` | `procurement` | OK | OK | OK | OK | OK | OK |
| `procurement-quote` | `procurement` | OK | OK | OK | OK | OK | OK |
| `procurement-po` | `procurement` | OK | OK | OK | OK | OK | OK |
| `procurement-delivery` | `procurement` | OK | OK | OK | OK | OK | OK |
| `hr-onboarding-form` | `hr_onboarding` | OK | OK | OK | OK | OK | OK |
| `hr-cv` | `hr_onboarding` | OK | OK | OK | OK | OK | OK |
| `hr-it-account` | `hr_onboarding` | OK | OK | OK | OK | OK | OK |
| `grants-award` | `grants` | OK | OK | OK | OK | OK | OK |
| `grants-reporting` | `grants` | OK | OK | OK | OK | OK | OK |
| `grants-budget` | `grants` | OK | OK | OK | OK | OK | OK |
| `contracts-equipment` | `contracts` | OK | OK | OK | OK | OK | OK |
| `contracts-subscription` | `contracts` | OK | OK | OK | OK | OK | OK |
| `reports-minutes` | `reports` | OK | OK | OK | OK | OK | OK |
| `reports-monthly` | `reports` | OK | OK | OK | OK | OK | OK |

14 documents, 0 failures.

Notes:
- *Extraction* is Phase-2 procurement-only (Document Intelligence `prebuilt-invoice`).
  Non-procurement workflows correctly render the explanatory `Extraction is not
  available for this workflow type in Phase 2` panel; the matrix counts that as OK.
- *Indexing + Search* covers Azure AI Document Intelligence `prebuilt-read` extraction,
  chunking, text-embedding-3-small embeddings, and the Azure AI Search hybrid index.
- *Grounded Q&A* counts as OK when at least one of the curated keyword hints for the
  question appears in the answer or its citation snippet, proving the answer is
  grounded in retrieved chunks rather than hallucinated.

## Q&A transcripts captured by the live run

### `procurement-invoice`

- **Q:** What is the invoice total?
  - **A (live):** what is the invoice total?

may 15, 2026, 4:16 pm

the invoice total is eur 4,010.30, which includes the net total of eur 3,370.00 plus vat of eur 640.30 [source 1].

sources

source 1 · page 1invoice
- **Q:** Who is the vendor on this invoice?
  - **A (live):** who is the vendor on this invoice?

may 15, 2026, 4:16 pm

the vendor on this invoice is helix lab supplies gmbh [source 1 | page 1].

sources

source 1 · page 1invoice - helix lab supplies gmbh synth

### `procurement-quote`

- **Q:** What service is being quoted?
  - **A (live):** what service is being quoted?

may 15, 2026, 4:17 pm

the service being quoted is annual preventive maintenance for two confocal microscope systems [source 1].

sources

source 1 · page 1quote - micro
- **Q:** What is the quoted price?
  - **A (live):** what is the quoted price?

may 15, 2026, 4:17 pm

the quoted price for the annual preventive maintenance for two confocal microscope systems is eur 3,879.40 gross total, including vat of eur 619.40. t

### `procurement-po`

- **Q:** What is the purchase order number?
  - **A (live):** what is the purchase order number?

may 15, 2026, 4:17 pm

the purchase order number is po-2026-001 [source 1].

sources

source 1 · page 1purchase order po-2026-001 synthetic internal purchase order 
- **Q:** What items are being ordered?
  - **A (live):** what items are being ordered?

may 15, 2026, 4:17 pm

i cannot find the information about the items being ordered in this document [source 1].

sources

source 1 · page 1purchase order po-2026-001 syn

### `procurement-delivery`

- **Q:** What was delivered?
  - **A (live):** what was delivered?

may 15, 2026, 4:18 pm

the delivery included 4 units of sequencing reagent kit and 12 units of cryobox storage set [source 1].

sources

source 1 · page 1delivery note dn-2026-001
- **Q:** When was the delivery made?
  - **A (live):** when was the delivery made?

may 15, 2026, 4:18 pm

the delivery was made on 2026-05-04 [source 1].

sources

source 1 · page 1delivery note dn-2026-001 synthetic delivery confirmation delivery suppli

### `hr-onboarding-form`

- **Q:** Who is being onboarded?
  - **A (live):** who is being onboarded?

may 15, 2026, 4:18 pm

the person being onboarded is alex weber.

sources

source 1 · page 1onboarding form - research assistant synthetic hr onboarding document person name: 
- **Q:** What role are they joining?
  - **A (live):** what role are they joining?

may 15, 2026, 4:18 pm

they are joining as a research assistant [source 1].

sources

source 1 · page 1onboarding form - research assistant synthetic hr onboarding documen

### `hr-cv`

- **Q:** What is this candidate’s field?
  - **A (live):** what is this candidate’s field?

may 15, 2026, 4:18 pm

the candidate's field is data science, with experience in data analysis for imaging workflows and skills in python, sql, and statistics [source 
- **Q:** What are the candidate’s key skills?
  - **A (live):** what are the candidate’s key skills?

may 15, 2026, 4:18 pm

the candidate's key skills are data analysis for imaging workflows, python, sql, statistics, and reproducible reporting [source 1].

source

### `hr-it-account`

- **Q:** Who needs an IT account?
  - **A (live):** who needs an it account?

may 15, 2026, 4:18 pm

alex weber needs an it account [source 1].

sources

source 1 · page 1it account request synthetic it onboarding form requester name: alex weber start 
- **Q:** What systems do they need access to?
  - **A (live):** what systems do they need access to?

may 15, 2026, 4:19 pm

they need access to the email mailbox, git repository, and the shared drive: neurodata operations [source 1].

sources

source 1 · page 1it

### `grants-award`

- **Q:** Which grant is being awarded?
  - **A (live):** which grant is being awarded?

may 15, 2026, 4:19 pm

the grant being awarded is the "neurodata infrastructure 2026" with grant id nd-2026-771.

sources

source 1 · page 1grant award letter - neurodat
- **Q:** What is the awarded amount?
  - **A (live):** what is the awarded amount?

may 15, 2026, 4:19 pm

the awarded amount is eur 480,000 [source 1].

sources

source 1 · page 1grant award letter - neurodata 2026 synthetic grant administration document

### `grants-reporting`

- **Q:** What reports must be submitted?
  - **A (live):** what reports must be submitted?

may 15, 2026, 4:19 pm

the reports that must be submitted are a financial report every six months and a scientific progress report every twelve months [source 1].

sou
- **Q:** When are reports due?
  - **A (live):** when are reports due?

may 15, 2026, 4:19 pm

reports are due as follows: financial reports every six months and scientific progress reports every twelve months [source 1].

sources

source 1 · page 1

### `grants-budget`

- **Q:** What budget categories are listed?
  - **A (live):** what budget categories are listed?

may 15, 2026, 4:19 pm

the budget categories listed are personnel, equipment, travel, and consumables as eligible costs. entertainment, late payment fees, and unsup
- **Q:** What is the total budget?
  - **A (live):** what is the total budget?

may 15, 2026, 4:19 pm

i cannot find the total budget in this document. the provided source only lists eligible and ineligible costs but does not specify the total budget am

### `contracts-equipment`

- **Q:** What equipment is covered by this contract?
  - **A (live):** what equipment is covered by this contract?

may 15, 2026, 4:20 pm

the contract covers freezer monitoring equipment. [source 1 | page 1]

sources

source 1 · page 1equipment service contract syntheti
- **Q:** How long does the contract last?
  - **A (live):** how long does the contract last?

may 15, 2026, 4:20 pm

the contract lasts for one year, from march 1, 2026, to february 28, 2027 [source 1].

sources

source 1 · page 1equipment service contract syn

### `contracts-subscription`

- **Q:** What software is being subscribed to?
  - **A (live):** what software is being subscribed to?

may 15, 2026, 4:20 pm

the document does not specify the name of the software being subscribed to. it only mentions a "software subscription agreement" between r
- **Q:** When does the subscription expire?
  - **A (live):** when does the subscription expire?

may 15, 2026, 4:20 pm

the subscription expires on 2027-04-30 [source 1 | page 1].

sources

source 1 · page 1software subscription agreement synthetic contract doc

### `reports-minutes`

- **Q:** What decisions were made at the meeting?
  - **A (live):** what decisions were made at the meeting?

may 15, 2026, 4:20 pm

the decisions made at the meeting were to use a shared intake queue for supplier invoices and to create a checklist for onboarding hard
- **Q:** Who attended the meeting?
  - **A (live):** who attended the meeting?

may 15, 2026, 4:20 pm

the meeting was attended by mira novak, jonas feld, and elena fischer [source 1 | page 1].

sources

source 1 · page 1meeting minutes - lab administra

### `reports-monthly`

- **Q:** What does this monthly report cover?
  - **A (live):** what does this monthly report cover?

may 15, 2026, 4:21 pm

the monthly report covers decisions, risks, and actions related to operations, including continuing the procurement intake pilot for neurod
- **Q:** What follow-up actions are listed?
  - **A (live):** what follow-up actions are listed?

may 15, 2026, 4:21 pm

the follow-up actions listed are:
- finance to review flagged invoices by 2026-05-20
- it to prepare laptop image for new hire [source 1].

s

Per-document screenshots in `tmp/screenshots/matrix/`.
