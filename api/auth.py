"""JWT authentication for QuantX web app.

Two modes:
  - Local/SQLite (no DATABASE_URL): auth is a no-op; existing single-user flows
    continue to work. The middleware in main.py skips /api/ protection.
  - PostgreSQL/Railway (DATABASE_URL set): users register with email+password,
    receive a JWT (valid 7 days), and must include it on /api/ calls.

The JWT payload contains user_id, email, and role. Tokens are symmetric
(HS256) and require JWT_SECRET to verify -- set JWT_SECRET in env.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt

# In local/dev mode without a JWT_SECRET, generate one per-process so tokens
# at least work within a single run. Set JWT_SECRET in env for production.
JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 1 week

COOKIE_NAME = "qx_token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False  # corrupt/malformed hash


def create_token(user_id: int, email: str, role: str = "student",
                 name: Optional[str] = None) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "name": name or "",
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user(request) -> Optional[dict]:
    """Extract the user dict from an Authorization header or qx_token cookie.
    Returns None if unauthenticated or token invalid/expired."""
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        return None
    return verify_token(token)


def require_auth(request) -> dict:
    """Raise 401 if not authenticated. For protected route handlers."""
    from fastapi import HTTPException
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def require_instructor(request) -> dict:
    """Raise 403 if user is not instructor role."""
    from fastapi import HTTPException
    user = require_auth(request)
    if user.get("role") != "instructor":
        raise HTTPException(403, "Instructor access required")
    return user
