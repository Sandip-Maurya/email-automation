# Pharma Trade Terms — Plain-Language Guide

**For non-technical users**

This guide explains the **pharma trade terms** you’ll see in emails and in this app. The app **reads incoming emails**, **understands** what they’re about, **processes** them using internal data and rules, and **sends a reply** on your behalf. Knowing these terms helps you understand what kind of emails the app handles and what the replies mean.

---

## What This App Does (In Simple Terms)

1. **Read** — The app receives an email (e.g. in your Inbox).
2. **Understand** — It figures out what the email is about (inventory, access, allocation, or general questions).
3. **Process** — It looks up the right information (stock levels, certifications, allocation, or past similar answers) and drafts a reply.
4. **Send reply** — It sends a professional email back to the sender.

The terms below are the **business and regulatory concepts** that appear in those emails and in the app’s logic.

---

## Product and Identification

### NDC (National Drug Code)

- **What it is:** A unique number that identifies a specific drug (strength, form, and package) in the US.
- **Why it matters:** When someone asks “Do you have product 12345-678-90?” they’re usually referring to its NDC. The app uses NDC to look up inventory, allocation, or product-related access.

### Distributor

- **What it is:** A company that buys medicines from manufacturers and delivers them to pharmacies, hospitals, or other customers (e.g. Cardinal Health, McKesson, AmerisourceBergen).
- **Why it matters:** Emails often ask about stock “at Cardinal” or “through McKesson.” The app uses the distributor name to find the right inventory or allocation data.

### Location / Warehouse / DC (Distribution Center)

- **What it is:** A specific place where product is stored (e.g. a warehouse or distribution center code like “Midwest DC” or “WH-12”).
- **Why it matters:** For supply questions, the app may need to report stock at a specific location or site.

---

## Types of Emails the App Handles (Scenarios)

The app sorts each email into **one of four types** (scenarios). Each type uses different data and a different style of reply.

### S1 — Product Supply (Inventory / Stock)

- **What it means:** Emails about **inventory**, **stock levels**, **product availability**, or **how much product is on hand** at a location or distributor.
- **Examples:** “What’s the current inventory for NDC 12345 at ABC Distributor?” or “Can you confirm stock at the Midwest DC?”
- **What the app does:** It looks up inventory data (e.g. from systems like 852 or Value Track), then replies with availability and quantities when possible.

### S2 — Product Access (Who Can Get the Product)

- **What it means:** Emails about **whether a customer or account is allowed** to order or receive a product. This includes certifications, eligibility, and account verification.
- **Examples:** “Are we REMS certified?” “What’s our 340B status?” “Can you verify our class of trade and LDN?”
- **What the app does:** It looks up the customer/account (e.g. by DEA number or name) and replies with access-related information (class of trade, REMS, 340B, etc.).

### S3 — Product Allocation (How Much Can Be Supplied)

- **What it means:** Emails about **allocation** — how much product a customer or distributor is allowed to order in a given period (e.g. by year), often for scarce or controlled products.
- **Examples:** “What’s our allocation for 2025 for NDC 77777?” “How is allocation split between Cardinal and McKesson?”
- **What the app does:** It looks up allocation data (e.g. from a DCS-style system) and replies with allocation percentages, limits, or quantities when available.

### S4 — Catch-All (General Questions)

- **What it means:** **General inquiries** that don’t fit supply, access, or allocation — e.g. business hours, ordering process, documentation, contact info, or product information.
- **Examples:** “What are your business hours?” “What documentation do you need to place an order?” “How do we get in touch with a rep?”
- **What the app does:** It searches for similar past answers (or standard info) and drafts a helpful, professional reply.

---

## Terms Used in Product Access (S2)

These terms often appear in emails about **who can access** a product or **account verification**.

### REMS (Risk Evaluation and Mitigation Strategy)

- **What it is:** A set of FDA-required rules and programs to make sure certain higher-risk drugs are used safely (e.g. training, certifications, or restrictions on who can prescribe or dispense).
- **Why it matters:** Customers may need to be **REMS certified** before they can order or dispense the product. The app may reply with whether an account is REMS certified or in good standing.

### 340B

- **What it is:** A US federal program that lets certain hospitals and clinics buy outpatient drugs at discounted prices so they can serve more low-income or uninsured patients.
- **Why it matters:** Emails may ask “Are we 340B eligible?” The app may look up and report 340B eligibility status for the account.

### DEA Number (Drug Enforcement Administration Number)

- **What it is:** A registration number the DEA assigns to entities that can handle controlled substances (e.g. pharmacies, hospitals). It’s used to identify and verify the account.
- **Why it matters:** The app often uses the DEA number (or customer name) to find the right account and then reply about access, REMS, or class of trade.

### Class of Trade (COT)

- **What it is:** The **type of customer** or channel (e.g. retail pharmacy, hospital, specialty pharmacy, clinic). It affects pricing, eligibility, and which products or programs they can access.
- **Why it matters:** Emails may ask “What’s our class of trade?” or “Can you verify our class of trade?” The app looks up and states the account’s class of trade when available.

### LDN (License / Account Identifier)

- **What it is:** In pharma trade, **LDN** often refers to a **license or account identifier** used to identify a specific customer or location in the manufacturer’s or distributor’s systems.
- **Why it matters:** Emails may ask for “LDN verification” when setting up or verifying an account. The app may use it in access and verification replies.

---

## Terms Used in Product Supply (S1)

### Inventory / Stock Levels / Quantity on Hand

- **What it is:** How many units of a product are available at a given location or distributor.
- **Why it matters:** Many emails ask “What’s in stock?” or “Can you confirm inventory for NDC X at distributor Y?” The app uses inventory-style data (e.g. 852 or Value Track) to answer.

### 852 / Value Track

- **What they are:** **852** is a standard (EDI or data) used for inventory and product movement in the supply chain. **Value Track** is an IQVIA service that tracks product movement and inventory in the market.
- **Why it matters:** The app may get inventory numbers from systems that use 852 or Value Track–style data. You don’t need to use these terms in day-to-day work; they’re the technical sources behind “current stock” answers.

---

## Terms Used in Product Allocation (S3)

### Allocation

- **What it is:** The **amount or share** of product a customer or distributor is allowed to order or receive in a given period (e.g. a calendar year). Used when supply is limited or controlled.
- **Why it matters:** Emails ask “What’s our allocation for 2025?” or “What are our allocation limits?” The app looks up allocation data and replies with percentages or quantities when available.

### Allocation Percentage / Limits

- **What it is:** A **percentage** or **cap** that defines how much of the available product a customer or distributor can get (e.g. “You have 5% of national allocation” or “Limit 100 units per quarter”).
- **Why it matters:** Replies may include these numbers so the customer can plan orders.

### Year-Based Allocation

- **What it is:** Allocation that is defined **per calendar year** (e.g. 2024, 2025). Customers may ask for “allocation for 2025” or “2024–2025.”
- **Why it matters:** The app uses the year (or range) from the email to look up the right allocation period.

### DCS (Demand / Allocation System)

- **What it is:** In this app, **DCS** refers to a **demand or allocation system** that holds allocation data (who gets how much, by product, distributor, and year).
- **Why it matters:** The app may get allocation numbers from a DCS-style system so it can answer “What’s our allocation?” accurately.

### Spec-Buy / WAC (Optional Context)

- **Spec-buy** can refer to special purchase or reporting programs. **WAC** (Wholesale Acquisition Cost) is a list price used in pharma. They may be referenced in allocation or reporting contexts in internal systems; the app’s replies focus on allocation and limits in plain language.

---

## How the Terms Fit Together

| Email is about…              | Scenario | Main terms you might see                    |
|-----------------------------|----------|---------------------------------------------|
| Stock, inventory, availability | S1       | NDC, distributor, location, quantity        |
| Who can order, certifications | S2       | REMS, 340B, DEA, class of trade, LDN        |
| How much we can get (limits)  | S3       | Allocation, percentage, limits, year, DCS   |
| General questions, process    | S4       | Business hours, ordering, documentation      |

---

## Quick Reference — Abbreviations

| Term   | Full form / meaning                          |
|--------|----------------------------------------------|
| NDC    | National Drug Code (unique drug identifier)  |
| REMS   | Risk Evaluation and Mitigation Strategy      |
| 340B   | Federal discounted drug program              |
| DEA    | Drug Enforcement Administration (number)     |
| COT    | Class of Trade                              |
| LDN    | License / account identifier               |
| DCS    | Demand / allocation system                  |
| DC     | Distribution center (warehouse/location)     |

---

*This guide is based on the email automation app’s scenarios (S1–S4) and the pharma trade terms used in its docs and code. For technical setup and workflows, see the other docs in this folder.*
