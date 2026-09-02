"""Claim taxonomy: required checks per claim type, and the deterministic decision rule.

See specs/technical.md §4 for the full check -> tool -> PASS/FAIL semantics. The
Approve/Deny/Inconclusive decision is always computed here from the check ledger,
never asserted by the model directly (requirements.md §6).
"""

COMMON_BILLING_CHECKS = [
    "transaction_exists",
    "policy_dispute_window",
    "account_standing",
]

BILLING_REASON_CHECKS = {
    "duplicate_charge": "duplicate_charge_check",
    "merchandise_services_not_received": "goods_services_delivery_check",
    "not_as_described_or_defective": "goods_services_quality_check",
    "cancelled_recurring_transaction": "recurring_cancellation_check",
    "credit_not_processed": "refund_credit_check",
}

CLAIM_TYPE_STORAGE = {
    "fraud": "Fraud",
    "billing_dispute": "Billing Dispute",
}

BILLING_REASON_STORAGE = {
    "unauthorized_transaction": "Unauthorized Transaction",
    "not_recognized": "Not Recognized",
    "duplicate_charge": "Duplicate Charge",
    "other": "Other",
    "merchandise_services_not_received": "Merchandise/Services Not Received",
    "not_as_described_or_defective": "Not As Described Or Defective",
    "cancelled_recurring_transaction": "Cancelled Recurring Transaction",
    "credit_not_processed": "Credit Not Processed",
}


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("/", " ").replace("_", " ").replace("-", " ")


def normalize_claim_type(value: str) -> str:
    normalized = _normalize_key(value)
    for key, label in CLAIM_TYPE_STORAGE.items():
        if normalized in (key.replace("_", " "), _normalize_key(label)):
            return key
    raise ValueError(f"Unknown claim_type: {value!r}")


def normalize_billing_reason(value: str) -> str:
    normalized = _normalize_key(value)
    for key, label in BILLING_REASON_STORAGE.items():
        if normalized in (key.replace("_", " "), _normalize_key(label)):
            return key
    raise ValueError(f"Unknown billing_dispute reason: {value!r}")


def storage_claim_type(value: str) -> str:
    return CLAIM_TYPE_STORAGE[normalize_claim_type(value)]


def storage_reason(value: str) -> str:
    return BILLING_REASON_STORAGE[normalize_billing_reason(value)]

REQUIRED_CHECKS = {
    "billing_dispute": COMMON_BILLING_CHECKS,
    "fraud": [
        "account_red_flags",
        "transaction_pattern_anomaly",
        "system_access_log_check",
        "policy_liability_rule",
    ],
}


def required_checks(claim_type: str, claim_payload: dict | None = None) -> list[str]:
    """Return the deterministic check profile for a claim and its submitted reason."""
    if claim_type != "billing_dispute":
        return list(REQUIRED_CHECKS[claim_type])

    reason = normalize_billing_reason((claim_payload or {}).get("reason", ""))
    reason_check = BILLING_REASON_CHECKS.get(reason)
    if reason_check is None:
        raise ValueError(f"Unknown billing_dispute reason: {reason!r}")
    return [*COMMON_BILLING_CHECKS, reason_check]


def compute_decision(checks: dict) -> tuple[str, str]:
    """Derive Approve/Deny/Inconclusive from check-ledger state.

    checks: {check_name: {"status": "PASS"|"FAIL"|"UNKNOWN"|"BLOCKED", "detail": ...}}
    """
    failed = sorted(name for name, c in checks.items() if c["status"] == "FAIL")
    if failed:
        return "deny", f"Required check(s) failed: {', '.join(failed)}"

    unresolved = sorted(name for name, c in checks.items() if c["status"] in ("UNKNOWN", "BLOCKED"))
    if not unresolved:
        return "approve", "All required checks passed"

    return "inconclusive", f"Required check(s) unresolved: {', '.join(unresolved)}"
