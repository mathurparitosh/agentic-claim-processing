import { useState } from 'react';
import { setStoredPassword, setStoredUser, checkAuth, USERS } from '../api';

// Demo affordance: all three users share AUTH_PASSWORD, so the quick-pick buttons can
// prefill both fields. Override at build time with VITE_DEMO_PASSWORD='' to disable
// (the buttons then only prefill the username and you type the password).
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? 'password';

const USER_BLURB = {
  admin: 'Everything — claims, the Agent tab, and the per-claim tracing tabs.',
  processor: 'Every claim, but no Agent tab and no tracing tabs.',
  customer: 'File a claim and see only the claims you filed.',
};

export default function PasswordGate({ onAuthenticated }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(false);

  function pick(user) {
    setUsername(user);
    setPassword(DEMO_PASSWORD);
    setError('');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setChecking(true);
    setStoredUser(username);
    setStoredPassword(password);
    try {
      const { role } = await checkAuth();
      onAuthenticated(role);
    } catch {
      setError('Incorrect username or password.');
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="gate">
      <form className="gate-form" onSubmit={handleSubmit}>
        <h1>Claim Assistant</h1>
        <p>Pick a demo user, or enter credentials.</p>

        <div className="gate-users">
          {USERS.map((u) => (
            <button
              type="button"
              key={u}
              className={`gate-user ${username === u ? 'gate-user-active' : ''}`}
              onClick={() => pick(u)}
            >
              <span className="gate-user-name">{u}</span>
              <span className="gate-user-blurb">{USER_BLURB[u]}</span>
            </button>
          ))}
        </div>

        <label className="gate-field">
          Username
          <input
            list="gate-user-list"
            value={username}
            onChange={(e) => setUsername(e.target.value.trim().toLowerCase())}
            placeholder="admin / processor / customer"
            autoComplete="username"
          />
          <datalist id="gate-user-list">
            {USERS.map((u) => (
              <option key={u} value={u} />
            ))}
          </datalist>
        </label>

        <label className="gate-field">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Shared password"
            autoComplete="current-password"
            autoFocus
          />
        </label>

        <button type="submit" disabled={checking || !password || !username}>
          {checking ? 'Checking…' : 'Continue'}
        </button>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  );
}
