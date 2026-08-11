import { useEffect, useState } from 'react';
import { getClaim, answerQuestion } from '../api';

const POLL_MS = 2000;
const ACTIVE_STATUSES = new Set(['pending', 'processing', 'awaiting_input']);

const DECISION_LABELS = {
  approve: 'Approved',
  deny: 'Denied',
  inconclusive: 'Inconclusive',
};

function CheckRow({ check }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className={`check-row check-${check.check_status}`}>
      <button type="button" className="check-summary" onClick={() => setExpanded((e) => !e)}>
        <span className="check-name">{check.check_name}</span>
        <span className={`check-status status-pill status-${check.check_status}`}>{check.check_status}</span>
      </button>
      {expanded && check.detail && (
        <pre className="check-detail">{JSON.stringify(check.detail, null, 2)}</pre>
      )}
    </li>
  );
}

export default function ClaimDetail({ claimId, onAnswered }) {
  const [claim, setClaim] = useState(null);
  const [error, setError] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [answering, setAnswering] = useState(false);

  useEffect(() => {
    if (!claimId) return;
    let cancelled = false;
    let timer;

    async function poll() {
      try {
        const data = await getClaim(claimId);
        if (cancelled) return;
        setClaim(data);
        setError('');
        if (ACTIVE_STATUSES.has(data.status)) {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [claimId]);

  async function submitAnswer(answer) {
    setAnswering(true);
    setError('');
    try {
      await answerQuestion(claimId, answer);
      setAnswerText('');
      const data = await getClaim(claimId);
      setClaim(data);
      onAnswered?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setAnswering(false);
    }
  }

  if (!claimId) {
    return <div className="claim-detail muted">Select a claim to view details.</div>;
  }
  if (error && !claim) {
    return <div className="claim-detail error">{error}</div>;
  }
  if (!claim) {
    return <div className="claim-detail muted">Loading…</div>;
  }

  return (
    <div className="claim-detail">
      <h2>Claim detail</h2>
      <div className="claim-meta">
        <div><span className="label">ID</span> {claim.id}</div>
        <div><span className="label">Type</span> {claim.claim_type}</div>
        <div><span className="label">Status</span> <span className={`status-badge status-${claim.status}`}>{claim.status}</span></div>
        <div><span className="label">Submitted</span> {new Date(claim.submitted_at).toLocaleString()}</div>
      </div>

      {claim.status === 'awaiting_input' && claim.pending_question && (
        <div className="question-box">
          <h3>The agent needs input</h3>
          <p className="question-text">{claim.pending_question.question}</p>
          <p className="muted">Resolving check: {claim.pending_question.check_name}</p>
          <div className="question-actions">
            <button disabled={answering} onClick={() => submitAnswer('yes')}>Yes</button>
            <button disabled={answering} onClick={() => submitAnswer('no')}>No</button>
          </div>
          <div className="question-actions">
            <input
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder="Or type a specific answer…"
            />
            <button disabled={answering || !answerText} onClick={() => submitAnswer(answerText)}>Send</button>
          </div>
        </div>
      )}

      {claim.decision && (
        <div className={`decision-box decision-${claim.decision}`}>
          <h3>{DECISION_LABELS[claim.decision] || claim.decision}</h3>
          <p>{claim.decision_reason}</p>
        </div>
      )}

      <h3>Check ledger</h3>
      <ul className="check-list">
        {claim.checks.map((c) => (
          <CheckRow key={c.check_name} check={c} />
        ))}
      </ul>

      {error && <p className="error">{error}</p>}
    </div>
  );
}
