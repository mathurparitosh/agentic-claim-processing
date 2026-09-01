import { useEffect, useState } from 'react';
import {
  getClaim,
  getContext,
  getAudit,
  getAgentContext,
  getAgentMemory,
  answerQuestion,
  checkRecoveryEligibility,
} from '../api';

const POLL_MS = 2000;
const ACTIVE_STATUSES = new Set(['pending', 'processing', 'awaiting_input']);
const RECOVERY_ELIGIBLE_DECISIONS = new Set(['approve', 'inconclusive']);
const TABS = [
  { id: 'checks', label: 'Checks' },
  { id: 'context', label: 'Account & Transaction' },
  { id: 'audit', label: 'Audit Trail' },
  { id: 'agentcontext', label: 'Context' },
  { id: 'memory', label: 'Memory' },
  { id: 'subagents', label: 'Sub-agents' },
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

function AgentMessageRow({ msg }) {
  const [expanded, setExpanded] = useState(false);
  const preview = (msg.content || '').replace(/\s+/g, ' ').trim();
  const toolCalls = msg.tool_calls || [];
  return (
    <li className="agent-msg-row">
      <button type="button" className="agent-msg-summary" onClick={() => setExpanded((e) => !e)}>
        <span className={`agent-msg-role role-${msg.role}`}>{msg.role}</span>
        {toolCalls.length > 0 ? (
          <span className="agent-msg-toolcall">
            → {toolCalls.map((tc) => `${tc.name}(${Object.keys(tc.args || {}).join(', ')})`).join(', ')}
          </span>
        ) : (
          <span className="agent-msg-preview">{preview || '(empty)'}</span>
        )}
      </button>
      {expanded && (
        <pre className="agent-msg-body">
          {msg.content || '(no text content)'}
          {toolCalls.length > 0 ? `\n\ntool_calls: ${JSON.stringify(toolCalls, null, 2)}` : ''}
        </pre>
      )}
    </li>
  );
}

function ContextTab({ data, loading }) {
  if (loading && !data) return <p className="muted">Loading…</p>;
  if (!data) return null;
  if (data.pending) {
    return <p className="muted">The agent hasn't started on this claim yet — no message window exists.</p>;
  }
  const c = data.counters || {};
  return (
    <div className="agent-context-tab">
      <div className="context-tracing-header">
        <span><span className="label">messages</span>{data.message_count}</span>
        <span><span className="label">≈ tokens</span>{data.approx_tokens.toLocaleString()}</span>
        <span><span className="label">iteration</span>{c.iteration ?? '—'} / {c.max_iterations}</span>
        <span><span className="label">no-progress</span>{c.iterations_without_progress ?? '—'} / {c.no_progress_limit}</span>
        <span><span className="label">questions</span>{c.questions_asked ?? '—'}</span>
        {data.active_agent && (
          <span>
            <span className="label">active</span>
            <span className={`sub-agent-pill sub-agent-${data.active_agent}`}>{data.active_agent}</span>
          </span>
        )}
        <span>
          <span className="label">next</span>
          {data.next_nodes.length ? data.next_nodes.join(', ') : data.claim_status === 'completed' ? 'done' : '—'}
        </span>
        <span><span className="label">model</span><span className="audit-model">{data.model}</span></span>
      </div>
      <p className="context-window-note">
        The exact message list handed to the model on its next turn — it grows every iteration. The
        Audit Trail tab is the durable record of the run; this is the working memory that gets sent.
      </p>
      <ul className="agent-msg-list">
        {data.messages.map((m, i) => (
          <AgentMessageRow key={i} msg={m} />
        ))}
      </ul>
    </div>
  );
}

function MemoryTab({ data, loading }) {
  if (loading && !data) return <p className="muted">Loading…</p>;
  if (!data) return null;
  if (!data.account_id) {
    return <p className="memory-empty">This claim has no <code>account_id</code>, so there are no episodic facts.</p>;
  }
  if (!data.facts.length) {
    return (
      <p className="memory-empty">
        No episodic facts stored for account <code>{data.account_id}</code> yet. The run writes these
        after account-profile lookups; they carry into later claims on the same account.
      </p>
    );
  }
  return (
    <div className="agent-memory-tab">
      <p className="context-window-note">
        Cross-claim memory for account <code>{data.account_id}</code>. Read at init, upserted after
        account lookups — each fact shows which claim last wrote it.
      </p>
      <ul className="agent-msg-list">
        {data.facts.map((f) => (
          <li className="memory-row" key={f.fact_key}>
            <div className="memory-row-head">
              <span className="memory-key">{f.fact_key}</span>
              <span className={`memory-origin-pill ${f.written_by_this_claim ? 'memory-origin-this' : ''}`}>
                {f.written_by_this_claim
                  ? 'written by this claim'
                  : `from claim ${(f.origin_claim_id || '').slice(0, 8) || 'unknown'}`}
              </span>
              {f.source_tool && <span className="audit-model">{f.source_tool}</span>}
            </div>
            <pre className="memory-value">{JSON.stringify(f.fact_value, null, 2)}</pre>
          </li>
        ))}
      </ul>
    </div>
  );
}

const SUBAGENT_ROLE = {
  research:
    'Grounding + Retrieval tools only. Gathers evidence for evidence-type checks; never judges or decides.',
  decisioning:
    'Computation tools + ask_human + write_determination. Resolves the remaining checks, escalates, calls the close.',
};

function deriveSubAgents(entries) {
  if (!entries) return null;
  const thinks = entries.filter((e) => e.event_type === 'agent_think');
  if (!thinks.length) return null;
  const calls = entries.filter((e) => e.event_type === 'tool_call');
  const build = (name) => {
    const t = thinks.filter((e) => e.payload?.sub_agent === name);
    const c = calls.filter((e) => e.payload?.sub_agent === name);
    const iters = t.map((e) => e.payload?.iteration).filter((n) => n != null);
    return {
      name,
      turns: t.length,
      iterationRange: iters.length ? [Math.min(...iters), Math.max(...iters)] : null,
      tools: [...new Set(c.map((e) => e.payload?.tool || e.event_subtype).filter(Boolean))],
      model: t[0]?.payload?.model || null,
    };
  };
  const handoff = thinks.find((e) => e.payload?.role_switch);
  return {
    research: build('research'),
    decisioning: build('decisioning'),
    handoff: handoff ? { iteration: handoff.payload?.iteration, at: handoff.created_at } : null,
    lastThink: thinks[thinks.length - 1]?.payload?.sub_agent || null,
  };
}

function SubAgentColumn({ agent, active }) {
  const range = agent.iterationRange;
  return (
    <div className={`subagent-col ${active ? 'subagent-col-active' : ''}`}>
      <h3>
        <span className={`sub-agent-pill sub-agent-${agent.name}`}>{agent.name}</span>
        {active && ' · active'}
      </h3>
      <p className="subagent-stat">{SUBAGENT_ROLE[agent.name]}</p>
      <p className="subagent-stat"><span className="muted">turns</span>{agent.turns}</p>
      <p className="subagent-stat">
        <span className="muted">iterations</span>
        {range ? (range[0] === range[1] ? range[0] : `${range[0]}–${range[1]}`) : '—'}
      </p>
      {agent.model && (
        <p className="subagent-stat"><span className="muted">model</span><span className="audit-model">{agent.model}</span></p>
      )}
      <p className="subagent-stat"><span className="muted">tools used</span></p>
      <ul className="subagent-turns">
        {agent.tools.length ? (
          agent.tools.map((t) => <li className="subagent-turn" key={t}>{t}</li>)
        ) : (
          <li className="subagent-turn muted">none</li>
        )}
      </ul>
    </div>
  );
}

function SubAgentsTab({ audit, activeAgent }) {
  const data = deriveSubAgents(audit);
  if (!data) return <p className="muted">No agent reasoning turns recorded yet.</p>;
  if (data.research.turns === 0 && data.decisioning.turns === 0) {
    return (
      <p className="muted">This run's audit trail has no research / decisioning turns (it may predate the orchestrator).</p>
    );
  }
  const active = activeAgent || data.lastThink;
  return (
    <div className="agent-subagents-tab">
      <p className="context-window-note">
        Research runs first, then hands off <em>permanently</em> to Decisioning once research-owned
        checks resolve or its iteration budget runs out. Iteration / no-progress / question counters
        are global across both.
      </p>
      <div className="subagent-grid">
        <SubAgentColumn agent={data.research} active={active === 'research'} />
        <SubAgentColumn agent={data.decisioning} active={active === 'decisioning'} />
      </div>
      <p className="subagent-handoff">
        {data.handoff
          ? `Handoff to Decisioning at iteration ${data.handoff.iteration} (${new Date(
              data.handoff.at,
            ).toLocaleTimeString()}).`
          : 'No handoff yet — still in the Research phase.'}
      </p>
    </div>
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
  const [agentContext, setAgentContext] = useState(null);
  const [memory, setMemory] = useState(null);
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
        // agent-context / memory degrade to null on error (transient checkpoint read,
        // etc.) rather than red-bannering the whole detail view.
        const [claimData, auditData, agentCtx, mem] = await Promise.all([
          getClaim(claimId),
          getAudit(claimId),
          getAgentContext(claimId).catch(() => null),
          getAgentMemory(claimId).catch(() => null),
        ]);
        if (cancelled) return;
        setClaim(claimData);
        setAudit(auditData.entries);
        if (agentCtx) setAgentContext(agentCtx);
        if (mem) setMemory(mem);
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
    setAgentContext(null);
    setMemory(null);
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
        {tab === 'agentcontext' && <ContextTab data={agentContext} loading={!agentContext} />}
        {tab === 'memory' && <MemoryTab data={memory} loading={!memory} />}
        {tab === 'context' && <ContextPanel context={context} loading={!context} />}
        {tab === 'audit' && <AuditPanel entries={audit} loading={!audit} />}
        {tab === 'subagents' && <SubAgentsTab audit={audit} activeAgent={agentContext?.active_agent} />}

        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
