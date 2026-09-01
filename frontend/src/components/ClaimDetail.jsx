import { useEffect, useState } from 'react';
import { getClaim, getContext, getAudit, answerQuestion, checkRecoveryEligibility } from '../api';

const POLL_MS = 2000;
const ACTIVE_STATUSES = new Set(['pending', 'processing', 'awaiting_input']);
const RECOVERY_ELIGIBLE_DECISIONS = new Set(['approve', 'inconclusive']);
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

const EVENT_LABELS = {
  claim_submitted: 'claim submitted',
  run_started: 'run started',
  agent_think: 'think',
  tool_call: 'tool',
  human_answer: 'human answer',
  determination_written: 'determination',
  recovery_assessment: 'recovery',
};

const RETRIEVAL_TOOLS = new Set(['search_policy', 'search_network_policy']);

// One-line summary of a vector-search (RAG) call for the collapsed row.
function retrievalDetail(p) {
  const r = p.result || {};
  const hits = r.results || [];
  const scanned = r.candidate_count ?? (r.candidates ? r.candidates.length : null);
  const filter = r.filter?.claim_type ? `filter=${r.filter.claim_type}` : '';
  const q = r.query ? `"${r.query}"` : '';
  if (!hits.length) {
    return [q, filter, `0 clauses cleared the relevance floor of ${scanned ?? '?'} scanned`]
      .filter(Boolean)
      .join('  ·  ');
  }
  const top = hits[0];
  const topStr = top?.citation
    ? `top ${top.citation}${top.score != null ? ` (${top.score.toFixed(2)})` : ''}`
    : '';
  return [q, filter, `${hits.length} hit${hits.length > 1 ? 's' : ''} / ${scanned ?? '?'} scanned`, topStr]
    .filter(Boolean)
    .join('  ·  ');
}

// Pull the two or three things worth seeing without expanding a row: what happened,
// a one-line detail, which sub-agent was active, and which model produced it.
function describeAudit(entry) {
  const p = entry.payload || {};
  const t = entry.event_type;
  let label = EVENT_LABELS[t] || t.replaceAll('_', ' ');
  const subAgent = p.sub_agent || null;
  const model = p.model || null;
  let detail = '';

  const toolName = p.tool || entry.event_subtype || '';
  const isRetrieval = t === 'tool_call' && RETRIEVAL_TOOLS.has(toolName);

  if (t === 'agent_think') {
    const tools = p.proposed_tools || [];
    detail = tools.length ? `→ ${tools.join(', ')}` : '→ (no tool proposed)';
    if (p.role_switch) detail = `role switch  ${detail}`;
  } else if (isRetrieval) {
    label = toolName === 'search_network_policy' ? 'RAG · network' : 'RAG · policy';
    const upd = p.checks_updated || [];
    const updStr = upd.length ? `  ⇒ ${upd.map((u) => `${u.check}: ${u.status}`).join(', ')}` : '';
    detail = retrievalDetail(p) + updStr;
  } else if (t === 'tool_call') {
    detail = toolName;
    const upd = p.checks_updated || [];
    if (upd.length) detail += `  ⇒ ${upd.map((u) => `${u.check}: ${u.status}`).join(', ')}`;
    else if (p.result?.skipped) detail += '  (skipped)';
  } else if (t === 'run_started') {
    detail = [p.agent_mode && `mode: ${p.agent_mode}`, p.provider].filter(Boolean).join('  ·  ');
  } else if (t === 'claim_submitted') {
    detail = p.claim_type || '';
  } else if (t === 'human_answer') {
    detail = `"${p.answer ?? ''}"`;
  } else if (t === 'determination_written') {
    detail = `${(p.decision || '').toUpperCase()}${p.forced ? '  (forced)' : ''}`;
  } else if (t === 'recovery_assessment') {
    detail = entry.event_subtype === 'eligible' ? 'eligible' : 'not eligible';
  } else if (entry.event_subtype) {
    detail = entry.event_subtype;
  }
  return { label, detail, subAgent, model, isRetrieval };
}

function AuditRow({ entry }) {
  const [expanded, setExpanded] = useState(false);
  const { label, detail, subAgent, model, isRetrieval } = describeAudit(entry);
  return (
    <li className={`audit-row audit-source-${entry.source}${isRetrieval ? ' audit-row-retrieval' : ''}`}>
      <button type="button" className="audit-summary" onClick={() => setExpanded((e) => !e)}>
        <span className="audit-time" title={new Date(entry.created_at).toLocaleString()}>
          {new Date(entry.created_at).toLocaleTimeString()}
        </span>
        <span className="audit-event">{label}</span>
        <span className="audit-detail" title={detail}>{detail}</span>
        {subAgent && <span className={`sub-agent-pill sub-agent-${subAgent}`}>{subAgent}</span>}
        {model && (
          <span
            className="audit-model"
            title={entry.payload?.provider ? `provider: ${entry.payload.provider}` : undefined}
          >
            {model}
          </span>
        )}
        <span className={`source-pill source-${entry.source}`}>{entry.source}</span>
      </button>
      {expanded && entry.payload && (
        <pre className="check-detail">{JSON.stringify(entry.payload, null, 2)}</pre>
      )}
    </li>
  );
}

function SummaryPane({ claim, context, loading }) {
  const account = context?.account;
  const transaction = context?.transaction;
  const disputeType = claim.claim_payload?.reason;

  return (
    <aside className="claim-summary-pane">
      <div className="summary-section">
        <h3>Account</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : account ? (
          <dl className="context-fields">
            <dt>Account ID</dt><dd>{account.account_id}</dd>
            <dt>Name</dt><dd>{account.member_name || '—'}</dd>
          </dl>
        ) : (
          <p className="muted">Not found.</p>
        )}
      </div>

      <div className="summary-section">
        <h3>Transaction</h3>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : transaction ? (
          <dl className="context-fields">
            <dt>Reference</dt><dd>{transaction.transaction_ref}</dd>
            <dt>Merchant</dt><dd>{transaction.merchant || '—'}</dd>
            <dt>Amount</dt><dd>${Number(transaction.amount).toFixed(2)}</dd>
          </dl>
        ) : (
          <p className="muted">Not found.</p>
        )}
      </div>

      <div className="summary-section">
        <h3>Dispute type</h3>
        <p className="summary-value">{disputeType ? disputeType.replaceAll('_', ' ') : '—'}</p>
      </div>
    </aside>
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
  const [recoveryStatus, setRecoveryStatus] = useState('idle'); // 'idle' | 'checking' | 'done'

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
    setRecoveryStatus('idle');
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

  async function handleCheckRecovery() {
    setRecoveryStatus('checking');
    setError('');
    try {
      await checkRecoveryEligibility(claimId);
      const auditData = await getAudit(claimId);
      setAudit(auditData.entries);
      setTab('audit');
      setRecoveryStatus('done');
    } catch (err) {
      setError(err.message);
      setRecoveryStatus('idle');
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
    <div className="claim-detail-layout">
      <SummaryPane claim={claim} context={context} loading={!context} />
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
            {RECOVERY_ELIGIBLE_DECISIONS.has(claim.decision) && (
              <button
                type="button"
                className="recovery-btn"
                disabled={recoveryStatus === 'checking'}
                onClick={handleCheckRecovery}
              >
                {recoveryStatus === 'checking' ? 'Checking…' : 'Check Recovery Eligibility'}
              </button>
            )}
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
    </div>
  );
}
