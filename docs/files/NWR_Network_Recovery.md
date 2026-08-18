# Meridian Trust Bank — Card Network Recovery Policy

**Document ID:** NWR
**Document Title:** Card Network Chargeback Recovery Policy (Visa, Mastercard, ATM Networks)
**Issuing Body:** Disputes & Fraud Operations, Recovery Unit, Meridian Trust Bank
**Source Type:** internal_policy
**Corpus Snapshot:** 2026-07-01
**Jurisdiction:** US (federal)

> *This is a synthetic policy document created for academic use. It does not describe any real financial institution and must not be relied upon for any operational purpose. Reason-code numbers are illustrative of the general shape of real card-network chargeback programs, not a current or authoritative citation to any network's actual rules — verify against the live Visa/Mastercard/network operating regulations before relying on any of it outside this project.*

---

## 1. Scope

### NWR-1.1 — Scope and Purpose

**Effective:** 2023-01-01 → present
**Applies to:** All claims that have reached a final or provisional Approve/Inconclusive determination under the rail-specific policies (ACH, CCD, DBD, ZEL) or FRD
**Cross-references:** FRD-8.1, CCD-4.2, DBD-4.2

Recovery is the process by which Meridian Trust, having credited an accountholder for a disputed transaction, attempts to recover that amount from the transaction's merchant via the merchant's acquiring bank, under the applicable card network's chargeback rules.

Recovery is only relevant once a credit has been issued or is likely to be issued. A claim that has been denied under any rail-specific policy involves no credit to the accountholder and is never eligible for recovery — there is nothing for Meridian Trust to recoup, since the disputed amount was never released to the accountholder in the first place.

### NWR-1.2 — Relationship to the Underlying Claim Determination

**Effective:** 2023-01-01 → present
**Applies to:** All recovery assessments
**Cross-references:** NWR-1.1, FRD-1.1

A recovery assessment does not reopen or revisit the underlying claim determination. It is a separate, downstream question: given the determination already reached, is the amount recoverable from the merchant, and under which network reason code. Recovery Unit staff (or an automated recovery assessment) must treat the claim's decision and supporting evidence as given.

A claim in `inconclusive` status may still be recovery-eligible where a provisional credit has already been issued to the accountholder pending final resolution — provisional-credit rules under the rail-specific policies (e.g. CCD-4.2, DBD-4.2) commonly require crediting the accountholder within a fixed number of days of the dispute being filed, independent of whether the investigation has concluded. Where no provisional credit was issued on an inconclusive claim, there is nothing yet to recover.

---

## 2. Visa Chargeback Reason Codes

### NWR-2.1 — Visa Fraud-Related Reason Codes

**Effective:** 2025-01-01 → present
**Applies to:** Fraud claims (claim_type: fraud) settled on a Visa-branded card
**Cross-references:** FRD-2.1, FRD-4.2, NWR-2.3

Where the underlying claim was adjudicated as fraud, the following Visa reason codes are the standard starting point for a recovery filing:

| Reason code | Category | Typical fact pattern |
|---|---|---|
| 10.1 | Fraud — Card-Absent Transaction | Fraudulent purchase where the card was not physically present (online, phone) |
| 10.2 | Fraud — Card Present Transaction | Fraudulent purchase where the card was physically present but the transaction was not authorized |
| 10.4 | Fraud — Card-Absent Environment | Card-not-present fraud where EMV liability shift does not apply |

Selection between 10.1, 10.2, and 10.4 depends on the transaction's channel (recorded on the disputed transaction as `channel`) and whether the fraud investigation identified card-present indicators (e.g. `account_red_flags` or `system_access_log_check` evidence pointing to in-person use vs. remote/card-not-present use). Do not select a card-present code (10.2) for a transaction recorded as card-absent, and vice versa — the network will reject a filing where the reason code contradicts the transaction's own recorded channel.

### NWR-2.2 — Visa Non-Fraud Reason Codes

**Effective:** 2025-01-01 → present
**Applies to:** Billing-dispute claims (claim_type: billing_dispute) settled on a Visa-branded card
**Cross-references:** CCD-2.1, DBD-2.1, NWR-2.3

Where the underlying claim was adjudicated as a billing dispute rather than fraud, the following Visa reason codes apply:

| Reason code | Category | Typical fact pattern |
|---|---|---|
| 12.6.1 | Duplicate Processing | The same transaction was processed and posted more than once |
| 13.1 | Merchandise/Services Not Received | Accountholder paid but never received the goods or services |
| 13.7 | Cancelled Merchandise/Services | Accountholder cancelled a recurring service and was charged anyway |

A duplicate-charge claim (`duplicate_charge_check: PASS` on the underlying claim) maps directly to reason code 12.6.1. Reason codes 13.1 and 13.7 require evidence in the claim's evidence trail that was not gathered by this project's current check taxonomy (specs/technical.md §4 does not include a merchandise-receipt check) — do not select 13.1 or 13.7 without that evidence actually present in the claim file; find the claim not eligible for those grounds instead of inferring them.

### NWR-2.3 — Visa Filing Windows

**Effective:** 2025-01-01 → present
**Applies to:** All Visa reason codes at NWR-2.1, NWR-2.2
**Cross-references:** NWR-2.1, NWR-2.2, NWR-5.1

A Visa chargeback must be filed within **120 calendar days** of the transaction's `occurred_at` date for fraud reason codes (10.x series), and within **120 calendar days** of the transaction's `occurred_at` date for non-fraud reason codes (12.x/13.x series). There is no extension of this window for either category — a claim adjudicated after the window has already closed is not recovery-eligible under this section, regardless of the merits of the underlying claim.

---

## 3. Mastercard Chargeback Reason Codes

### NWR-3.1 — Mastercard Fraud-Related Reason Codes

**Effective:** 2025-01-01 → present
**Applies to:** Fraud claims (claim_type: fraud) settled on a Mastercard-branded card
**Cross-references:** FRD-2.1, FRD-4.2, NWR-3.3

| Reason code | Category | Typical fact pattern |
|---|---|---|
| 4837 | No Cardholder Authorization | Cardholder states they did not authorize the transaction |
| 4840 | Fraudulent Processing of Transactions | Transaction was fraudulently processed by the merchant or a compromised terminal |
| 4849 | Questionable Merchant Activity | Merchant is associated with a documented pattern of fraudulent activity |

Reason code 4849 requires evidence of a merchant-level pattern (e.g. multiple unrelated claims against the same merchant), which this project's evidence model does not currently track per merchant — do not select 4849 without that evidence actually present; 4837 is the standard default for an individual unauthorized-transaction fraud claim absent merchant-pattern evidence.

### NWR-3.2 — Mastercard Non-Fraud Reason Codes

**Effective:** 2025-01-01 → present
**Applies to:** Billing-dispute claims (claim_type: billing_dispute) settled on a Mastercard-branded card
**Cross-references:** CCD-2.1, DBD-2.1, NWR-3.3

| Reason code | Category | Typical fact pattern |
|---|---|---|
| 4834 | Duplicate Processing | The same transaction was processed and posted more than once |
| 4853 | Cardholder Dispute — Not Elsewhere Classified | General merchandise/services dispute not covered by a more specific code |
| 4855 | Goods or Services Not Provided | Accountholder paid but never received the goods or services |

A duplicate-charge claim maps to reason code 4834, the Mastercard analogue of Visa's 12.6.1. As with the Visa non-fraud codes at NWR-2.2, do not select 4853 or 4855 without documented merchandise/service-receipt evidence in the claim file.

### NWR-3.3 — Mastercard Filing Windows

**Effective:** 2025-01-01 → present
**Applies to:** All Mastercard reason codes at NWR-3.1, NWR-3.2
**Cross-references:** NWR-3.1, NWR-3.2, NWR-5.1

A Mastercard chargeback must be filed within **120 calendar days** of the transaction's `occurred_at` date, for both fraud (48xx) and non-fraud reason codes. As with Visa (NWR-2.3), there is no extension of this window.

---

## 4. ATM Network Rules

### NWR-4.1 — ATM Network Recovery (NYCE / STAR / Pulse)

**Effective:** 2025-01-01 → present
**Applies to:** Claims involving an ATM transaction (`channel: atm` on the disputed transaction)
**Cross-references:** DBD-1.1, NWR-4.2

ATM transactions are not routed through Visa or Mastercard's card-present chargeback programs; they are recovered, where recoverable, through the regional ATM network the transaction was originated on (commonly NYCE, STAR, or Pulse for a Meridian Trust debit card). The applicable network is recorded on the transaction record's `channel`/routing metadata where available; where it is not recorded, the claim is not recovery-eligible under this section — do not guess which ATM network handled a given transaction.

### NWR-4.2 — ATM Network Filing Window

**Effective:** 2025-01-01 → present
**Applies to:** All ATM network recovery filings under NWR-4.1
**Cross-references:** NWR-4.1, NWR-5.1

An ATM network recovery request must be filed within **45 calendar days** of the transaction's `occurred_at` date — materially shorter than the card-network windows at NWR-2.3 and NWR-3.3. A claim adjudicated more than 45 days after the disputed ATM transaction occurred is not recovery-eligible under this section, even where the underlying claim was correctly approved.

---

## 5. Filing Windows and Deadlines — Summary

### NWR-5.1 — Consolidated Filing Window Table

**Effective:** 2025-01-01 → present
**Applies to:** All recovery filings
**Cross-references:** NWR-2.3, NWR-3.3, NWR-4.2

| Network | Category | Filing window (from transaction `occurred_at`) |
|---|---|---|
| Visa | Fraud (10.x) | 120 calendar days |
| Visa | Non-fraud (12.x/13.x) | 120 calendar days |
| Mastercard | Fraud (48xx) | 120 calendar days |
| Mastercard | Non-fraud (48xx) | 120 calendar days |
| ATM network (NYCE/STAR/Pulse) | All | 45 calendar days |

The filing deadline is always computed from the disputed transaction's own `occurred_at` timestamp (from `lookup_transaction`), never from the claim's `filed_at`/submission date — the same distinction FRD-1.1 and this project's tool docstrings already draw for the underlying claim, and it applies identically here.

---

## 6. Evidence and Documentation Package

### NWR-6.1 — Required Documentation Package Contents

**Effective:** 2025-01-01 → present
**Applies to:** All recovery filings found eligible under this policy
**Cross-references:** FRD-7.1, FRD-7.2

A recovery filing package must include: the applicable network and reason code with the specific policy provision relied upon to select it; the transaction detail (reference, amount, merchant, date/time, channel); the underlying claim's decision and decision reason; the specific check-ledger evidence supporting recoverability (e.g. the fraud or duplicate-charge evidence that closed the underlying checks); and the filing deadline computed under NWR-5.1, with the date basis shown.

A package that asserts eligibility without citing the specific retrieved provision it relies on does not satisfy this requirement — consistent with FRD-7.2's audit trail standard for the underlying claim, a recovery determination must be reproducible from what it cites, not from the reasoning model's own unstated judgment.

---

## 7. Exclusions

### NWR-7.1 — Non-Recoverable Scenarios

**Effective:** 2025-01-01 → present
**Applies to:** All recovery assessments
**Cross-references:** NWR-1.1, NWR-2.3, NWR-3.3, NWR-4.2

A claim is not recovery-eligible, regardless of its underlying decision, where any of the following applies:

1. The underlying claim decision is `deny` — no credit was issued, so there is nothing to recover (NWR-1.1);
2. The underlying claim is `inconclusive` and no provisional credit was issued (NWR-1.2);
3. The applicable filing window under NWR-5.1 has already elapsed as of the assessment date;
4. The disputed transaction's channel/network cannot be determined from the claim's evidence (e.g. an ATM transaction with no recorded network per NWR-4.1);
5. The only available reason code would require evidence this project's check taxonomy does not gather (e.g. merchandise-receipt or merchant-pattern evidence per NWR-2.2/NWR-3.1/NWR-3.2) and that evidence is not actually present in the claim's check ledger.

Ground 5 exists for the same reason FRD-2.4's ground 6 excludes novel-provision claims from automated determination elsewhere in this corpus: a recovery filing built on an inferred fact not actually in the claim file is a well-reasoned but ungrounded filing, and the network will reject it on review regardless of how plausible the inference was.
