import { useState } from 'react';
import { getStoredPassword, clearStoredPassword } from './api';
import PasswordGate from './components/PasswordGate';
import ClaimForm from './components/ClaimForm';
import ClaimList from './components/ClaimList';
import ClaimDetail from './components/ClaimDetail';
import TabStrip from './components/TabStrip';

const LIST_TAB_ID = 'list';
const LIST_TAB = { id: LIST_TAB_ID, kind: 'list' };

let tabSeq = 0;
function nextTabId(prefix) {
  tabSeq += 1;
  return `${prefix}-${tabSeq}`;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(!!getStoredPassword());
  const [tabs, setTabs] = useState([LIST_TAB]);
  const [activeTabId, setActiveTabId] = useState(LIST_TAB_ID);
  const [refreshToken, setRefreshToken] = useState(0);

  if (!authenticated) {
    return <PasswordGate onAuthenticated={() => setAuthenticated(true)} />;
  }

  function handleLogout() {
    clearStoredPassword();
    setAuthenticated(false);
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
          <button className="start-claim-btn" onClick={openNewClaimTab}>Start Claim</button>
          <button className="logout" onClick={handleLogout}>Log out</button>
        </div>
      </header>
      <TabStrip tabs={tabs} activeTabId={activeTabId} onSelect={setActiveTabId} onClose={closeTab} />
      <div className="app-body">
        {tabs.map((tab) => (
          <div key={tab.id} className="tab-panel" style={{ display: tab.id === activeTabId ? 'block' : 'none' }}>
            {tab.kind === 'list' && (
              <ClaimList openClaimIds={openClaimIds} onSelect={openClaimTab} refreshToken={refreshToken} />
            )}
            {tab.kind === 'new-claim' && (
              <ClaimForm onSubmitted={(claimId) => handleClaimSubmitted(tab.id, claimId)} />
            )}
            {tab.kind === 'detail' && (
              <ClaimDetail claimId={tab.claimId} onAnswered={() => setRefreshToken((t) => t + 1)} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
