"""Demo-grade multi-user auth.

Three fixed users -- `admin`, `processor`, `customer` -- all sharing the one
`AUTH_PASSWORD`. The username (sent in the `X-Username` header) only selects a
*role*; it is not a secret and carries no per-user password. This is deliberately
minimal (see README "Known Limitations"): enough to demo role-scoped views, not a
real identity provider.

Roles:
  - admin     -- sees everything, including the Agent tab and the per-claim
                 Context / Memory / Sub-agents tracing tabs.
  - processor -- every claim, but no Agent tab and no tracing tabs.
  - customer  -- may only file claims and see the claims they filed.
"""
import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ROLES = {"admin", "processor", "customer"}

_bearer_scheme = HTTPBearer()


@dataclass(frozen=True)
class Identity:
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_customer(self) -> bool:
        return self.role == "customer"


def _password() -> str | None:
    # Read lazily so tests / imports that set the env var after module load still work.
    return os.getenv("AUTH_PASSWORD")


def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
    x_username: str | None = Header(default=None),
) -> Identity:
    """Validate the shared password and resolve the caller's role from `X-Username`.
    Missing header -> `admin` (keeps `curl`/tests that only send the bearer working)."""
    password = _password()
    if not password or credentials.credentials != password:
        raise HTTPException(status_code=401, detail="invalid credentials")

    username = (x_username or "admin").strip().lower()
    if username not in ROLES:
        raise HTTPException(status_code=401, detail=f"unknown user {username!r}")
    return Identity(username=username, role=username)


def require_admin(identity: Identity = Depends(require_auth)) -> Identity:
    """Gate for the agent-tracing endpoints -- admin only."""
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail="admin only")
    return identity
