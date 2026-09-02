import { useEffect, useState } from 'react';
import { submitClaim, listAccounts, listAccountTransactions } from '../api';

const FRAUD_REASONS = [
  { value: 'Unauthorized Transaction', label: 'Unauthorized Transaction' },
  { value: 'Not Recognized', label: 'Not Recognized' },
  { value: 'Duplicate Charge', label: 'Duplicate Charge' },
  { value: 'Other', label: 'Other' },
];
const BILLING_DISPUTE_REASONS = [
  { value: 'Duplicate Charge', label: 'Duplicate Charge' },
  { value: 'Merchandise/Services Not Received', label: 'Merchandise/Services Not Received' },
  { value: 'Not As Described Or Defective', label: 'Not As Described Or Defective' },
  { value: 'Cancelled Recurring Transaction', label: 'Cancelled Recurring Transaction' },
  { value: 'Credit Not Processed', label: 'Credit Not Processed' },
];
const TRANSACTION_NOT_FOUND = 'transaction_not_found';

function nowIso() {
  return new Date().toISOString();
}

function transactionLabel(t) {
  const amount = Number(t.amount).toFixed(2);
  return `${t.transaction_ref} — $${amount} ${t.merchant || ''} (${t.location || 'unknown'})`;
}

export default function ClaimForm({ onSubmitted }) {
  const [claimType, setClaimType] = useState('fraud');
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState('');
  const [transactions, setTransactions] = useState([]);
  const [transactionId, setTransactionId] = useState('');
  const [reason, setReason] = useState(FRAUD_REASONS[0].value);
  const [filedAt, setFiledAt] = useState(nowIso());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    listAccounts().then(setAccounts).catch((err) => setError(err.message));
  }, []);

  const knownAccount = accounts.some((a) => a.account_id === accountId);
  const reasons = claimType === 'Billing Dispute' ? BILLING_DISPUTE_REASONS : FRAUD_REASONS;

  useEffect(() => {
    setReason(reasons[0].value);
  }, [claimType]);

  useEffect(() => {
    if (!knownAccount) {
      setTransactions([]);
      setTransactionId(TRANSACTION_NOT_FOUND);
      return;
    }
    let cancelled = false;
    listAccountTransactions(accountId)
      .then((txns) => {
        if (cancelled) return;
        setTransactions(txns);
        setTransactionId(txns[0]?.transaction_ref || TRANSACTION_NOT_FOUND);
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [accountId, knownAccount]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const result = await submitClaim(claimType, {
        account_id: accountId,
        disputed_transaction_id: transactionId,
        reason,
        filed_at: filedAt,
      });
      setAccountId('');
      setTransactionId('');
      setFiledAt(nowIso());
      onSubmitted(result.claim_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="claim-form" onSubmit={handleSubmit}>
      <div className="claim-form-layout">
        <div className="claim-form-fields">
          <h2>Submit a claim</h2>

          <label>
            Claim type
            <select value={claimType} onChange={(e) => setClaimType(e.target.value)}>
              <option value="Fraud">Fraud</option>
              <option value="Billing Dispute">Billing Dispute</option>
            </select>
          </label>

          <label>
            Account ID
            <input
              list="account-options"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              placeholder="Start typing an account ID…"
              autoComplete="off"
              required
            />
            <datalist id="account-options">
              {accounts.map((a) => (
                <option key={a.account_id} value={a.account_id}>{a.member_name}</option>
              ))}
            </datalist>
          </label>

          <label>
            Reason
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              {reasons.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </label>

          <button type="submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit claim'}
          </button>
          {error && <p className="error">{error}</p>}
        </div>

        {knownAccount && (
          <fieldset className="transaction-panel">
            <legend>Transactions</legend>
            {transactions.length === 0 && <p className="muted">No transactions found.</p>}
            {transactions.map((t) => (
              <label className="transaction-option" key={t.transaction_ref}>
                <input
                  type="radio"
                  name="disputed-transaction"
                  value={t.transaction_ref}
                  checked={transactionId === t.transaction_ref}
                  onChange={(e) => setTransactionId(e.target.value)}
                  required
                />
                <span>{transactionLabel(t)}</span>
              </label>
            ))}
            <label className="transaction-option">
              <input
                type="radio"
                name="disputed-transaction"
                value={TRANSACTION_NOT_FOUND}
                checked={transactionId === TRANSACTION_NOT_FOUND}
                onChange={(e) => setTransactionId(e.target.value)}
                required
              />
              <span>Transaction not found</span>
            </label>
          </fieldset>
        )}
      </div>
    </form>
  );
}
