"""
JWT-based authentication + RBAC dependency injection for FastAPI.

Roles (ascending privilege):
  analyst   – can view data, run analyses, create overrides
  reviewer  – can generate reports, approve/reject overrides
  admin     – full access including audit logs and user management

Dev-mode bypass:
  Set AUTH_DISABLED=true (or app_env=development + AUTH_DISABLED not set)
  to skip all JWT checks. The request is treated as analyst role by default.
  This preserves compatibility with all existing test workflows.

Token format:
  Bearer JWT signed with HS256 using SECRET_KEY env var.
  Payload: {sub: username, role: str, exp: int}

In-memory user store (dev only):
  Loaded from DEV_USERS env var as JSON, defaults to a single admin user.
  Production deployments replace this with a DB lookup.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

try:
    from jose import JWTError, jwt
    from passlib.context import CryptContext
    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

ROLE_HIERARCHY = {"analyst": 0, "reviewer": 1, "admin": 2}

# ── Dev user store ────────────────────────────────────────────────────────────

import json as _json

_DEV_USERS_RAW = os.getenv("DEV_USERS", "")
_DEV_USERS: dict[str, dict] = {}

if _DEV_USERS_RAW:
    try:
        _DEV_USERS = _json.loads(_DEV_USERS_RAW)
    except Exception:
        logger.warning("DEV_USERS env var is not valid JSON; using defaults.")

if not _DEV_USERS:
    # Default: one user per role for local development
    _DEV_USERS = {
        "admin": {"password": "admin123", "role": "admin"},
        "analyst": {"password": "analyst123", "role": "analyst"},
        "reviewer": {"password": "reviewer123", "role": "reviewer"},
    }

# ── Password hashing ──────────────────────────────────────────────────────────

if _JOSE_AVAILABLE:
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def verify_password(plain: str, hashed: str) -> bool:
        return _pwd_context.verify(plain, hashed)

    def hash_password(plain: str) -> str:
        return _pwd_context.hash(plain)
else:
    # Fallback for environments without passlib (dev only)
    def verify_password(plain: str, hashed: str) -> bool:  # type: ignore[misc]
        return plain == hashed

    def hash_password(plain: str) -> str:  # type: ignore[misc]
        return plain


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(username: str, role: str) -> str:
    if not _JOSE_AVAILABLE:
        return f"dev-token-{username}-{role}"
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    if not _JOSE_AVAILABLE:
        # Simple dev token format: "dev-token-{username}-{role}"
        parts = token.split("-")
        if len(parts) >= 4:
            return {"sub": parts[2], "role": parts[3]}
        return {"sub": "anonymous", "role": "analyst"}
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── User authentication ───────────────────────────────────────────────────────

def authenticate_user(username: str, password: str) -> dict | None:
    """Check credentials against the in-memory dev store."""
    user = _DEV_USERS.get(username)
    if not user:
        return None
    stored_pw = user["password"]
    # Dev passwords stored as plaintext; production would use bcrypt hash
    if password != stored_pw:
        return None
    return {"username": username, "role": user["role"]}


# ── FastAPI dependency ────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def _auth_disabled() -> bool:
    settings = get_settings()
    # Disable auth in development unless explicitly enabled
    return os.getenv("AUTH_DISABLED", "true" if settings.app_env == "development" else "false").lower() == "true"


def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)] = None) -> dict:
    """
    FastAPI dependency. Returns the current user dict {username, role}.
    In dev mode (AUTH_DISABLED=true), returns a default analyst user.
    """
    if _auth_disabled():
        return {"username": "dev-analyst", "role": "analyst"}

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        username: str = payload.get("sub", "")
        role: str = payload.get("role", "analyst")
        if not username:
            raise ValueError("Empty subject")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": username, "role": role}


def require_role(minimum_role: str):
    """
    Returns a FastAPI dependency that enforces a minimum role level.

    Usage::

        @router.post("/admin-only")
        def endpoint(user = Depends(require_role("admin"))):
            ...
    """
    def _check(user: dict = Depends(get_current_user)) -> dict:
        user_level = ROLE_HIERARCHY.get(user.get("role", "analyst"), 0)
        required_level = ROLE_HIERARCHY.get(minimum_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role}' or higher required.",
            )
        return user
    return _check
