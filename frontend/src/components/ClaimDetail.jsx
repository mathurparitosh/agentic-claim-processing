import { useEffect, useState } from 'react';
import { getClaim, getContext, getAudit, answerQuestion } from '../api';

const POLL_MS = 2000;
const ACTIVE_STATUSES = new Set(['pending', 'processing', 'awaiting_input']);
const TABS = [
  { id: 'checks', label: 'Checks' },
  { id: 'context', label: 'Account & Transaction' },
  { id: 'audit', label: 'Audit Trail' },
];

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

function ContextPanel({ context, loading }) {
  if (loading) return <p className="muted">Loading…</p>;
  if (!context) return null;

  const { account, transaction } = context;
  return (
    <div className="context-panel">
      <div className="context-card">
        <h3>Account</h3>
        {account ? (
          <dl className="context-fields">
            <dt>Account ID</dt><dd>{account.account_id}</dd>
            <dt>Member name</dt><dd>{account.member_name || '—'}</dd>
            <dt>Standing</dt><dd>{account.standing}</dd>
            <dt>Opened</dt><dd>{account.opened_at ? new Date(account.opened_at).toLocaleString() : '—'}</dd>
            <dt>Dispute history count</dt><dd>{account.dispute_history_count}</dd>
            <dt>Fraud red flags</dt>
            <dd>{account.fraud_red_flags?.length ? account.fraud_red_flags.join(', ') : 'None'}</dd>
          </dl>
        ) : (
          <p className="muted">No account profile found for this claim's account ID.</p>
        )}
      </div>

      <div className="context-card">
        <h3>Disputed transaction</h3>
        {transaction ? (
          <dl className="context-fields">
            <dt>Reference</dt><dd>{transaction.transaction_ref}</dd>
            <dt>Occurred</dt><dd>{new Date(transaction.occurred_at).toLocaleString()}</dd>
            <dt>Amount</dt><dd>${Number(transaction.amount).toFixed(2)}</dd>
            <dt>Merchant</dt><dd>{transaction.merchant || '—'}</dd>
            <dt>Location</dt><dd>{transaction.location || '—'}</dd>
            <dt>Channel</dt><dd>{transaction.channel || '—'}</dd>
            <dt>Status</dt><dd>{transaction.status}</dd>
          </dl>
        ) : (
          <p className="muted">No transaction record found for this claim's disputed transaction ID.</p>
        )}
      </div>
    </div>
  );
}

function AuditRow({ entry }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li className={`audit-row audit-source-${entry.source}`}>
      <button type="button" className="audit-summary" onClick={() => setExpanded((e) => !e)}>
        <span className="audit-time">{new Date(entry.created_at).toLocaleString()}</span>
        <span className="audit-event">
          {entry.event_type}
          {entry.event_subtype ? ` / ${entry.event_subtype}` : ''}
        </span>
        <span className={`source-pill source-${entry.source}`}>{entry.source}</span>
      </button>
      {expanded && entry.payload && (
        <pre className="check-detail">{JSON.stringify(entry.payload, null, 2)}</pre>
      )}
    </li>
  );
}

function AuditPanel({ entries, loading }) {
  if (loading && !entries) return <p className="muted">Loading…</p>;
  if (!entries || entries.length === 0) return <p className="muted">No audit entries yet.</p>;
  return (
    <ul className="audit-list">
      {entries.map((entry, i) => (
        <AuditRow key={i} entry={entry} />
      ))}
    </ul>
  );
}

export default function ClaimDetail({ claimId, onAnswered }) {
  const [claim, setClaim] = useState(null);
  const [context, setContext] = useState(null);
  const [audit, setAudit] = useState(null);
  const [tab, setTab] = useState('checks');
  const [error, setError] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [answering, setAnswering] = useState(false);

  useEffect(() => {
    if (!claimId) return;
    let cancelled = false;
    let timer;

    async function poll() {
      try {
        const [claimData, auditData] = await Promise.all([getClaim(claimId), getAudit(claimId)]);
        if (cancelled) return;
        setClaim(claimData);
        setAudit(auditData.entries);
        setError('');
        if (ACTIVE_STATUSES.has(claimData.status)) {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    setClaim(null);
    setContext(null);
    setAudit(null);
    setTab('checks');
    poll();
    getContext(claimId).then((data) => {
      if (!cancelled) setContext(data);
    }).catch((err) => {
      if (!cancelled) setError(err.message);
    });

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

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab ${tab === t.id ? 'tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'checks' && (
        <ul className="check-list">
          {claim.checks.map((c) => (
            <CheckRow key={c.check_name} check={c} />
          ))}
        </ul>
      )}
      {tab === 'context' && <ContextPanel context={context} loading={!context} />}
      {tab === 'audit' && <AuditPanel entries={audit} loading={!audit} />}

      {error && <p className="error">{error}</p>}
    </div>
  );
}
