# Core Workflow

This document describes the core processing workflow at a high level, then in detail for each scenario (S1–S4). All diagrams are ASCII/text.

---

## High-Level Pipeline (All Scenarios)

Every email thread is processed by the same pipeline: **fetch thread → classify (A0) → scenario branch (extract → [S3 only: A_D1–A_D4 scaffold] → trigger API → draft) → Input A11 aggregate → Decision A10 review → Email A12 format → send**. Only the middle branch (which input agent, which trigger API, which draft agent) varies by scenario. S3 runs the Demand IQ scaffold (A_D1–A_D4) as placeholders before the allocation trigger. **Scenario wiring** (input agent ID, trigger name, draft agent ID, low-confidence threshold) is defined in **`config/agents.yaml`** and applied at runtime via the agent and trigger registries; the orchestrator looks up the active scenario’s config and dispatches accordingly.

```
  +------------------+
  |  Trigger entry   |   message_id or conversation_id (+ optional user_id)
  |  (process_trigger)
  +--------+---------+
           |
           v
  +------------------+
  |  Fetch thread    |   provider.get_message / get_conversation
  |  (Graph or mock) |   -> graph_messages_to_thread -> EmailThread
  +--------+---------+
           |
           v
  +------------------+
  |  A0 Decision     |   classify_thread(thread) -> ScenarioDecision
  |  (classify)      |   scenario in {S1, S2, S3, S4}, confidence, reasoning
  +--------+---------+
           |
           +---> S1 ---> A1 extract -> Inventory API -> A6 draft -------+
           |                                                             |
           +---> S2 ---> A2 extract -> Access API  -> A7 draft ----------+
           |                                                             |
           +---> S3 ---> A3 extract -> A_D1->A_D2->A_D3->A_D4 -> Allocation API -> A8 draft -+
           |                                                             |
           +---> S4 ---> A4 extract -> RAG search  -> A9 draft ----------+
                                                                        |
                                                                        v
  +------------------+
  |  Input A11       |   aggregate_context_for_decision(decision, inputs)
  |  (aggregate)     |   -> AggregatedContext (decision, ndc, distributor, year)
  +--------+---------+
           |
           v
  +------------------+
  |  Decision A10    |   review_draft(draft, context) -> ReviewResult
  |  (review)        |   status: approved | needs_human_review
  +--------+---------+
           |
           v
  +------------------+
  |  Email A12       |   format_final_email(draft, review, reply_to, sender_name)
  |  (final format)  |   -> FinalEmail (adds human-review header if flagged)
  +--------+---------+
           |
           v
  +------------------+
  |  Send reply      |   provider.reply_to_message(...) if provider set
  |  (optional)      |   raw_data gets sent_message_id, sent_at
  +------------------+
```

**Shared behavior**

- **Low confidence**: If the input agent returns confidence &lt; threshold (default 0.5), the orchestrator logs a step "Low confidence -> flag for human" (review agent can still approve or flag).
- **Context for review**: Each branch builds `context_for_review = {"inputs": inputs, "trigger_data": trigger_data, "aggregated_context": aggregated_context}` and passes it to Decision A10 (review).
- **Result**: `ProcessingResult` contains thread_id, scenario, decision_confidence, draft, review, final_email, and raw_data (including sent_message_id/sent_at when a reply was sent).

---

## Scenario S1: Product Supply

**High level:** Incoming mail is classified as S1 when it is about inventory, stock levels, product availability, quantities at locations or distributors, or NDC inventory checks. The pipeline extracts location, distributor, and NDC (A1), calls the mock Inventory API to get matching records and total quantity, then **A6** drafts a supply-style reply. The draft is followed by Input A11 aggregate, Decision A10 review, and Email A12 format before send.

**ASCII flow (S1 only):**

```
  EmailThread
       |
       v
  +---------+
  | A1      |  extract_supply(thread) -> ProductSupplyInput
  | Extract |  location, distributor, ndc, confidence
  +----+----+
       |
       v
  +----------------+
  | Inventory API  |  inventory_api_fetch(inputs)
  | (mock)         |  Loads data/csv, filters by ndc/distributor/location
  |                |  -> { records[], total_quantity_available }
  +-------+--------+
          |
          v
  +---------+
  | A6      |  Draft agent A6_draft (S1 only) -> DraftEmail
  | Draft   |  subject, body, scenario=S1, metadata
  +----+----+
       |
       v
  Input A11 aggregate -> Decision A10 Review -> Email A12 Format -> Send
```

**Detail**

| Step        | What happens |
|------------|----------------|
| **Input (A1)** | `ProductSupplyInput`: optional `location`, `distributor`, `ndc`; `confidence` (0–1). |
| **Trigger**    | `inventory_api_fetch(inputs)`: reads inventory CSV, filters rows by NDC (substring), distributor (substring), location (substring); returns `records` (list of InventoryRecord dicts) and `total_quantity_available`. |
| **Draft (A6)** | Config-driven: scenario S1 uses `A6_draft`; produces draft subject and body for a supply/inventory reply using extracted inputs and API result. |
| **After draft**| Same as all scenarios: Input A11 aggregate → Decision A10 review → Email A12 format → send if provider and reply_to_message_id are set. |

---

## Scenario S2: Product Access

**High level:** S2 covers customer access, class of trade, REMS certification, 340B eligibility, DEA registration, and account/address verification. The pipeline extracts customer, distributor, NDC, DEA number, address, 340B flag, and contact (A2), calls the mock Access API to get class of trade and REMS/340B status, then **A7** drafts an access-style reply. Input A11 aggregate, Decision A10 review, and Email A12 format then follow.

**ASCII flow (S2 only):**

```
  EmailThread
       |
       v
  +---------+
  | A2      |  extract_access(thread) -> ProductAccessInput
  | Extract |  customer, distributor, ndc, dea_number, address, is_340b, contact,
  |         |  confidence
  +----+----+
       |
       v
  +----------------+
  | Access API     |  access_api_fetch(inputs)
  | (mock)        |  Loads customers CSV, matches by DEA or customer name
  |               |  -> { class_of_trade, rems_certified, is_340b, address?, customer_id?, source }
  +-------+--------+
          |
          v
  +---------+
  | A7      |  draft_supply_or_access("S2", inputs, trigger_data, original_subject)
  | Draft   |  -> DraftEmail (subject, body, scenario=S2, metadata)
  +----+----+
       |
       v
  A10 Review -> A11 Format -> Send
```

**Detail**

| Step        | What happens |
|------------|----------------|
| **Input (A2)** | `ProductAccessInput`: optional `customer`, `distributor`, `ndc`, `dea_number`, `address`, `is_340b`, `contact`; `confidence`. |
| **Trigger**    | `access_api_fetch(inputs)`: loads customers CSV; finds first row where DEA matches or customer name contains input; returns `class_of_trade`, `rems_certified`, `is_340b`, optional `address`/`customer_id`, and `source`. If no match, returns defaults (e.g. class_of_trade "Unknown", rems_certified False). |
| **Draft (A7)** | `draft_supply_or_access("S2", inputs, trigger_data, original_subject)`: drafts reply for access/REMS/340B using inputs and API result. |
| **After draft**| A10 → A11 → send (same as all scenarios). |

---

## Scenario S3: Product Allocation

**High level:** S3 is for allocation requests, allocation percentages or limits, and year-based or distributor allocation. The pipeline extracts urgency, year range, distributor, and NDC (A3), runs the **Demand IQ scaffold** (A_D1–A_D4 placeholders: reply type, dashboard/report, check allocation, allocation simulation), then calls the mock Allocation API (with optional s3_context). **A8** drafts an allocation-style reply. Input A11 aggregate, Decision A10 review, and Email A12 format then follow.

**ASCII flow (S3 only):**

```
  EmailThread
       |
       v
  +---------+
  | A3      |  extract_allocation(thread) -> ProductAllocationInput
  | Extract |  urgency, year_start, year_end, distributor, ndc, confidence
  +----+----+
       |
       v
  +------------------+
  | S3 Scaffold      |  A_D1 (reply type) -> A_D2 (dashboard/report) -> A_D3 (check) -> A_D4 (simulation)
  | (placeholder)   |  Returns mock dicts; merged into trigger_data as s3_scaffold
  +--------+---------+
           |
           v
  +------------------+
  | Allocation API   |  allocation_api_simulate(inputs, s3_context)
  | (mock, DCS-style)|  Loads allocations CSV, filters by ndc/distributor/year range
  |                  |  -> { allocation_records[], ..., s3_scaffold? }
  +--------+---------+
           |
           v
  +---------+
  | A8      |  Draft agent A8_draft (S3 only) -> DraftEmail
  | Draft   |  subject, body, scenario=S3, metadata
  +----+----+
       |
       v
  Input A11 aggregate -> Decision A10 Review -> Email A12 Format -> Send
```

**Detail**

| Step        | What happens |
|------------|----------------|
| **Input (A3)** | `ProductAllocationInput`: optional `urgency`, `year_start`, `year_end`, `distributor`, `ndc`; `confidence`. |
| **S3 scaffold** | For S3 only: `step_s3_ad1`–`step_s3_ad4` (placeholders) run in order; results merged into `s3_context` and passed to allocation API. A_D1–A_D4 are scaffold only until real Demand IQ integration. |
| **Trigger**    | `allocation_api_simulate(inputs, s3_context=None)`: loads allocations CSV; filters by NDC, distributor, year range; when `s3_context` is provided, merges it into result as `s3_scaffold`. |
| **Draft (A8)** | Config-driven: scenario S3 uses `A8_draft`; drafts reply for allocation using inputs and API result. |
| **After draft**| Input A11 aggregate → Decision A10 → Email A12 → send (same as all scenarios). |

---

## Scenario S4: Catch-All

**High level:** S4 is the fallback for general inquiries, ordering process, documentation, business hours, contact info, or anything that does not clearly fit S1–S3. The pipeline extracts topics and a question summary (A4), runs a mock RAG search over past emails, then **A9** drafts a reply using similar past content. Input A11 aggregate, Decision A10 review, and Email A12 format then follow.

**ASCII flow (S4 only):**

```
  EmailThread
       |
       v
  +---------+
  | A4      |  extract_catchall(thread) -> CatchAllInput
  | Extract |  topics[], question_summary, confidence
  +----+----+
       |
       v
  +----------------+
  | RAG search     |  rag_search_find_similar(inputs)
  | (mock)         |  Loads past_emails CSV, matches by topics or question_summary
  |                |  -> { similar_emails[], source }
  +-------+--------+
          |
          v
  +---------+
  | A9      |  Draft agent A9_draft (S4 only) -> DraftEmail
  | Draft   |  subject, body, scenario=S4, metadata
  +----+----+
       |
       v
  Input A11 aggregate -> Decision A10 Review -> Email A12 Format -> Send
```

**Detail**

| Step        | What happens |
|------------|----------------|
| **Input (A4)** | `CatchAllInput`: `topics` (list of strings), optional `question_summary`; `confidence`. |
| **Trigger**    | `rag_search_find_similar(inputs)`: loads past_emails CSV; keeps rows where any topic appears in topic/subject/body or question_summary appears in subject/body; returns `similar_emails` (list of {email_id, subject, body, topic}). If no matches, returns first 3 rows as fallback. |
| **Draft (A9)** | Config-driven: scenario S4 uses `A9_draft`; drafts reply using extracted topics/summary and similar past emails. |
| **After draft**| Input A11 aggregate → Decision A10 → Email A12 → send (same as all scenarios). |

---

## Shared Post-Draft Steps (All Scenarios)

```
  DraftEmail
       |
       v
  +----------------+
  | Input A11      |  aggregate_context_for_decision(decision, inputs) -> AggregatedContext
  | (aggregate)    |  decision (scenario), ndc, distributor, year
  +--------+-------+
           |
           v
  context_for_review = { inputs, trigger_data, aggregated_context }
       |
       v
  +----------------+
  | Decision A10   |  review_draft(draft, context) -> ReviewResult
  | (review)       |  status: "approved" | "needs_human_review"
  |                |  confidence, quality_score, accuracy_notes[], suggestions[]
  +--------+-------+
           |
           v
  +----------------+
  | Email A12      |  format_final_email(draft, review, reply_to, sender_name) -> FinalEmail
  | (format)       |  Adds human-review header if status is needs_human_review
  |                |  Personalizes greeting with sender_name
  +--------+-------+
           |
           v
  +------------+
  | Send       |  provider.reply_to_message(reply_to_message_id, final_email.body, user_id)
  | (optional) |  Only if provider and reply_to_message_id are set
  +------------+
```

The final `ProcessingResult` is built with thread_id, scenario, decision_confidence, draft, review, final_email, and raw_data (including sent_message_id and sent_at when a reply was sent).
