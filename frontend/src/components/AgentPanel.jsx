import { useEffect, useMemo, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { getToolCatalog, getAgentGraph } from '../api';

mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'loose', flowchart: { curve: 'linear' } });

const SUBTABS = [
  { id: 'tools', label: 'Tools' },
  { id: 'graph', label: 'Graph' },
];

const OWNER_LABEL = { research: 'Research', decisioning: 'Decisioning', recovery: 'Recovery (on-demand)' };

function MermaidDiagram({ chart, onError }) {
  const [svg, setSvg] = useState('');
  const ref = useRef(0);

  useEffect(() => {
    let cancelled = false;
    ref.current += 1;
    const id = `agent-graph-${ref.current}`;
    mermaid
      .render(id, chart)
      .then((res) => {
        if (!cancelled) setSvg(res.svg);
      })
      .catch((err) => {
        if (!cancelled) onError?.(err);
      });
    return () => {
      cancelled = true;
    };
  }, [chart, onError]);

  if (!svg) return <p className="muted">Rendering diagram…</p>;
  return <div className="mermaid-diagram" dangerouslySetInnerHTML={{ __html: svg }} />;
}

function ToolsView({ catalog }) {
  const byCategory = useMemo(() => {
    const groups = {};
    for (const tool of catalog.tools) {
      (groups[tool.category] ||= []).push(tool);
    }
    return groups;
  }, [catalog]);

  return (
    <div className="agent-tools">
      <div className="agent-owner-grid">
        {['research', 'decisioning'].map((owner) => (
          <div className="agent-owner-card" key={owner}>
            <h3>
              <span className={`sub-agent-pill sub-agent-${owner}`}>{OWNER_LABEL[owner]}</span> sub-agent
            </h3>
            <p className="agent-owner-line">
              <span className="muted">tools</span>{' '}
              {catalog.owners[owner].tools.map((t) => <code key={t}>{t}</code>)}
            </p>
            <p className="agent-owner-line">
              <span className="muted">owns checks</span>{' '}
              {catalog.owners[owner].checks.map((c) => <code key={c}>{c}</code>)}
            </p>
          </div>
        ))}
      </div>

      {Object.entries(byCategory).map(([category, tools]) => (
        <div className="agent-tool-group" key={category}>
          <h4>{category}</h4>
          <ul className="agent-tool-list">
            {tools.map((tool) => (
              <li className="agent-tool-row" key={tool.name}>
                <div className="agent-tool-head">
                  <code className="agent-tool-name">
                    {tool.name}({tool.params.map((p) => p.name).join(', ')})
                  </code>
                  <span className={`sub-agent-pill sub-agent-${tool.owner}`}>{OWNER_LABEL[tool.owner]}</span>
                </div>
                <p className="agent-tool-desc">{tool.description}</p>
                <div className="agent-tool-meta">
                  {tool.params.length > 0 && (
                    <span>
                      params:{' '}
                      {tool.params.map((p) => (
                        <code key={p.name} className={p.required ? 'param-required' : ''}>
                          {p.name}
                          {p.required ? '' : '?'}: {p.type}
                        </code>
                      ))}
                    </span>
                  )}
                  <span>
                    resolves:{' '}
                    {tool.resolves_checks.length === 0
                      ? <span className="muted">— (no check closes directly)</span>
                      : tool.resolves_checks.map((c) => (
                          <code key={c}>{c === '*' ? 'any check (via check_name)' : c}</code>
                        ))}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function GraphView({ graph }) {
  const [mode, setMode] = useState('mermaid');
  const [mermaidFailed, setMermaidFailed] = useState(false);
  const showAscii = mode === 'ascii' || mermaidFailed;

  return (
    <div className="agent-graph">
      <div className="tabs agent-graph-toggle">
        <button
          type="button"
          className={`tab ${!showAscii ? 'tab-active' : ''}`}
          onClick={() => { setMode('mermaid'); setMermaidFailed(false); }}
        >
          Diagram
        </button>
        <button type="button" className={`tab ${showAscii ? 'tab-active' : ''}`} onClick={() => setMode('ascii')}>
          ASCII
        </button>
      </div>

      {mermaidFailed && mode === 'mermaid' && (
        <p className="muted">Diagram rendering failed — showing the ASCII rendering instead.</p>
      )}

      {showAscii ? (
        <pre className="agent-graph-ascii">{graph.ascii}</pre>
      ) : (
        <MermaidDiagram chart={graph.mermaid} onError={() => setMermaidFailed(true)} />
      )}

      <h4>Nodes</h4>
      <dl className="agent-graph-nodes">
        {Object.entries(graph.nodes).map(([node, prose]) => (
          <div key={node}>
            <dt><code>{node}</code></dt>
            <dd>{prose}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function AgentPanel() {
  const [subtab, setSubtab] = useState('tools');
  const [catalog, setCatalog] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([getToolCatalog(), getAgentGraph()])
      .then(([c, g]) => {
        if (cancelled) return;
        setCatalog(c);
        setGraph(g);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="agent-panel">
      <h2>Agent</h2>
      <p className="muted agent-panel-intro">
        The tool catalog and compiled graph for the Research / Decisioning orchestrator — the same for
        every claim. Per-run state (context window, memory, sub-agent activity) lives on each claim's own tabs.
      </p>

      <div className="tabs">
        {SUBTABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab ${subtab === t.id ? 'tab-active' : ''}`}
            onClick={() => setSubtab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {!error && (!catalog || !graph) && <p className="muted">Loading…</p>}

      {catalog && graph && subtab === 'tools' && <ToolsView catalog={catalog} />}
      {catalog && graph && subtab === 'graph' && <GraphView graph={graph} />}
    </div>
  );
}
