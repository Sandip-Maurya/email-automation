# Core Workflow

This document describes the core processing workflow at a high level, then in detail for each scenario (S1–S4). All diagrams are ASCII/text.

---

## High-Level Pipeline (All Scenarios)

Every email thread is processed by the same pipeline: **fetch thread → classify (A0) → scenario branch (extract → trigger API → draft) → review (A10) → format (A11) → send**. Only the middle branch (which input agent, which trigger API, which draft agent) varies by scenario.

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
           +---> S1 ---> A1 extract -> Inventory API -> A7 draft ---+
           |                                                      |
           +---> S2 ---> A2 extract -> Access API  -> A7 draft ---+
           |                                                      |
           +---> S3 ---> A3 extract -> Allocation API -> A8 draft -+
           |                                                      |
           +---> S4 ---> A4 extract -> RAG search  -> A8 draft ---+
                                                                  |
                                                                  v
  +------------------+
  |  A10 Review      |   review_draft(draft, context) -> ReviewResult
  |  (quality check) |   status: approved | needs_human_review
  +--------+---------+
           |
           v
  +------------------+
  |  A11 Email       |   format_final_email(draft, review, reply_to, sender_name)
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

- **Low confidence / missing fields**: If the input agent returns confidence &lt; 0.5 and `missing_fields` is non-empty, the orchestrator logs a step "Low confidence / missing data -> flag for human" (review agent can still approve or flag).
- **Context for review**: Each branch builds `context_for_review = {"inputs": inputs, "trigger_data": trigger_data}` and passes it to A10.
- **Result**: `ProcessingResult` contains thread_id, scenario, decision_confidence, draft, review, final_email, and raw_data (including sent_message_id/sent_at when a reply was sent).

---

## Scenario S1: Product Supply

**High level:** Incoming mail is classified as S1 when it is about inventory, stock levels, product availability, quantities at locations or distributors, or NDC inventory checks. The pipeline extracts location, distributor, and NDC (A1), calls the mock Inventory API to get matching records and total quantity, then A7 drafts a supply-style reply. The draft is reviewed by A10 and formatted by A11 before send.

**ASCII flow (S1 only):**

```
  EmailThread
       |
       v
  +---------+
  | A1      |  extract_supply(thread) -> ProductSupplyInput
  | Extract |  location, distributor, ndc, confidence, missing_fields
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
  | A7      |  draft_supply_or_access("S1", inputs, trigger_data, original_subject)
  | Draft   |  -> DraftEmail (subject, body, scenario=S1, metadata)
  +----+----+
       |
       v
  A10 Review -> A11 Format -> Send
```

**Detail**

| Step        | What happens |
|------------|----------------|
| **Input (A1)** | `ProductSupplyInput`: optional `location`, `distributor`, `ndc`; `confidence` (0–1); `missing_fields` list. |
| **Trigger**    | `inventory_api_fetch(inputs)`: reads inventory CSV, filters rows by NDC (substring), distributor (substring), location (substring); returns `records` (list of InventoryRecord dicts) and `total_quantity_available`. |
| **Draft (A7)** | `draft_supply_or_access("S1", inputs, trigger_data, original_subject)`: produces draft subject and body for a supply/inventory reply using extracted inputs and API result. |
| **After draft**| Same as all scenarios: A10 review → A11 format → send if provider and reply_to_message_id are set. |

---

## Scenario S2: Product Access

**High level:** S2 covers customer access, class of trade, REMS certification, 340B eligibility, DEA registration, and account/address verification. The pipeline extracts customer, distributor, NDC, DEA number, address, 340B flag, and contact (A2), calls the mock Access API to get class of trade and REMS/340B status, then A7 drafts an access-style reply. Review and format then follow.

**ASCII flow (S2 only):**

```
  EmailThread
       |
       v
  +---------+
  | A2      |  extract_access(thread) -> ProductAccessInput
  | Extract |  customer, distributor, ndc, dea_number, address, is_340b, contact,
  |         |  confidence, missing_fields
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
| **Input (A2)** | `ProductAccessInput`: optional `customer`, `distributor`, `ndc`, `dea_number`, `address`, `is_340b`, `contact`; `confidence`; `missing_fields`. |
| **Trigger**    | `access_api_fetch(inputs)`: loads customers CSV; finds first row where DEA matches or customer name contains input; returns `class_of_trade`, `rems_certified`, `is_340b`, optional `address`/`customer_id`, and `source`. If no match, returns defaults (e.g. class_of_trade "Unknown", rems_certified False). |
| **Draft (A7)** | `draft_supply_or_access("S2", inputs, trigger_data, original_subject)`: drafts reply for access/REMS/340B using inputs and API result. |
| **After draft**| A10 → A11 → send (same as all scenarios). |

---

## Scenario S3: Product Allocation

**High level:** S3 is for allocation requests, allocation percentages or limits, and year-based or distributor allocation. The pipeline extracts urgency, year range, distributor, and NDC (A3), calls the mock Allocation API to get allocation records and totals, then A8 drafts an allocation-style reply. Review and format then follow.

**ASCII flow (S3 only):**

```
  EmailThread
       |
       v
  +---------+
  | A3      |  extract_allocation(thread) -> ProductAllocationInput
  | Extract |  urgency, year_start, year_end, distributor, ndc, confidence, missing_fields
  +----+----+
       |
       v
  +------------------+
  | Allocation API   |  allocation_api_simulate(inputs)
  | (mock, DCS-style)|  Loads allocations CSV, filters by ndc/distributor/year range
  |                  |  -> { allocation_records[], total_quantity_allocated,
  |                  |       total_quantity_used, year_start, year_end, source, spec_buy_note }
  +--------+---------+
           |
           v
  +---------+
  | A8      |  draft_allocation_or_catchall("S3", inputs, trigger_data, original_subject)
  | Draft   |  -> DraftEmail (subject, body, scenario=S3, metadata)
  +----+----+
       |
       v
  A10 Review -> A11 Format -> Send
```

**Detail**

| Step        | What happens |
|------------|----------------|
| **Input (A3)** | `ProductAllocationInput`: optional `urgency`, `year_start`, `year_end`, `distributor`, `ndc`; `confidence`; `missing_fields`. |
| **Trigger**    | `allocation_api_simulate(inputs)`: loads allocations CSV; filters by NDC (substring), distributor (substring), and year in [year_start, year_end] (defaults 2025); returns `allocation_records`, `total_quantity_allocated`, `total_quantity_used`, year range, `source`, and a `spec_buy_note`. |
| **Draft (A8)** | `draft_allocation_or_catchall("S3", inputs, trigger_data, original_subject)`: drafts reply for allocation using inputs and API result. |
| **After draft**| A10 → A11 → send (same as all scenarios). |

---

## Scenario S4: Catch-All

**High level:** S4 is the fallback for general inquiries, ordering process, documentation, business hours, contact info, or anything that does not clearly fit S1–S3. The pipeline extracts topics and a question summary (A4), runs a mock RAG search over past emails, then A8 drafts a reply using similar past content. Review and format then follow.

**ASCII flow (S4 only):**

```
  EmailThread
       |
       v
  +---------+
  | A4      |  extract_catchall(thread) -> CatchAllInput
  | Extract |  topics[], question_summary, confidence, missing_fields
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
  | A8      |  draft_allocation_or_catchall("S4", inputs, trigger_data, original_subject)
  | Draft   |  -> DraftEmail (subject, body, scenario=S4, metadata)
  +----+----+
       |
       v
  A10 Review -> A11 Format -> Send
```

**Detail**

| Step        | What happens |
|------------|----------------|
| **Input (A4)** | `CatchAllInput`: `topics` (list of strings), optional `question_summary`; `confidence`; `missing_fields`. |
| **Trigger**    | `rag_search_find_similar(inputs)`: loads past_emails CSV; keeps rows where any topic appears in topic/subject/body or question_summary appears in subject/body; returns `similar_emails` (list of {email_id, subject, body, topic}). If no matches, returns first 3 rows as fallback. |
| **Draft (A8)** | `draft_allocation_or_catchall("S4", inputs, trigger_data, original_subject)`: drafts reply using extracted topics/summary and similar past emails. |
| **After draft**| A10 → A11 → send (same as all scenarios). |

---

## Shared Post-Draft Steps (All Scenarios)

```
  DraftEmail + context_for_review
       |
       v
  +------------+
  | A10 Review |  review_draft(draft, context) -> ReviewResult
  |            |  status: "approved" | "needs_human_review"
  |            |  confidence, quality_score, accuracy_notes[], suggestions[]
  +-----+------+
        |
        v
  +------------+
  | A11 Format |  format_final_email(draft, review, reply_to, sender_name) -> FinalEmail
  |            |  Adds human-review header if status is needs_human_review
  |            |  Personalizes greeting with sender_name
  +-----+------+
        |
        v
  +------------+
  | Send       |  provider.reply_to_message(reply_to_message_id, final_email.body, user_id)
  | (optional) |  Only if provider and reply_to_message_id are set
  +------------+
```

The final `ProcessingResult` is built with thread_id, scenario, decision_confidence, draft, review, final_email, and raw_data (including sent_message_id and sent_at when a reply was sent).
