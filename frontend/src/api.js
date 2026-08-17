const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const PASSWORD_KEY = 'claim-assistant-password';

export function getStoredPassword() {
  return sessionStorage.getItem(PASSWORD_KEY) || '';
}

export function setStoredPassword(password) {
  sessionStorage.setItem(PASSWORD_KEY, password);
}

export function clearStoredPassword() {
  sessionStorage.removeItem(PASSWORD_KEY);
}

class UnauthorizedError extends Error {}

async function request(path, options = {}) {
  const password = getStoredPassword();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${password}`,
      ...options.headers,
    },
  });

  if (res.status === 401) {
    clearStoredPassword();
    throw new UnauthorizedError('invalid credentials');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `request failed: ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

/** Cheap auth check: any authenticated GET works, /claims is always safe (no side effects). */
export function checkAuth() {
  return request('/claims?limit=1');
}

export function listClaims() {
  return request('/claims?limit=50');
}

export function getClaim(claimId) {
  return request(`/claims/${claimId}`);
}

export function getQuestions(claimId) {
  return request(`/claims/${claimId}/questions`);
}

export function getDecision(claimId) {
  return request(`/claims/${claimId}/decision`);
}

export function getContext(claimId) {
  return request(`/claims/${claimId}/context`);
}

export function getAudit(claimId) {
  return request(`/claims/${claimId}/audit`);
}

export function listAccounts() {
  return request('/accounts');
}

export function listAccountTransactions(accountId) {
  return request(`/accounts/${accountId}/transactions`);
}

export function submitClaim(claimType, claimPayload) {
  return request('/claims', {
    method: 'POST',
    body: JSON.stringify({ claim_type: claimType, claim_payload: claimPayload }),
  });
}

export function answerQuestion(claimId, answer) {
  return request(`/claims/${claimId}/answer`, {
    method: 'POST',
    body: JSON.stringify({ answer }),
  });
}

export { UnauthorizedError };
