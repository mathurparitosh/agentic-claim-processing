import { useEffect, useState } from 'react';
import { listClaims } from '../api';

const POLL_MS = 3000;
const ACTIVE_STATUSES = new Set(['pending', 'processing', 'awaiting_input']);

const STATUS_LABELS = {
  pending: 'Pending',
  processing: 'Processing',
  awaiting_input: 'Awaiting input',
  completed: 'Completed',
};

export default function ClaimList({ selectedClaimId, onSelect, refreshToken }) {
  const [claims, setClaims] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const data = await listClaims();
        if (!cancelled) {
          setClaims(data);
          setError('');
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [refreshToken]);

  return (
    <div className="claim-list">
      <h2>Claims</h2>
      {error && <p className="error">{error}</p>}
      {claims.length === 0 && <p className="muted">No claims yet.</p>}
      <ul>
        {claims.map((c) => (
          <li
            key={c.id}
            className={c.id === selectedClaimId ? 'selected' : ''}
            onClick={() => onSelect(c.id)}
          >
            <div className="claim-list-row">
              <span className="claim-type">{c.claim_type}</span>
              <span className={`status-badge status-${c.status}`}>
                {STATUS_LABELS[c.status] || c.status}
                {ACTIVE_STATUSES.has(c.status) && <span className="pulse" />}
              </span>
            </div>
            {c.decision && <div className={`decision-badge decision-${c.decision}`}>{c.decision}</div>}
            <div className="claim-id">{c.id}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
