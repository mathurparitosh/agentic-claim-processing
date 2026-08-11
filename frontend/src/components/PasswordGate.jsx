import { useState } from 'react';
import { setStoredPassword, checkAuth } from '../api';

export default function PasswordGate({ onAuthenticated }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setChecking(true);
    setStoredPassword(password);
    try {
      await checkAuth();
      onAuthenticated();
    } catch {
      setError('Incorrect password.');
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="gate">
      <form className="gate-form" onSubmit={handleSubmit}>
        <h1>Claim Assistant</h1>
        <p>Enter the shared access password to continue.</p>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
        />
        <button type="submit" disabled={checking || !password}>
          {checking ? 'Checking…' : 'Continue'}
        </button>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  );
}
