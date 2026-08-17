# Corpus Index — Meridian Trust Bank Dispute & Fraud Policy Library

**Corpus snapshot:** 2026-07-01
**Documents:** 5
**Active provisions:** 101
**Superseded versions:** 4
**Total retrievable chunks:** 105

> *Synthetic corpus created for academic use. Meridian Trust Bank does not exist. No provision here reflects the policy of any real institution, and regulatory citations are illustrative rather than authoritative — verify against actual CFR text before relying on any of it outside this project.*

---

## 1. Documents

| Doc ID | Title | Provisions | Prefix pattern |
|---|---|---|---|
| CCD | Credit Card Dispute and Fraud Claims Adjudication Policy | 24 | `CCD-{section}.{rule}[.{sub}]` |
| DBD | Debit Card and EFT Dispute Adjudication Policy | 22 | `DBD-{section}.{rule}[.{sub}]` |
| ZEL | Person-to-Person Transfer Dispute and Fraud Claims Policy | 16 | `ZEL-{section}.{rule}[.{sub}]` |
| ACH | ACH Dispute, Return, and Unauthorized Debit Adjudication Policy | 19 | `ACH-{section}.{rule}[.{sub}]` |
| FRD | Cross-Rail Fraud Investigation, Scoring, and Claims Governance Policy | 20 | `FRD-{section}.{rule}[.{sub}]` |

---

## 2. Suggested Chunk Metadata

Each `###` or `####` heading is one chunk. Suggested extraction:

```json
{
  "chunk_id": "CCD-4.2",
  "citation_label": "CCD-4.2",
  "doc_id": "CCD",
  "doc_title": "Credit Card Dispute and Fraud Claims Adjudication Policy",
  "source_type": "internal_policy",
  "issuing_body": "Disputes & Fraud Operations",

  "effective_from": "2025-01-01",
  "effective_to": null,
  "supersedes": "CCD-4.2-v1",
  "superseded_by": null,
  "status": "active",

  "section_path": ["4. Provisional Credit", "CCD-4.2 Provisional Credit Timing"],
  "parent_chunk_id": "CCD-4",
  "rail": "credit_card",
  "cross_references": ["CCD-4.1", "CCD-4.3"],
  "regulatory_basis": "Regulation Z §1026.13(d)",

  "corpus_snapshot": "2026-07-01",
  "embedding_model": "<pin this>"
}
```

The `**Effective:**`, `**Supersedes:**`, `**Cross-references:**`, `**Applies to:**`, and `**Regulatory basis:**` lines are machine-parseable — they appear in a fixed order directly under each heading. Parse them into metadata and strip them from the embedded text, or keep them in; test both, since including the effective dates in the embedded text sometimes helps and sometimes adds noise.

**Embed the heading path with the text.** `"4. Provisional Credit > CCD-4.2 Provisional Credit Timing: Where a cardholder is eligible..."` retrieves better than the bare clause.

---

## 3. Superseded Pairs — for Effective-Date Filter Testing

| Active | Superseded | Boundary | What changes |
|---|---|---|---|
| CCD-4.2 | CCD-4.2-v1 | 2025-01-01 | Provisional credit: 10 business days → 2 business days; $2,500 deferral removed |
| DBD-4.2 | DBD-4.2-v1 | 2025-07-01 | New account: 60 days → 30 days; no provisional credit → 20 business days |
| ZEL-2.2.a | ZEL-2.2.a-v1 | 2026-01-01 | Imposter scope: Meridian only → any FI/government/utility; 30 → 60 day window |
| FRD-8.1 | FRD-8.1-v1 | 2026-01-01 | Automated denials: prohibited → permitted with all checks resolved |

**Suggested demo:** a credit card claim with date of first notice **2024-11-15** must retrieve **CCD-4.2-v1** (10 business days), not CCD-4.2 (2 business days). If your retrieval returns the current version, the effective-date pre-filter is not working. This one example proves the entire date-filtering design.

**Harder variant:** a Zelle imposter claim with send date **2025-11-20**, where the impersonator posed as a *different* bank. Under ZEL-2.2.a-v1 (in force) this is **not** reimbursable — the old rule covers only Meridian impersonation. Under the current ZEL-2.2.a it would be. An agent that retrieves the current version approves a claim that should be denied.

---

## 4. Near-Duplicate Provisions — for MMR and Score-Margin Testing

These pairs read almost identically and will crowd each other in similarity search:

| Pair | Why it's dangerous |
|---|---|
| CCD-2.1 / DBD-2.1 | Both "60 calendar days from statement transmission." Different rails, different liability consequences. Each carries an explicit adjudicator note warning about the other. |
| CCD-7.1 / DBD-7.1 / ZEL-7.1 / ACH-7.1 | Four denial-grounds lists with overlapping enumerations. A query about denial grounds will return all four. |
| CCD-9.1 / DBD-9.1 / ZEL-8.1 / ACH-9.1 | Four business-account exclusions with near-identical language. |
| CCD-8.1 / DBD-8.1 / ACH-8.1 | Three recurring-transaction rules, similar structure, different revocation mechanics. |
| ACH-2.1 / ACH-2.3 | Consumer 60-day vs. business 2-day return window, same document, adjacent text. |

**Test:** query *"what is the filing deadline for a disputed transaction"* without a rail filter. Without scope routing you'll get a mix of CCD-2.1, DBD-2.1, ZEL-2.3, and ACH-2.1 — with margins tight enough that rank-1 is close to arbitrary. This is exactly the condition your score-margin detector should flag as AMBIGUOUS rather than close a check.

---

## 5. Cross-Reference Chains — for Completeness Testing

Provisions that are incomplete without a second retrieval:

| Retrieve this | And you also need | Why |
|---|---|---|
| CCD-2.3 | CCD-2.3.a, CCD-2.3.b | The parent states extension is available *only* via the subrules |
| CCD-3.2 | CCD-3.2.a | Five waiver conditions live in the subrule |
| DBD-2.3 | DBD-2.3.a/b/c | Liability tiers are entirely in the subrules |
| ZEL-2.2 | ZEL-2.2.a, ZEL-3.3 | Denial requires both recall attempt and exception evaluation |
| ACH-6.1 | ACH-3.2, ACH-6.3 | Revocation vs. never-authorized distinction and the stop-payment alternative |
| FRD-2.2 | FRD-2.4 | Routing depends on exclusions defined elsewhere |
| Any rail denial | FRD-8.2 | A score may not be cited as a ground in the notice |

**Deepest chain:** ZEL-2.2 → ZEL-2.2.a → ZEL-6.1 → FRD-3.2 → FRD-3.3. Four hops from "consumer sent money to a scammer" to "here is what evidence is required before you may infer first-party fraud."

---

## 6. Deliberate Coverage Gaps — for Score-Floor Testing

The corpus contains **no** provision governing these. A correct agent returns nothing and blocks the check; an agent with fixed top-k returns the nearest neighbour and reasons from it.

1. **Wire transfer disputes** — explicitly excluded at ZEL-1.1, covered nowhere
2. **Foreign currency conversion disputes** on any rail
3. **Cryptocurrency purchases** and exchange-related claims
4. **Check fraud / forged endorsement** — no provision anywhere
5. **Merchant service quality on P2P** — CCD-3.2 covers card, nothing covers Zelle
6. **Disputes on closed accounts** — no provision on where credit is directed
7. **Joint accountholder disputing the other's transaction** — CCD-9.2 covers authorized users on credit, no analogue for joint deposit accounts
8. **Minor accountholder claims**

**Test:** *"what is the filing window for a disputed wire transfer?"* Correct behavior is zero results above the floor → `BLOCKED_NEEDS_HUMAN`. Watch for retrieval of ACH-2.1 or ZEL-2.3 as false positives — they're the nearest neighbours and neither governs.

---

## 7. Provisions with Structured Applicability

These carry explicit enumerated conditions and are good candidates for extracting `applies_to` fields to validate programmatically rather than trusting the model's reading:

- **ZEL-2.2.a** — four conditions, all required
- **CCD-3.2.a** — five waiver grounds, any one sufficient
- **FRD-2.4** — eight exclusions, any one sufficient
- **FRD-4.2** — six indicators, any two required, within a 30-day window
- **FRD-3.2** — three thresholds, any one sufficient
- **DBD-2.3.a/b/c** — mutually exclusive tiers keyed to notice timing

FRD-4.2 is the best test of applicability validation: "any two of six within 30 days" is a rule a model will happily satisfy with one indicator and a plausible-sounding second.

---

## 8. Suggested Golden-Set Scenarios

Starting points for a retrieval regression suite:

| # | Scenario | Should retrieve | Tests |
|---|---|---|---|
| 1 | Credit card claim, first notice 2024-11-15, provisional credit timing | CCD-4.2-v1 | Effective-date filter |
| 2 | Zelle imposter (other bank), send date 2025-11-20 | ZEL-2.2.a-v1 → not reimbursable | Date filter changing the outcome |
| 3 | Debit claim, account open 45 days, first notice 2025-08-01 | DBD-4.2 (30-day threshold — does not qualify) | Boundary + version |
| 4 | Same as #3 but first notice 2025-05-01 | DBD-4.2-v1 (60-day threshold — qualifies) | Same facts, opposite outcome |
| 5 | "Filing deadline for disputed transaction," no rail given | AMBIGUOUS — flag, don't close | Score margin |
| 6 | Wire transfer dispute window | Nothing above floor | Score floor / empty result |
| 7 | Consumer ACH claim on day 75 after statement | ACH-2.1 + adjudicator note | Regulation E claim survives closed network window |
| 8 | Zelle scam, consumer sent voluntarily | ZEL-1.2, ZEL-2.2, ZEL-2.2.a, ZEL-3.3 | Multi-hop completeness |
| 9 | Credit card claim, disputed $7,500, low fraud score | FRD-2.4 ground 1 — no automated determination | Exclusion overriding score band |
| 10 | Claim where 1 of 6 ATO indicators present | FRD-4.2 — threshold not met | Applicability validation |
| 11 | Sole proprietor debit account | DBD-9.1 — predominant purpose must be determined first | Precondition before applying a rule |
| 12 | Fourth claim in 10 months, no other indicators | FRD-3.2 → FRD-3.3 (review required, denial prohibited) | Review ≠ denial |

Scenarios 3 and 4 are the most valuable pair in the set: identical facts, different notice dates, opposite outcomes, driven entirely by which version of DBD-4.2 was in force.

---

## 9. Notes on Deliberate Design

A few things were built in on purpose that may look like drafting errors:

- **The adjudicator notes in CCD-2.1 and DBD-2.1** warn about each other. Real policy documents do this, and it gives your cross-reference extraction something to find.
- **ACH-2.1 contains two different deadlines** — the consumer's Regulation E claim right and the bank's network return right. Conflating them is a real and common error, and the note calls it out explicitly.
- **ZEL-4.1 states its own consequence** ("the most consequential error available in this policy"). Provisions occasionally editorialize; this tests whether your chunker keeps such framing with the operative text.
- **FRD-1.1 establishes a precedence rule** — rail-specific governs substance, FRD governs process. An agent that retrieves an FRD provision and a rail provision needs this to resolve the conflict.
- **FRD-8.1 describes your own agent's constraints.** The corpus contains the rule that an automated system may not deny on unresolved checks. Your agent retrieving and applying that provision to itself is a reasonable demo.
