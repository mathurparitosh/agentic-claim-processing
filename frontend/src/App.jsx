import { useState } from 'react';
import { getStoredPassword, clearStoredPassword } from './api';
import PasswordGate from './components/PasswordGate';
import ClaimForm from './components/ClaimForm';
import ClaimList from './components/ClaimList';
import ClaimDetail from './components/ClaimDetail';

export default function App() {
  const [authenticated, setAuthenticated] = useState(!!getStoredPassword());
  const [selectedClaimId, setSelectedClaimId] = useState(null);
  const [refreshToken, setRefreshToken] = useState(0);

  if (!authenticated) {
    return <PasswordGate onAuthenticated={() => setAuthenticated(true)} />;
  }

  function handleSubmitted(claimId) {
    setSelectedClaimId(claimId);
    setRefreshToken((t) => t + 1);
  }

  function handleLogout() {
    clearStoredPassword();
    setAuthenticated(false);
    setSelectedClaimId(null);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Claim Assistant</h1>
        <button className="logout" onClick={handleLogout}>Log out</button>
      </header>
      <div className="app-body">
        <aside className="app-sidebar">
          <ClaimForm onSubmitted={handleSubmitted} />
          <ClaimList
            selectedClaimId={selectedClaimId}
            onSelect={setSelectedClaimId}
            refreshToken={refreshToken}
          />
        </aside>
        <main className="app-main">
          <ClaimDetail claimId={selectedClaimId} onAnswered={() => setRefreshToken((t) => t + 1)} />
        </main>
      </div>
    </div>
  );
}
