import { lazy, Suspense, useState } from 'react';
import { getStoredPassword, getRole, clearStoredPassword } from './api';
import PasswordGate from './components/PasswordGate';
import ClaimForm from './components/ClaimForm';
import ClaimList from './components/ClaimList';
import ClaimDetail from './components/ClaimDetail';
import TabStrip from './components/TabStrip';

// Lazy so mermaid (a large dep, only used here) stays out of the initial bundle.
const AgentPanel = lazy(() => import('./components/AgentPanel'));

const LIST_TAB_ID = 'list';
const LIST_TAB = { id: LIST_TAB_ID, kind: 'list' };
const AGENT_TAB_ID = 'agent';

let tabSeq = 0;
function nextTabId(prefix) {
  tabSeq += 1;
  return `${prefix}-${tabSeq}`;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(!!getStoredPassword());
  const [role, setRole] = useState(getRole());
  const [tabs, setTabs] = useState([LIST_TAB]);
  const [activeTabId, setActiveTabId] = useState(LIST_TAB_ID);
  const [refreshToken, setRefreshToken] = useState(0);

  if (!authenticated) {
    return (
      <PasswordGate
        onAuthenticated={(r) => {
          setRole(r || getRole());
          setAuthenticated(true);
        }}
      />
    );
  }

  const isAdmin = role === 'admin';

  function handleLogout() {
    clearStoredPassword();
    setAuthenticated(false);
    setRole('');
    setTabs([LIST_TAB]);
    setActiveTabId(LIST_TAB_ID);
  }

  function openClaimTab(claimId) {
    const existing = tabs.find((t) => t.kind === 'detail' && t.claimId === claimId);
    if (existing) {
      setActiveTabId(existing.id);
      return;
    }
    const tab = { id: nextTabId('detail'), kind: 'detail', claimId };
    setTabs([...tabs, tab]);
    setActiveTabId(tab.id);
  }

  function openNewClaimTab() {
    const tab = { id: nextTabId('new'), kind: 'new-claim' };
    setTabs([...tabs, tab]);
    setActiveTabId(tab.id);
  }

  function openAgentTab() {
    if (!isAdmin) return;
    if (!tabs.some((t) => t.id === AGENT_TAB_ID)) {
      setTabs([...tabs, { id: AGENT_TAB_ID, kind: 'agent' }]);
    }
    setActiveTabId(AGENT_TAB_ID);
  }

  function closeTab(tabId) {
    if (tabId === LIST_TAB_ID) return;
    const index = tabs.findIndex((t) => t.id === tabId);
    if (index === -1) return;
    const next = tabs.filter((t) => t.id !== tabId);
    setTabs(next);
    if (activeTabId === tabId) {
      const fallback = next[index - 1] || next[0];
      setActiveTabId(fallback.id);
    }
  }

  function handleClaimSubmitted(tabId, claimId) {
    setTabs(tabs.map((t) => (t.id === tabId ? { id: t.id, kind: 'detail', claimId } : t)));
    setActiveTabId(tabId);
    setRefreshToken((t) => t + 1);
  }

  const openClaimIds = new Set(tabs.filter((t) => t.kind === 'detail').map((t) => t.claimId));

  return (
    <div className="app">
      <header className="app-header">
        <h1>Claim Assistant</h1>
        <div className="app-header-actions">
          <span className="app-role-badge" title="Logged-in role">{role || 'admin'}</span>
          {isAdmin && (
            <button className="agent-btn" onClick={openAgentTab}>Agent</button>
          )}
          <button className="start-claim-btn" onClick={openNewClaimTab}>Start Claim</button>
          <button className="logout" onClick={handleLogout}>Log out</button>
        </div>
      </header>
      <TabStrip tabs={tabs} activeTabId={activeTabId} onSelect={setActiveTabId} onClose={closeTab} />
      <div className="app-body">
        {tabs.map((tab) => (
          <div key={tab.id} className="tab-panel" style={{ display: tab.id === activeTabId ? 'block' : 'none' }}>
            {tab.kind === 'list' && (
              <ClaimList openClaimIds={openClaimIds} onSelect={openClaimTab} refreshToken={refreshToken} role={role} />
            )}
            {tab.kind === 'new-claim' && (
              <ClaimForm onSubmitted={(claimId) => handleClaimSubmitted(tab.id, claimId)} />
            )}
            {tab.kind === 'detail' && (
              <ClaimDetail
                claimId={tab.claimId}
                role={role}
                onAnswered={() => setRefreshToken((t) => t + 1)}
              />
            )}
            {tab.kind === 'agent' && isAdmin && (
              <Suspense fallback={<p className="muted">Loading…</p>}>
                <AgentPanel />
              </Suspense>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
