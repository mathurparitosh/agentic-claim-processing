# Demo Test Cases

A compact demo script for the Claim Assistant. These scenarios use the existing synthetic
fixtures and cover approval, denial, human-in-the-loop resolution, and inconclusive
outcomes.

Prerequisites:

1. Load fixtures with `python -m backend.generate_synthetic_data`.
2. Start the application with `./scripts/start.sh`.
3. Open the Claims screen and use the account and transaction selectors.
4. Clear prior claims between runs if needed:
   `docker compose exec -T postgres psql -U postgres -d claims_dev -c 'DELETE FROM claims;'`

## Scenario List

| # | Account | Type | Reason | Transaction | Expected | Demo focus |
|---|---|---|---|---|---|---|
| 1 | `ACC-9001` | `Fraud` | `Unauthorized Transaction` | `TXN-7001` | **Approve** | Complete fraud investigation with anomalous transaction, risky access log, good standing, and policy evidence. |
| 2 | `ACC-9002` | `Billing Dispute` | `Duplicate Charge` | `TXN-2007` | **Approve** | Duplicate-charge computation finds the matching charge; all checks pass. |
| 3 | `ACC-9003` | `Fraud` | `Unauthorized Transaction` | `TXN-3007` | **Approve** | Independent approval case showing the result is reproducible across accounts. |
| 4 | `ACC-9004` | `Fraud` | `Unauthorized Transaction` | `TXN-4007` | **Deny** | Suspended account and existing fraud flags cause an immediate failed check. |
| 5 | `ACC-9005` | `Billing Dispute` | `Duplicate Charge` | `TXN-5007` | **Deny** | No matching duplicate exists within the 24-hour window, so the duplicate check fails. |
| 6 | `ACC-9006` | `Fraud` | `Not Recognized` | `TXN-6007` | **Approve after human answer** | Account profile is intentionally missing. Answer **yes** when asked whether the account is in good standing. |
| 7 | `ACC-9007` | `Billing Dispute` | `Duplicate Charge` | `TXN-7107` | **Deny after human answer** | A real duplicate exists, but the account profile is missing. Answer **no** to the account-standing question. |
| 8 | `ACC-9010` | `Fraud` | `Other` | `TXN-1007` | **Inconclusive** | Answer `not sure, can't confirm either way` each time. The unresolved account check forces Inconclusive. |

## What To Observe

For every case:

- The claim list header shows the Title Case type and reason, account ID, name, merchant,
  and amount.
- The individual claim summary shows the automatically captured filing time.
- The Checks tab shows the required checks and their final statuses.
- The Audit Trail shows retrieval, computation, human-answer, and determination events.

For scenarios 6 through 8:

- Enter the account ID manually because these accounts have no account profile and do not
  appear in the account autocomplete list.
- Because the account is not in the profile list, enter the transaction ID manually;
  the transaction panel is shown only after a known account is selected.
- Wait for the status to become `Awaiting input` before answering.
- Scenario 8 requires an ambiguous answer three times and should finish Inconclusive.

## Expected Coverage

- Approve: scenarios 1, 2, 3, and 6
- Deny: scenarios 4, 5, and 7
- Inconclusive: scenario 8
- Human-in-the-loop: scenarios 6, 7, and 8
- Billing dispute: scenarios 2, 5, and 7
- Fraud: scenarios 1, 3, 4, 6, and 8

## New Billing Reason Demonstration

The following Title Case reasons are configured and ready for a reason-specific evidence
workflow:

- `Merchandise/Services Not Received`
- `Not As Described Or Defective`
- `Cancelled Recurring Transaction`
- `Credit Not Processed`

The current synthetic schema does not include delivery, cancellation, quality, or refund
records. Submitting one of these reasons therefore demonstrates the corresponding
reason-specific check and human escalation rather than a straight-through approval.
