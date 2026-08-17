# Meridian Trust Bank — Zelle and Person-to-Person Transfer Claims Policy

**Document ID:** ZEL
**Document Title:** Person-to-Person Transfer Dispute and Fraud Claims Policy
**Issuing Body:** Disputes & Fraud Operations, Meridian Trust Bank
**Source Type:** internal_policy
**Corpus Snapshot:** 2026-07-01
**Jurisdiction:** US (federal); state supplements noted per provision

> *This is a synthetic policy document created for academic use. It does not describe any real financial institution and must not be relied upon for any operational purpose.*

---

## 1. Scope and Definitions

### ZEL-1.1 — Scope of This Policy

**Effective:** 2023-01-01 → present
**Applies to:** Consumer deposit accounts enrolled in the Zelle network through Meridian Trust
**Regulatory basis:** Regulation E, 12 CFR Part 1005; network participation rules
**Cross-references:** ZEL-8.1, DBD-1.1

This policy governs claims arising from person-to-person transfers sent or received through the Zelle network. It does not govern debit card transactions (DBD-1.1), ACH entries originated by a third party (ACH-1.1), or wire transfers, which are outside the scope of this corpus entirely.

### ZEL-1.2 — Authorized and Unauthorized Transfers Distinguished

**Effective:** 2023-01-01 → present
**Applies to:** All claims under this document
**Regulatory basis:** Regulation E §1005.2(m)
**Cross-references:** ZEL-2.1, ZEL-2.2

This distinction governs nearly every determination under this policy and must be resolved before any other analysis.

**Unauthorized transfer** means a transfer initiated by a person other than the consumer without actual authority. The consumer did not enter the transfer, did not approve it, and received no benefit from it.

**Authorized transfer induced by fraud** means a transfer the consumer personally initiated and approved, but did so because of a misrepresentation by another party. The consumer entered the recipient, the amount, and confirmed the send. These are commonly described as scams.

A transfer the consumer initiated is authorized for purposes of Regulation E even where the consumer was deceived about the recipient's identity or intentions. The consumer's regret, or the recipient's dishonesty, does not convert an authorized transfer into an unauthorized one.

---

## 2. Claim Categories and Filing

### ZEL-2.1 — Unauthorized Transfer Claims

**Effective:** 2023-01-01 → present
**Applies to:** Claims meeting the ZEL-1.2 definition of unauthorized transfer
**Regulatory basis:** Regulation E §1005.6, §1005.11
**Cross-references:** ZEL-1.2, ZEL-3.2, ZEL-4.1

Where a transfer is unauthorized under ZEL-1.2, the claim is governed by Regulation E error resolution. The consumer's liability is limited under the tiers described at DBD-2.3, applied to the P2P context, and Meridian Trust waives that liability in full for consumer accounts.

The determination that a transfer is unauthorized must rest on the device, session, and enrollment evidence obtained under ZEL-3.2, not on the consumer's characterization of the transfer.

### ZEL-2.2 — Authorized Transfers Induced by Fraud

**Effective:** 2023-01-01 → present
**Applies to:** Claims where the consumer initiated the transfer
**Cross-references:** ZEL-1.2, ZEL-2.2.a, ZEL-3.3

A transfer the consumer initiated and approved is not an error under Regulation E, and the bank has no reimbursement obligation under that regulation, even where the consumer was deceived.

Meridian Trust will attempt recovery under ZEL-3.3 in all such cases, and will reimburse the consumer where an exception under ZEL-2.2.a applies. Absent recovery or an applicable exception, the claim is denied under ZEL-7.1.

The adjudicator must not deny such a claim without first (a) attempting recall under ZEL-3.3 and (b) evaluating ZEL-2.2.a. A denial issued without both steps documented is a quality defect.

#### ZEL-2.2.a — Imposter Scam Reimbursement Exception

**Effective:** 2026-01-01 → present
**Supersedes:** ZEL-2.2.a-v1
**Applies to:** Authorized transfers under ZEL-2.2
**Conditions:** all four conditions below must be satisfied
**Cross-references:** ZEL-2.2, ZEL-6.1, FRD-6.1

Meridian Trust reimburses a consumer for an authorized transfer induced by fraud where **all** of the following are established:

1. The recipient impersonated a financial institution, a government agency, or a utility or service provider with which the consumer had an existing relationship;
2. The consumer reported the transfer within **60 calendar days** of the send date;
3. The consumer has not received reimbursement for more than one prior claim under this provision within the preceding **24 months** (see ZEL-6.1);
4. The claim file documents the impersonation, including the communication channel and, where available, the number or address from which contact originated.

Reimbursement under this provision requires approval under FRD-6.1. Purchase scams, investment scams, romance scams, and employment scams are outside this provision and are not reimbursable.

#### ZEL-2.2.a-v1 — Imposter Scam Reimbursement Exception *(superseded)*

**Effective:** 2024-08-01 → 2025-12-31
**Superseded by:** ZEL-2.2.a
**Status:** SUPERSEDED — applies only to claims whose send date falls on or before 2025-12-31

Meridian Trust reimburses a consumer for an authorized transfer induced by fraud where the recipient impersonated Meridian Trust Bank specifically, or an employee or agent of Meridian Trust Bank, and the consumer reported the transfer within **30 calendar days** of the send date.

Impersonation of other financial institutions, government agencies, or service providers is outside this provision.

### ZEL-2.3 — Filing Window

**Effective:** 2023-01-01 → present
**Applies to:** All claims under this document
**Regulatory basis:** Regulation E §1005.11(b)(1)
**Cross-references:** ZEL-2.2.a, DBD-2.1, ACH-2.1

A claim must be received no later than **60 calendar days** after the bank transmitted the periodic statement on which the transfer appeared.

For claims under ZEL-2.2.a, the shorter 60-day window measured from the **send date** governs, and applies whether or not a statement has been transmitted. Where both windows could apply, the earlier deadline controls.

---

## 3. Evidence and Recovery

### ZEL-3.1 — Enrollment and Token Verification

**Effective:** 2024-06-01 → present
**Applies to:** Unauthorized transfer claims under ZEL-2.1
**Cross-references:** ZEL-3.2, FRD-4.2

The claim file must record the enrollment history for the sending account, including the enrollment date, the email address or mobile number token used, and any token change within **90 days** before the disputed transfer.

A token change shortly before a disputed transfer, particularly one followed by a transfer to a newly added recipient, is a strong account takeover indicator and requires routing under FRD-4.2.

### ZEL-3.2 — Device and Session Evidence

**Effective:** 2024-06-01 → present
**Applies to:** Unauthorized transfer claims under ZEL-2.1
**Cross-references:** ZEL-2.1, FRD-4.2

The adjudicator must obtain the device identifier, IP address, geolocation, session authentication method, and device enrollment date for the session in which the disputed transfer was initiated.

Where the device matches a device the consumer has used for at least **30 days** preceding the transfer, and authentication succeeded through the consumer's registered biometric or passcode, the evidence weighs against a finding of unauthorized transfer — but does not alone establish authorization, because credential compromise and coercion both produce matching device evidence.

Where the device is unrecognized and enrolled within **7 days** before the transfer, the claim is presumptively unauthorized absent contrary evidence.

### ZEL-3.3 — Recipient Bank Recall Request

**Effective:** 2023-01-01 → present
**Applies to:** All claims where funds have been sent
**Cross-references:** ZEL-2.2, ZEL-5.2

Upon receipt of any claim, and before any determination, the bank must submit a recall request to the receiving institution through the network. The request must be submitted within **1 business day** of the date of first notice.

Recovery through recall is not guaranteed and depends on whether funds remain in the receiving account. Failure to recover does not determine the claim outcome; it determines only whether reimbursement, if owed, comes from recovered funds or from the bank.

The recall request date and the receiving institution's response must both be recorded in the claim file.

---

## 4. Provisional Credit

### ZEL-4.1 — Provisional Credit Applicability

**Effective:** 2024-02-01 → present
**Applies to:** Claims under ZEL-2.1 only
**Regulatory basis:** Regulation E §1005.11(c)(2)
**Cross-references:** ZEL-2.1, ZEL-2.2, DBD-4.1

Provisional credit obligations under Regulation E apply to unauthorized transfer claims under ZEL-2.1. Where the investigation will exceed **10 business days**, the bank must provisionally credit the account within that period.

Provisional credit does **not** apply to claims under ZEL-2.2, because an authorized transfer is not an error under Regulation E. Reimbursement under ZEL-2.2.a, where granted, is a final credit and not a provisional one.

Misclassification of a ZEL-2.2 claim as a ZEL-2.1 claim, or the reverse, is the most consequential error available in this policy. The adjudicator must resolve ZEL-1.2 before applying this provision.

---

## 5. Investigation Timeline

### ZEL-5.1 — Investigation Timeline

**Effective:** 2023-01-01 → present
**Applies to:** Claims under ZEL-2.1
**Regulatory basis:** Regulation E §1005.11(c)
**Cross-references:** ZEL-4.1, ZEL-5.2

The bank must investigate and determine whether an error occurred within **10 business days** of the date of first notice, or within **45 calendar days** where provisional credit has been issued under ZEL-4.1.

Claims under ZEL-2.2 are not subject to Regulation E investigation timelines but must be determined within **30 calendar days** as a matter of internal service standard.

### ZEL-5.2 — Recipient Institution Response Window

**Effective:** 2024-06-01 → present
**Applies to:** Claims where a recall was submitted under ZEL-3.3
**Cross-references:** ZEL-3.3, ZEL-5.1

The receiving institution is expected to respond to a recall request within **10 business days**. Where no response is received within that period, the adjudicator must proceed to determination on the available evidence.

The pendency of a recall request is not grounds for extending the timelines at ZEL-5.1. A claim may not be held open awaiting recovery.

---

## 6. Claimant History

### ZEL-6.1 — Repeat Claimant Review

**Effective:** 2025-04-01 → present
**Applies to:** Consumers filing multiple P2P claims
**Cross-references:** ZEL-2.2.a, FRD-3.2, FRD-3.3

Where a consumer has filed **three or more** P2P claims within a rolling 12-month period, or **two or more** claims reimbursed under ZEL-2.2.a within a rolling 24-month period, the claim must be routed to first-party fraud review under FRD-3.3 before determination.

Repeat filing is not itself evidence of first-party fraud. Victims of account takeover and of organized scam operations frequently file multiple legitimate claims. This provision requires review, not denial, and the reviewer must document affirmative indicators before any adverse inference is drawn.

---

## 7. Determinations and Notices

### ZEL-7.1 — Grounds for Denial

**Effective:** 2023-01-01 → present
**Applies to:** All P2P claims
**Cross-references:** ZEL-1.2, ZEL-2.2, ZEL-2.2.a, ZEL-7.2

A claim must be denied where documented evidence establishes any of the following:

1. The consumer initiated and approved the transfer, and no exception under ZEL-2.2.a applies;
2. The transfer was initiated by a person to whom the consumer furnished credentials, and the consumer had not notified the bank that transfers by that person were unauthorized;
3. The claim was received outside the window at ZEL-2.3;
4. The consumer received the goods, services, or benefit for which the transfer was sent;
5. The claim duplicates a previously adjudicated claim on the same transfer.

A denial under ground 1 requires that the recall attempt at ZEL-3.3 be documented and that ZEL-2.2.a be evaluated and found inapplicable, with the reason recorded.

### ZEL-7.2 — Notice Requirements

**Effective:** 2023-01-01 → present
**Applies to:** All denied P2P claims
**Cross-references:** ZEL-7.1, FRD-7.2

A written notice of denial must state the specific ground under ZEL-7.1 relied upon, identify the provision, and — where the denial rests on the transfer being authorized — explain the distinction at ZEL-1.2 in plain language.

The notice must inform the consumer of the right to request the documents relied upon and of the right to appeal within **30 calendar days**.

---

## 8. Exclusions

### ZEL-8.1 — Business Account Exclusion

**Effective:** 2023-01-01 → present
**Applies to:** P2P transfers on business or commercial deposit accounts
**Cross-references:** ZEL-1.1, DBD-9.1, CCD-9.1

Regulation E protections and the reimbursement provisions of this policy do not apply to transfers sent or received on accounts held for business purposes. Claims on business accounts are governed by the deposit agreement and network participation rules.
