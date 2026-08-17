# Meridian Trust Bank — ACH Dispute and Unauthorized Debit Claims Policy

**Document ID:** ACH
**Document Title:** ACH Dispute, Return, and Unauthorized Debit Adjudication Policy
**Issuing Body:** Payments Operations and Disputes & Fraud Operations, Meridian Trust Bank
**Source Type:** internal_policy incorporating network operating rules
**Corpus Snapshot:** 2026-07-01
**Jurisdiction:** US (federal); network rules as adopted

> *This is a synthetic policy document created for academic use. It does not describe any real financial institution and must not be relied upon for any operational purpose.*

---

## 1. Scope and Definitions

### ACH-1.1 — Scope of This Policy

**Effective:** 2023-01-01 → present
**Applies to:** ACH debit and credit entries posted to accounts at Meridian Trust
**Regulatory basis:** Regulation E, 12 CFR Part 1005; Nacha Operating Rules
**Cross-references:** ACH-9.1, DBD-1.1, ZEL-1.1

This policy governs claims arising from ACH entries where Meridian Trust acts as the Receiving Depository Financial Institution. It does not govern card transactions (CCD-1.1, DBD-1.1) or P2P transfers through the Zelle network (ZEL-1.1). Where an entry was originated by Meridian Trust as ODFI, this policy governs only the receiving-side claim.

### ACH-1.2 — Definitions

**Effective:** 2023-01-01 → present
**Applies to:** All provisions of this document

**Unauthorized entry** means a debit entry to a consumer account that was not authorized by the receiver, or for which the authorization was revoked before the entry was initiated.

**Improperly originated entry** means an entry that was authorized in principle but was originated in a manner inconsistent with the terms of the authorization — for example, in a different amount, on a different date, or with a different frequency than authorized.

**WSUD** means a Written Statement of Unauthorized Debit, the receiver's signed or similarly authenticated attestation required by network rules for certain returns.

**Settlement date** means the date on which the entry posted to the receiver's account, not the effective entry date carried in the entry detail record.

**Consumer account** means an account held by a natural person primarily for personal, family, or household purposes.

---

## 2. Claim Windows

### ACH-2.1 — Consumer Unauthorized Debit Window

**Effective:** 2023-01-01 → present
**Applies to:** Consumer accounts; unauthorized entries under ACH-1.2
**Regulatory basis:** Regulation E §1005.11(b)(1); Nacha Operating Rules
**Cross-references:** ACH-2.2, ACH-2.3, DBD-2.1, ZEL-2.3

A consumer must notify the bank of an unauthorized ACH debit no later than **60 calendar days** after the bank transmitted the periodic statement on which the entry first appeared.

The bank's ability to return the entry through the network is governed by a separate and shorter deadline: a consumer return must be transmitted by the RDFI by the opening of business on the **banking day following the sixtieth calendar day** after the settlement date of the entry.

> **Adjudicator note:** the consumer's claim right under Regulation E and the bank's return right under network rules are distinct. A claim may remain valid under Regulation E after the network return window has closed. In that case the bank must still make the consumer whole and pursue recovery outside the return process. Do not deny a timely Regulation E claim on the ground that the network return window expired.

### ACH-2.2 — Written Statement of Unauthorized Debit

**Effective:** 2023-01-01 → present
**Applies to:** Consumer unauthorized entry claims proceeding to return
**Regulatory basis:** Nacha Operating Rules
**Cross-references:** ACH-2.2.a, ACH-3.2

A WSUD must be obtained from the receiver before an entry may be returned as unauthorized under the applicable return reason code. The WSUD must state that the entry was not authorized, or that authorization was revoked, and must be dated on or after the settlement date of the entry.

A WSUD dated before the settlement date is invalid and must be re-obtained. The absence of a valid WSUD prevents the network return; it does not prevent the Regulation E claim from proceeding under ACH-2.1.

#### ACH-2.2.a — WSUD Form and Timing

**Effective:** 2024-03-01 → present
**Applies to:** WSUD collection under ACH-2.2
**Conditions:** consumer accounts only

The WSUD may be obtained in writing or in a similarly authenticated electronic form, including a recorded telephone attestation where the recording captures the required elements and the receiver's identity is verified.

The WSUD must be obtained before the return is transmitted. Where the receiver has provided oral notice but the WSUD is pending, the adjudicator may transmit the return only where the WSUD is obtained within the same banking day. Transmitting a return in anticipation of a WSUD is prohibited.

### ACH-2.3 — Business Account Return Window

**Effective:** 2023-01-01 → present
**Applies to:** Non-consumer accounts
**Regulatory basis:** Nacha Operating Rules
**Cross-references:** ACH-2.1, ACH-9.1

For entries posted to non-consumer accounts, the return must be transmitted by the RDFI by the opening of business on the **second banking day** following the settlement date.

This window is not extendable. Where a business receiver reports an unauthorized entry after the window has closed, the claim is outside the return process entirely, and recovery must be pursued directly with the originator under ACH-5.2.

---

## 3. Return Reason Codes

### ACH-3.1 — Return Reason Code Selection

**Effective:** 2024-01-01 → present
**Applies to:** All entries being returned
**Source type:** internal_policy incorporating network rules
**Cross-references:** ACH-3.2, ACH-6.1

The adjudicator must select the return reason code that most specifically describes the documented facts. Where more than one code could apply, the more specific code governs.

The selected code must be supported by the evidence in the claim file. Selecting a code the evidence does not support exposes the bank to a rules violation and to reversal of the return, and is a documented quality defect.

### ACH-3.2 — Unauthorized Versus Revoked Authorization

**Effective:** 2024-01-01 → present
**Applies to:** Consumer claims where authorization is at issue
**Cross-references:** ACH-2.2, ACH-6.1, ACH-6.3

Two distinct categories must not be conflated:

**Never authorized.** The receiver never granted authorization to the originator for any entry. This category supports the unauthorized return codes and requires a WSUD under ACH-2.2.

**Authorization revoked.** The receiver granted authorization, subsequently revoked it directly with the originator, and the originator debited the account thereafter. This category is governed by ACH-6.1 and requires evidence of the revocation, not merely the receiver's assertion of it.

An entry posted **before** a documented revocation date is neither unauthorized nor revoked, and is not returnable on either ground. The adjudicator must establish the revocation date before selecting a code.

---

## 4. Provisional Credit

### ACH-4.1 — Provisional Credit for Consumer Claims

**Effective:** 2023-01-01 → present
**Applies to:** Consumer unauthorized entry claims under ACH-2.1
**Regulatory basis:** Regulation E §1005.11(c)(2)
**Cross-references:** ACH-2.1, ACH-5.1, DBD-4.1

Where the investigation of a consumer claim will exceed **10 business days** from the date of first notice, the bank must provisionally credit the account for the full disputed amount within that period.

Recovery of funds through a network return is not a condition of provisional credit. The obligation to the consumer runs independently of whether the return succeeds.

Provisional credit obligations do not apply to non-consumer accounts under ACH-9.1.

---

## 5. Investigation

### ACH-5.1 — Investigation Timeline

**Effective:** 2023-01-01 → present
**Applies to:** Consumer claims under ACH-2.1
**Regulatory basis:** Regulation E §1005.11(c)
**Cross-references:** ACH-4.1, ACH-5.2

The bank must investigate and determine whether an error occurred within **10 business days** of the date of first notice, or within **45 calendar days** where provisional credit has been issued under ACH-4.1.

Where the entry was initiated outside a state, the extended period at DBD-4.3 applies by analogy, and the investigation period is **90 calendar days**.

### ACH-5.2 — Originator Contact

**Effective:** 2024-07-01 → present
**Applies to:** Claims of improperly originated or revoked-authorization entries
**Cross-references:** ACH-6.1, ACH-6.2

For claims under ACH-6.1 or ACH-6.2, the adjudicator must request the originator's authorization record through the ODFI before determining the claim. The request and any response must be recorded in the claim file.

Where the ODFI does not produce an authorization record within **10 banking days**, the absence of a record weighs in the receiver's favor. The originator bears the burden of evidencing authorization; the receiver does not bear the burden of disproving it.

---

## 6. Authorization Issues

### ACH-6.1 — Revoked Authorization Claims

**Effective:** 2024-01-01 → present
**Applies to:** Claims that authorization was revoked before the entry
**Cross-references:** ACH-3.2, ACH-5.2, ACH-6.3, CCD-8.1, DBD-8.1

The claim file must document the revocation date, the method, and the party to whom revocation was communicated. Revocation communicated to the bank alone, without communication to the originator, does not revoke the originator's authorization — it operates as a stop payment request under ACH-6.3 instead.

Entries posted after a documented revocation are returnable. Entries posted before it are not, and a claim seeking return of pre-revocation entries must be denied under ACH-7.1 as to those entries, while proceeding as to entries after the revocation date.

### ACH-6.2 — Improperly Originated Entries

**Effective:** 2024-01-01 → present
**Applies to:** Entries inconsistent with the terms of a valid authorization
**Cross-references:** ACH-1.2, ACH-5.2

Where the receiver authorized entries in a specific amount, on a specific date, or at a specific frequency, and the originator debited in a different amount, on a different date, or at a different frequency, the entry is improperly originated and returnable.

The claim file must contain the terms of the authorization and the actual entry detail, and must identify the specific variance. A claim asserting only that the amount was "wrong," without the authorized amount established, is incomplete under ACH-7.1 and must be returned for completion rather than denied.

### ACH-6.3 — Stop Payment Orders

**Effective:** 2023-01-01 → present
**Applies to:** Receiver requests to block future entries
**Regulatory basis:** Regulation E §1005.10(c)
**Cross-references:** ACH-6.1, ACH-8.1

A receiver may order the bank to stop payment of a preauthorized recurring entry by notifying the bank at least **3 business days** before the scheduled date. Oral orders may be honored, and the bank may require written confirmation within **14 days** of an oral order.

A stop payment order is prospective. It does not create a claim for entries already posted, which remain governed by ACH-2.1 and ACH-6.1.

---

## 7. Determinations

### ACH-7.1 — Grounds for Denial

**Effective:** 2023-01-01 → present
**Applies to:** All ACH claims
**Cross-references:** ACH-2.1, ACH-6.1, ACH-7.2

A claim must be denied where documented evidence establishes any of the following:

1. The originator holds a valid authorization covering the entry, and the entry conforms to its terms;
2. The entry posted before the documented revocation date under ACH-6.1;
3. The claim was received outside the window at ACH-2.1 and the account is a consumer account, or outside ACH-2.3 for a non-consumer account;
4. The receiver received the benefit of the entry;
5. The claim duplicates a previously adjudicated claim on the same entry.

Where the ODFI fails to produce an authorization record under ACH-5.2, ground 1 is not established and may not be used as a basis for denial.

### ACH-7.2 — Notice Requirements

**Effective:** 2023-01-01 → present
**Applies to:** All denied consumer ACH claims
**Regulatory basis:** Regulation E §1005.11(d)
**Cross-references:** ACH-7.1, FRD-7.2

Written notice of an adverse determination must be transmitted within **3 business days** of concluding the investigation, must state the specific ground and provision relied upon, and must inform the receiver of the right to request the documents relied upon.

Where the denial rests on an authorization record produced by the originator, that record must be among the documents available on request.

---

## 8. Recurring Entries

### ACH-8.1 — Recurring Debit Entries

**Effective:** 2024-04-01 → present
**Applies to:** Preauthorized recurring ACH debits on consumer accounts
**Regulatory basis:** Regulation E §1005.10
**Cross-references:** ACH-6.1, ACH-6.3, CCD-8.1, DBD-8.1

Where a preauthorized recurring entry varies in amount from the previous entry, the originator must have provided the receiver notice of the amount at least **10 days** before the scheduled date, unless the receiver elected to receive notice only when the amount falls outside a specified range.

Failure to provide required notice makes the entry improperly originated under ACH-6.2. The claim file must record whether notice was provided and on what date.

---

## 9. Special Cases and Exclusions

### ACH-9.1 — Non-Consumer Account Exclusion

**Effective:** 2023-01-01 → present
**Applies to:** Business, corporate, and other non-consumer accounts
**Cross-references:** ACH-2.3, ACH-4.1, CCD-9.1, DBD-9.1

Regulation E protections, including the claim window at ACH-2.1 and the provisional credit obligation at ACH-4.1, do not apply to non-consumer accounts. Such claims are governed by the deposit agreement, the network rules, and the return window at ACH-2.3.

Where an account is held by a sole proprietor, the adjudicator must determine the predominant purpose before applying this exclusion and must record the basis for that determination.

### ACH-9.2 — Same-Day ACH Entries

**Effective:** 2025-02-01 → present
**Applies to:** Entries processed through same-day settlement
**Cross-references:** ACH-2.1, ACH-2.3

Same-day settlement does not alter the claim windows at ACH-2.1 or ACH-2.3, both of which run from the settlement date. It does compress the practical window for recovery, because funds are typically available to the originator sooner.

Claims involving same-day entries in amounts exceeding **$25,000** must be routed for expedited review within **1 business day** of the date of first notice, given the reduced likelihood of recovery after that point.
