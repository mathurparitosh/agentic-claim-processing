"""Claim taxonomy: required checks per claim type, and the deterministic decision rule.

See specs/technical.md §4 for the full check -> tool -> PASS/FAIL semantics. The
Approve/Deny/Inconclusive decision is always computed here from the check ledger,
never asserted by the model directly (requirements.md §6).
"""

REQUIRED_CHECKS = {
    "billing_dispute": [
        "transaction_exists",
        "duplicate_charge_check",
        "policy_dispute_window",
        "account_standing",
    ],
    "fraud": [
        "account_red_flags",
        "transaction_pattern_anomaly",
        "system_access_log_check",
        "policy_liability_rule",
    ],
}


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
