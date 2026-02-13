# Demo Sample Emails (S1–S4)

Use these in the webhook demo or share with the audience. Each has **Subject** and **Body** only. Copy-paste into your mail client; send from an address that is in the allowed senders list.

**Mock data alignment:** Subjects and bodies below use NDCs, locations, distributors, and customer/DEA values that match the seeded DB data (`data/inventory.csv`, `data/customers.csv`, `data/allocations.csv`) so agents can reply with real lookup results.

---

## S1 – Product Supply (inventory, stock, NDC)

*Mock data: NDCs `12345-678-90` (Product Alpha), `99999-001-00` (Product Beta). Locations `WH-01` (Warehouse East), `WH-02` (Warehouse West). Distributors `DIST-A` (Acme Distribution), `DIST-B` (Beta Wholesale).*

### Mail 1

**Subject:** Inventory check for NDC 12345-678-90 at DIST-A

**Body:**

Hi,

Could you please confirm current inventory levels for NDC 12345-678-90 at location WH-01 through DIST-A (Acme Distribution)? We need to fulfill an order by end of week.

Thanks.

---

### Mail 2

**Subject:** Stock availability – Product Beta, WH-02

**Body:**

Hello,

We are checking product availability for NDC 99999-001-00. Can you provide the quantity on hand at WH-02 (Warehouse West) and at DIST-B (Beta Wholesale)?

Regards.

---

### Mail 3

**Subject:** RE: Availability at Beta Wholesale

**Body:**

Following up on our earlier request – could you share the current stock levels for NDC 12345-678-90 at location WH-01 through DIST-B? We need both Product Alpha and allocation outlook for 2025.

Thank you.

---

## S2 – Product Access (REMS, 340B, class of trade, DEA)

*Mock data: Acme Pharmacy (DEA AB1234567, Retail, REMS certified, not 340B). Hospital North (DEA CD9876543, Hospital, REMS certified, 340B). Beta Drug (DEA EF1111111, Retail, not REMS, not 340B).*

### Mail 1

**Subject:** REMS certification status for our account

**Body:**

Hi,

We need to confirm our REMS certification status for Product Alpha (NDC 12345-678-90). Our DEA number is AB1234567 and we are a retail pharmacy (Acme Pharmacy). Can you confirm we are in good standing and whether our 340B eligibility is current?

Thanks.

---

### Mail 2

**Subject:** Class of trade and REMS verification – Hospital North

**Body:**

Hello,

We are Hospital North and need verification of our class of trade and REMS status. Our DEA is CD9876543. We are a 340B participant. Can you confirm our REMS certification and access for the restricted product line?

Regards.

---

### Mail 3

**Subject:** 340B eligibility – Beta Drug

**Body:**

We need to verify our REMS certification and class of trade. Our facility is Beta Drug, DEA: EF1111111. Address: 789 Elm St. Can you confirm our current status and whether we are approved for 340B?

Thank you.

---

## S3 – Product Allocation (allocation, year, distributor)

*Mock data: Allocation records for NDC 12345-678-90 and 99999-001-00, distributors DIST-A and DIST-B, year 2025.*

### Mail 1

**Subject:** Allocation request for 2025 – NDC 12345-678-90

**Body:**

Hi,

We would like to request our allocation for calendar year 2025 for NDC 12345-678-90. We work with DIST-A (Acme Distribution) as our primary distributor. Can you provide our allocation totals and quantity used so far?

Thanks.

---

### Mail 2

**Subject:** Year 2025 allocation – NDC 99999-001-00, DIST-B

**Body:**

Hello,

We need to understand our allocation for NDC 99999-001-00 for 2025. Distributor: DIST-B (Beta Wholesale). This is urgent as we are planning our purchasing for Q1.

Regards.

---

### Mail 3

**Subject:** Allocation limits and distributor split 2025

**Body:**

Could you share our current allocation limits for NDC 12345-678-90 for 2025? We use both DIST-A and DIST-B and need to know how the allocation and quantity used are split by distributor.

Thank you.

---

## S4 – Catch-All (general inquiry, ordering, hours, contact)

*No DB lookup; RAG-style or general reply.*

### Mail 1

**Subject:** Business hours and contact for orders

**Body:**

Hi,

What are your standard business hours for order support? We also need the correct contact for placing a new order and for documentation requests.

Thanks.

---

### Mail 2

**Subject:** Ordering process and required documentation

**Body:**

Hello,

We are a new customer and would like to understand the ordering process. What documentation do you need from us before we can place an order? Is there a checklist or form we should complete?

Regards.

---

### Mail 3

**Subject:** General inquiry – product information

**Body:**

Could you send us general product information and any ordering guides you have? We are evaluating your product line and would like to know lead times and how to get in touch with a rep.

Thank you.

---

*For demo flow and script, see [docs/DEMO_WEBHOOK_GUIDE.md](docs/DEMO_WEBHOOK_GUIDE.md) and [docs/DEMO_WEBHOOK_MINDMAP.md](docs/DEMO_WEBHOOK_MINDMAP.md).*
