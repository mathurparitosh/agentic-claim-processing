# Meridian Trust Bank — Fraud Investigation and Claims Governance Policy

**Document ID:** FRD
**Document Title:** Cross-Rail Fraud Investigation, Scoring, and Claims Governance Policy
**Issuing Body:** Financial Crimes and Disputes & Fraud Operations, Meridian Trust Bank
**Source Type:** internal_policy
**Corpus Snapshot:** 2026-07-01
**Jurisdiction:** US (federal)

> *This is a synthetic policy document created for academic use. It does not describe any real financial institution and must not be relied upon for any operational purpose.*

---

## 1. Scope

### FRD-1.1 — Scope of This Policy

**Effective:** 2023-01-01 → present
**Applies to:** All dispute and fraud claims across all payment rails
**Cross-references:** CCD-1.1, DBD-1.1, ZEL-1.1, ACH-1.1

This policy applies across all payment rails and supplements the rail-specific policies. Where a rail-specific provision and a provision of this policy both apply, **the rail-specific provision governs the substance of the determination** and this policy governs the process, controls, and escalation.

Where a rail-specific policy is silent on a matter addressed here, this policy governs.

### FRD-1.2 — Fraud and Dispute Claims Distinguished

**Effective:** 2023-01-01 → present
**Applies to:** Claim intake and routing across all rails
**Cross-references:** CCD-1.2, DBD-1.2, ZEL-1.2

**Third-party fraud** means a transaction initiated by a person other than the accountholder, without authority. The accountholder is a victim.

**First-party fraud** means a claim filed by the accountholder asserting fraud where the accountholder in fact initiated or benefited from the transaction. The accountholder is the perpetrator.

**Merchant or service dispute** means a transaction the accountholder initiated where the dispute concerns delivery, quality, or terms rather than authorization.

Initial classification is provisional and must be revisited as evidence develops. A claim classified as third-party fraud at intake that develops first-party indicators must be reclassified and routed under FRD-3.3, not silently determined under the original classification.

---

## 2. Fraud Scoring

### FRD-2.1 — Fraud Score Bands

**Effective:** 2025-01-01 → present
**Applies to:** All claims scored by the fraud risk model
**Cross-references:** FRD-2.2, FRD-2.3, FRD-2.4

Claims receive a fraud risk score from 0 to 1000 at intake. The bands are:

| Band | Score | Meaning |
|---|---|---|
| Low | 0–299 | Claim consistent with third-party fraud; no elevated risk indicators |
| Moderate | 300–599 | Some indicators present; standard review |
| Elevated | 600–799 | Multiple indicators; enhanced review required |
| High | 800–1000 | Strong indicators of first-party fraud or organized activity |

The score is an input to the determination, not a determination. No claim may be approved or denied on the score alone. See FRD-8.2.

### FRD-2.2 — Score-Based Routing

**Effective:** 2025-01-01 → present
**Applies to:** All scored claims
**Cross-references:** FRD-2.1, FRD-2.4, FRD-6.1

Routing by band:

- **Low (0–299)** — eligible for automated determination where no exclusion at FRD-2.4 applies
- **Moderate (300–599)** — standard adjudication; automated determination permitted for approvals only
- **Elevated (600–799)** — mandatory human review under FRD-6.1 before any determination
- **High (800–1000)** — mandatory human review and first-party fraud assessment under FRD-3.3

A claim may be escalated to a higher-touch path at the adjudicator's discretion. A claim may **not** be routed to a lower-touch path than its band requires.

### FRD-2.3 — Score Override

**Effective:** 2025-01-01 → present
**Applies to:** Requests to route a claim below its band requirement
**Cross-references:** FRD-2.2, FRD-6.2

A score-based routing requirement may be overridden downward only with dual approval under FRD-6.2, and only where the claim file documents the specific factual basis on which the score is believed to overstate risk.

Overrides must be logged with the approver identities, the original score, and the basis. Override frequency is reported monthly to the Disputes Governance Committee. A pattern of overrides on a single score driver is treated as a model defect and referred for model review, not as a run of individual judgment calls.

### FRD-2.4 — Exclusions from Automated Determination

**Effective:** 2025-01-01 → present
**Applies to:** All claims otherwise eligible for automated determination
**Cross-references:** FRD-2.2, FRD-6.1, FRD-8.1

A claim is excluded from automated determination, regardless of score, where any of the following applies:

1. The disputed amount exceeds **$5,000**;
2. The claim would result in a denial and the account holder is flagged as a vulnerable adult under FRD-9.1;
3. The claim involves a deceased accountholder;
4. The account is subject to an active law enforcement hold or legal process;
5. The claim is the third or subsequent claim by the same accountholder within a rolling 12-month period;
6. The determination would rest on a policy provision not previously used to determine a claim of that type;
7. The claim involves a suspected account takeover under FRD-4.2;
8. The claim is part of a merchant-level or originator-level fraud event under active investigation.

Ground 6 exists because a novel provision applied without human review is the most common route to a well-reasoned but incorrect determination.

---

## 3. Claimant History and First-Party Fraud

### FRD-3.1 — Customer History Review

**Effective:** 2024-01-01 → present
**Applies to:** All claims
**Cross-references:** FRD-3.2, FRD-3.3

The adjudicator must review the accountholder's prior claim history across all rails before determining a claim. The review must cover the preceding **24 months** and must record, in the claim file, the number of prior claims, their outcomes, and any pattern observed.

Absence of prior claims is a neutral fact. Presence of prior claims is a neutral fact absent a documented pattern. Neither supports an inference on its own.

### FRD-3.2 — Repeat Claimant Thresholds

**Effective:** 2025-04-01 → present
**Applies to:** Accountholders with multiple claims
**Cross-references:** FRD-3.1, FRD-3.3, ZEL-6.1

Enhanced review under FRD-3.3 is required where the accountholder has:

- **Four or more** claims of any type within a rolling 12-month period; or
- **Three or more** claims within a rolling 12-month period where the aggregate disputed amount exceeds **$10,000**; or
- **Two or more** claims within a rolling 24-month period reimbursed under ZEL-2.2.a.

Meeting a threshold requires review. It does not support denial, and a denial resting on claim frequency alone is prohibited under FRD-3.3.

### FRD-3.3 — First-Party Fraud Assessment

**Effective:** 2024-01-01 → present
**Applies to:** Claims routed for first-party fraud review
**Cross-references:** FRD-2.2, FRD-3.2, FRD-6.1, FRD-6.2

A determination of first-party fraud requires **affirmative documented evidence**, which may include: device and session evidence placing the accountholder at the transaction; delivery confirmation to the accountholder's address; recovery of the disputed goods; a documented admission; or benefit to the accountholder traced through account activity.

The following do **not**, individually or in combination, constitute evidence of first-party fraud:

- Claim frequency alone;
- A high fraud score alone;
- The accountholder's inability to explain how a credential was compromised;
- Inconsistency in the accountholder's account of events, absent other evidence, since trauma and elapsed time both produce inconsistency in truthful accounts.

A first-party fraud determination requires dual approval under FRD-6.2 and must identify the specific affirmative evidence relied upon.

---

## 4. Identity and Account Takeover

### FRD-4.1 — Claimant Identity Verification

**Effective:** 2023-01-01 → present
**Applies to:** All claims at intake
**Cross-references:** FRD-4.2

The claimant's identity must be verified before a claim is opened, using a method independent of any credential that may itself be compromised. Where account takeover is suspected under FRD-4.2, verification must not rely on the account's registered phone number or email address, as those are commonly the first assets an attacker changes.

### FRD-4.2 — Account Takeover Indicators

**Effective:** 2024-06-01 → present
**Applies to:** All claims
**Cross-references:** FRD-2.4, FRD-4.1, CCD-8.2, ZEL-3.1, ZEL-3.2, DBD-6.2

A claim must be routed as suspected account takeover where any two of the following are present within **30 days** before the first disputed transaction:

1. Change to the registered phone number or email address;
2. Password or credential reset from an unrecognized device;
3. New device enrollment followed within 72 hours by a transfer or high-value transaction;
4. Login from a geolocation inconsistent with the accountholder's established pattern;
5. Disablement of alerts or notifications;
6. Addition of a new payee, recipient token, or external account.

Account takeover claims are excluded from automated determination under FRD-2.4 and require review of the full credential change history, not only the disputed transaction.

An account takeover finding does not require identifying how the compromise occurred. The accountholder's inability to explain the compromise is not evidence against the claim.

---

## 5. Regulatory Referral

### FRD-5.1 — Suspicious Activity Referral Triggers

**Effective:** 2023-01-01 → present
**Applies to:** All claims
**Cross-references:** FRD-5.2, FRD-3.3

The adjudicator must refer a claim to Financial Crimes for suspicious activity evaluation where the claim involves: suspected first-party fraud under FRD-3.3; an aggregate disputed amount exceeding **$5,000** with indicators of organized activity; a pattern involving multiple accountholders and a common counterparty; or suspected elder financial exploitation under FRD-9.1.

Referral is a separate obligation from the claim determination. **The claim determination must proceed on its own timeline and may not be delayed pending the referral outcome.**

### FRD-5.2 — Referral Confidentiality

**Effective:** 2023-01-01 → present
**Applies to:** All referrals under FRD-5.1
**Cross-references:** FRD-5.1, FRD-7.2

The existence and content of a suspicious activity referral are confidential and must not be disclosed to the accountholder, to any party outside the authorized internal group, or in any notice issued under a rail-specific notice provision.

An adverse determination notice must state the policy ground for the determination without reference to any referral. Where the only articulable ground would disclose a referral, the adjudicator must consult Financial Crimes before issuing the notice.

---

## 6. Human Review and Approval

### FRD-6.1 — Mandatory Human Review

**Effective:** 2025-01-01 → present
**Applies to:** Claims meeting any listed condition
**Cross-references:** FRD-2.2, FRD-2.4, FRD-6.2, FRD-8.1

Human review before determination is mandatory where the claim: falls in the elevated or high score bands under FRD-2.2; is excluded from automated determination under FRD-2.4; would be reimbursed under ZEL-2.2.a; involves an extension request beyond 120 days under DBD-2.2; or involves provisional credit on a claim of unauthorized use filed more than 180 days after posting under CCD-2.2.

The reviewer must record the evidence reviewed and the basis for concurrence or override. A review recorded only as "reviewed and agreed" does not satisfy this provision.

### FRD-6.2 — Dual Approval Requirements

**Effective:** 2024-01-01 → present
**Applies to:** Enumerated high-consequence actions
**Cross-references:** FRD-2.3, FRD-3.3, CCD-6.3

Two approvers, neither of whom adjudicated the claim, are required for: a first-party fraud determination under FRD-3.3; a downward score override under FRD-2.3; initiation of pre-arbitration under CCD-6.3; any determination on a claim exceeding **$25,000**; and any reversal of a previously issued final credit.

Both approver identities and the time of each approval must be recorded.

---

## 7. Evidence and Audit

### FRD-7.1 — Evidence Retention

**Effective:** 2023-01-01 → present
**Applies to:** All claim files
**Cross-references:** CCD-3.1, DBD-3.1, FRD-7.2

The complete claim file, including all evidence obtained, all evidence requested but not obtained, and the determination and its basis, must be retained for **7 years** from the date of final determination.

Evidence requested but not obtained must be recorded with the request date and the reason it was not obtained. A file that shows only the evidence relied upon, without the gaps, does not permit an auditor to assess whether the investigation was adequate.

### FRD-7.2 — Audit Trail Requirements

**Effective:** 2025-01-01 → present
**Applies to:** All claims, including automated determinations
**Cross-references:** FRD-7.1, FRD-8.2, CCD-7.2, DBD-7.2, ZEL-7.2, ACH-7.2

The audit trail for every claim must record, in sequence: each investigative step taken and its result; each policy provision consulted, including the version and effective date of the provision as applied; each provision relied upon in the determination, with the specific text supporting the conclusion; every request for information made to any internal or external party, with dates; and the identity of every human who reviewed or approved any part of the determination.

Where a determination relied on a retrieved policy provision, the trail must record **which version of that provision was applied and the date basis for selecting that version.** A trail that cites a provision without its version does not permit the determination to be reproduced and is deficient.

The audit trail is append-only. Corrections are recorded as additional entries; existing entries are never modified or deleted.

---

## 8. Automated Decisioning

### FRD-8.1 — Limits on Automated Determination

**Effective:** 2026-01-01 → present
**Supersedes:** FRD-8.1-v1
**Applies to:** All automated or model-assisted determinations
**Cross-references:** FRD-2.2, FRD-2.4, FRD-6.1, FRD-8.2

An automated determination may be issued only where: the claim is in the low or moderate score band; no exclusion under FRD-2.4 applies; and every required check has been resolved against documented evidence.

**An automated system may not issue a denial where any required check remains unresolved.** Where a check cannot be resolved on available evidence, the claim must be routed to human review with the unresolved check identified and the evidence gathered to date preserved. Routing an unresolved claim to a human is the correct outcome and is not a system failure.

An automated system may not treat the absence of evidence as evidence. A check that cannot be resolved is unresolved; it is not a failed check.

### FRD-8.1-v1 — Limits on Automated Determination *(superseded)*

**Effective:** 2025-01-01 → 2025-12-31
**Superseded by:** FRD-8.1
**Status:** SUPERSEDED — applies only to claims determined on or before 2025-12-31

An automated determination may be issued only where the claim is in the low score band and the disputed amount does not exceed **$1,000**. Automated denials are prohibited in all cases; automated approvals only are permitted.

### FRD-8.2 — Disclosure of Model-Assisted Determination

**Effective:** 2026-01-01 → present
**Applies to:** Determinations informed by a fraud model or automated system
**Cross-references:** FRD-2.1, FRD-8.1, FRD-7.2

Where a determination was informed by a fraud risk score or an automated system, the claim file must record that fact, the model version, and the score. The adverse determination notice must state the substantive policy ground for the determination; a score is not a ground and may not be cited as one.

A notice stating that a claim was denied because of a risk score does not satisfy the notice requirements at CCD-7.2, DBD-7.2, ZEL-7.2, or ACH-7.2, each of which requires the specific policy provision relied upon.

---

## 9. Vulnerable Accountholders

### FRD-9.1 — Vulnerable Adult and Deceased Accountholder Claims

**Effective:** 2024-10-01 → present
**Applies to:** Claims involving accountholders aged 65 or older, accountholders with a documented conservatorship or power of attorney, and deceased accountholders
**Cross-references:** FRD-2.4, FRD-5.1, FRD-6.1

Claims in this category are excluded from automated determination under FRD-2.4 and require human review under FRD-6.1.

Where elder financial exploitation is suspected, the adjudicator must refer to Financial Crimes under FRD-5.1 and must not contact any party identified as a suspected exploiter, including a family member or caregiver holding a power of attorney, without Financial Crimes concurrence.

For claims on deceased accountholder accounts, the adjudicator must verify the authority of the person filing before proceeding, and must not disclose transaction detail to a person whose authority is not established.
