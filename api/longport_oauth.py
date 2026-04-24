"""LongPort OAuth2 integration for QuantX web app.

Flow:
  1. GET /api/auth/longport/start       -> return authorize_url + set oauth_state row
  2. GET /callback/longport?code=&state -> exchange code for tokens, store encrypted
  3. Access tokens auto-refresh via refresh_access_token() when within 5 min of expiry

Registered client:
  client_id: 81d2945e-f0b0-4eda-89a8-ca8677ebea1d
  redirect_uri: https://quantxdeployer.railway.app/callback/longport
               (also: http://localhost:8080/callback/longport for dev)
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

import requests
from cryptography.fernet import Fernet

log = logging.getLogger("quantx-longport-oauth")

LONGPORT_CLIENT_ID = os.environ.get(
    "LONGPORT_OAUTH_CLIENT_ID",
    "81d2945e-f0b0-4eda-89a8-ca8677ebea1d",
)
LONGPORT_AUTHORIZE_URL = "https://openapi.longbridge.com/oauth2/authorize"
LONGPORT_TOKEN_URL = "https://openapi.longbridge.com/oauth2/token"

# Running on Railway sets RAILWAY_ENVIRONMENT automatically.
IS_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
REDIRECT_URI = os.environ.get(
    "LONGPORT_OAUTH_REDIRECT_URI",
    "https://quantxdeployer.railway.app/callback/longport"
    if IS_RAILWAY
    else "http://localhost:8080/callback/longport",
)

# Fernet key for encrypting OAuth tokens at rest. Set TOKEN_ENCRYPTION_KEY in env.
# On first run without a key we generate one and log a warning -- tokens will not
# survive a restart in that case (Fernet will reject encrypted-with-old-key blobs).
_TOKEN_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY", "")


def _coerce_fernet_key(raw: str) -> bytes:
    """Accept either a proper Fernet key (44 chars url-safe base64) or any string
    padded/truncated to fit. Proper keys should be generated with Fernet.generate_key()."""
    if not raw:
        raw = Fernet.generate_key().decode()
        log.warning("TOKEN_ENCRYPTION_KEY not set. Generated ephemeral key: %s", raw)
        log.warning("Tokens will NOT survive restart. Set TOKEN_ENCRYPTION_KEY in env.")
    if len(raw) == 44 and raw.endswith("="):
        return raw.encode()
    # Pad or truncate to 32 raw bytes, then base64-encode for Fernet
    data = raw.encode()[:32].ljust(32, b"\0")
    return base64.urlsafe_b64encode(data)


_fernet = Fernet(_coerce_fernet_key(_TOKEN_KEY))


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(enc: str) -> str:
    return _fernet.decrypt(enc.encode()).decode()


# ── PKCE + authorize-URL helpers ──────────────────────────────────────────────
def generate_pkce() -> Tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def get_authorize_url(state: str, code_challenge: str, scope: str = "3") -> str:
    """Build the LongPort OAuth2 authorization URL. scope '3' = read + trade."""
    import urllib.parse
    params = {
        "response_type": "code",
        "client_id": LONGPORT_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{LONGPORT_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str, code_verifier: str) -> dict:
    resp = requests.post(
        LONGPORT_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": LONGPORT_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": code_verifier,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    resp = requests.post(
        LONGPORT_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": LONGPORT_CLIENT_ID,
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ── OAuth-state table ops (PKCE verifier lives between /start and /callback) ──
def save_oauth_state(user_id: int, state: str, code_verifier: str,
                     ttl_minutes: int = 10) -> None:
    from api.db_postgres import get_conn, USE_POSTGRES
    if not USE_POSTGRES:
        raise RuntimeError("LongPort OAuth requires PostgreSQL (DATABASE_URL)")
    expires = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO oauth_states (state, user_id, broker, code_verifier, expires_at)
        VALUES (%s, %s, 'longport', %s, %s)
        ON CONFLICT (state) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            code_verifier = EXCLUDED.code_verifier,
            expires_at = EXCLUDED.expires_at
    """, (state, user_id, code_verifier, expires))
    conn.commit()
    cur.close()
    conn.close()


def consume_oauth_state(state: str) -> Optional[dict]:
    """Fetch and delete the oauth_states row matching `state`. Returns the
    row dict (with code_verifier + user_id) or None if missing/expired."""
    from api.db_postgres import get_conn, USE_POSTGRES
    if not USE_POSTGRES:
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM oauth_states
        WHERE state = %s AND expires_at > NOW()
        RETURNING user_id, code_verifier
    """, (state,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(row) if row else None


# ── Token storage + retrieval ────────────────────────────────────────────────
def store_tokens(user_id: int, tokens: dict) -> None:
    from api.db_postgres import get_conn, USE_POSTGRES
    if not USE_POSTGRES:
        raise RuntimeError("LongPort OAuth token storage requires PostgreSQL")
    access_enc = encrypt_token(tokens["access_token"])
    refresh_enc = encrypt_token(tokens.get("refresh_token", "")) if tokens.get("refresh_token") else None
    expires_at = datetime.utcnow() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    scope = str(tokens.get("scope", ""))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO oauth_tokens (user_id, broker, access_token_enc,
                                  refresh_token_enc, expires_at, scope)
        VALUES (%s, 'longport', %s, %s, %s, %s)
        ON CONFLICT (user_id, broker) DO UPDATE SET
            access_token_enc = EXCLUDED.access_token_enc,
            refresh_token_enc = EXCLUDED.refresh_token_enc,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            updated_at = NOW()
    """, (user_id, access_enc, refresh_enc, expires_at, scope))
    # Mirror into broker_accounts so the Brokers UI shows "connected"
    cur.execute("""
        INSERT INTO broker_accounts (user_id, email, broker, account_type,
                                     oauth_connected, is_connected)
        SELECT u.id, u.email, 'longport', 'paper', TRUE, 1
        FROM users u WHERE u.id = %s
        ON CONFLICT (user_id, broker, account_type) DO UPDATE SET
            oauth_connected = TRUE, is_connected = 1
    """, (user_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_access_token(user_id: int) -> Optional[str]:
    """Return a valid access token, refreshing if within 5 minutes of expiry."""
    from api.db_postgres import get_conn, USE_POSTGRES
    if not USE_POSTGRES:
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT access_token_enc, refresh_token_enc, expires_at
        FROM oauth_tokens WHERE user_id = %s AND broker = 'longport'
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    if row["expires_at"] and row["expires_at"] > datetime.utcnow() + timedelta(minutes=5):
        return decrypt_token(row["access_token_enc"])
    if not row["refresh_token_enc"]:
        return None
    try:
        refresh_tok = decrypt_token(row["refresh_token_enc"])
        new_tokens = refresh_access_token(refresh_tok)
        store_tokens(user_id, new_tokens)
        return new_tokens["access_token"]
    except Exception as e:
        log.warning("Token refresh failed for user %s: %s", user_id, e)
        return None


def get_token_status(user_id: int) -> dict:
    """Return {connected, expires_at, account_id} without side effects."""
    from api.db_postgres import get_conn, USE_POSTGRES
    if not USE_POSTGRES:
        return {"connected": False, "reason": "postgres_not_configured"}
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT expires_at, account_id FROM oauth_tokens
        WHERE user_id = %s AND broker = 'longport'
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"connected": False}
    return {
        "connected": True,
        "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
        "account_id": row["account_id"],
    }


def disconnect(user_id: int) -> None:
    from api.db_postgres import get_conn, USE_POSTGRES
    if not USE_POSTGRES:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM oauth_tokens WHERE user_id = %s AND broker = 'longport'", (user_id,))
    cur.execute("""
        UPDATE broker_accounts SET oauth_connected = FALSE, is_connected = 0
        WHERE user_id = %s AND broker = 'longport'
    """, (user_id,))
    conn.commit()
    cur.close()
    conn.close()
