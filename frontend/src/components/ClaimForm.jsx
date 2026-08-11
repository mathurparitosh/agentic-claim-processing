import { useState } from 'react';
import { submitClaim } from '../api';

const REASONS = ['unauthorized_transaction', 'not_recognized', 'duplicate_charge', 'other'];

function nowIso() {
  return new Date().toISOString();
}

export default function ClaimForm({ onSubmitted }) {
  const [claimType, setClaimType] = useState('fraud');
  const [accountId, setAccountId] = useState('');
  const [transactionId, setTransactionId] = useState('');
  const [reason, setReason] = useState(REASONS[0]);
  const [filedAt, setFiledAt] = useState(nowIso());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

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
        <input value={accountId} onChange={(e) => setAccountId(e.target.value)} placeholder="ACC-9001" required />
      </label>

      <label>
        Disputed transaction ID
        <input value={transactionId} onChange={(e) => setTransactionId(e.target.value)} placeholder="TXN-7001" required />
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
