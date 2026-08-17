import { useEffect, useState } from 'react';
import { submitClaim, listAccounts, listAccountTransactions } from '../api';

const REASONS = ['unauthorized_transaction', 'not_recognized', 'duplicate_charge', 'other'];

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
  const [reason, setReason] = useState(REASONS[0]);
  const [filedAt, setFiledAt] = useState(nowIso());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    listAccounts().then(setAccounts).catch((err) => setError(err.message));
  }, []);

  const knownAccount = accounts.some((a) => a.account_id === accountId);

  useEffect(() => {
    if (!knownAccount) {
      setTransactions([]);
      setTransactionId('');
      return;
    }
    let cancelled = false;
    listAccountTransactions(accountId)
      .then((txns) => {
        if (cancelled) return;
        setTransactions(txns);
        setTransactionId(txns[0]?.transaction_ref || '');
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
      <h2>Submit a claim</h2>

      <label>
        Claim type
        <select value={claimType} onChange={(e) => setClaimType(e.target.value)}>
          <option value="fraud">Fraud</option>
          <option value="billing_dispute">Billing dispute</option>
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
        Disputed transaction ID
        {knownAccount ? (
          <select value={transactionId} onChange={(e) => setTransactionId(e.target.value)} required>
            {transactions.length === 0 && <option value="">Loading transactions…</option>}
            {transactions.map((t) => (
              <option key={t.transaction_ref} value={t.transaction_ref}>{transactionLabel(t)}</option>
            ))}
          </select>
        ) : (
          <input
            value={transactionId}
            onChange={(e) => setTransactionId(e.target.value)}
            placeholder="TXN-7001"
            required
          />
        )}
      </label>

      <label>
        Reason
        <select value={reason} onChange={(e) => setReason(e.target.value)}>
          {REASONS.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </label>

      <label>
        Filed at
        <input value={filedAt} onChange={(e) => setFiledAt(e.target.value)} />
      </label>

      <button type="submit" disabled={submitting}>
        {submitting ? 'Submitting…' : 'Submit claim'}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
