"""PostgreSQL database layer for QuantX Deployer (web/Railway mode).

Falls back to the existing SQLite database (api/database.py) when DATABASE_URL
is not set, so local development without Railway keeps working unchanged.

Anything importing from this module should use:
    from api.db_postgres import USE_POSTGRES, get_conn, init_db
to remain dual-mode compatible.
"""

from __future__ import annotations

import os
import logging

log = logging.getLogger("quantx-db-postgres")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    def get_conn():
        """Return a fresh PostgreSQL connection. Caller must close()."""
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

else:
    # Forward to the existing SQLite layer so single-function imports work.
    # Note: api.database exposes `get_db`, not `get_db_connection`.
    from api.database import get_db as get_conn  # noqa: F401


def init_db() -> None:
    """Create tables (PostgreSQL) or forward to SQLite init (local mode)."""
    if not USE_POSTGRES:
        from api.database import init_db as sqlite_init
        return sqlite_init()

    conn = get_conn()
    cur = conn.cursor()

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_login TIMESTAMPTZ
        )
    """)

    # Sessions (reserved for server-side revocation if needed later)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # OAuth state -- short-lived rows holding PKCE verifier + state across the redirect
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            broker TEXT NOT NULL DEFAULT 'longport',
            code_verifier TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL
        )
    """)

    # OAuth tokens (encrypted)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            broker TEXT NOT NULL DEFAULT 'longport',
            access_token_enc TEXT NOT NULL,
            refresh_token_enc TEXT,
            expires_at TIMESTAMPTZ,
            scope TEXT,
            account_id TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, broker)
        )
    """)

    # Broker accounts (manual-key mode still supported alongside OAuth)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS broker_accounts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            broker TEXT NOT NULL,
            account_type TEXT DEFAULT 'paper',
            account_id TEXT,
            nickname TEXT,
            app_key_enc TEXT,
            app_secret_enc TEXT,
            access_token_enc TEXT,
            oauth_connected BOOLEAN DEFAULT FALSE,
            is_connected INTEGER DEFAULT 0,
            last_tested TIMESTAMPTZ,
            last_error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, broker, account_type)
        )
    """)

    # Strategies
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id SERIAL PRIMARY KEY,
            strategy_id TEXT UNIQUE NOT NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            strategy_name TEXT,
            symbol TEXT,
            arena TEXT,
            timeframe TEXT,
            conditions_json TEXT,
            risk_json TEXT,
            is_active INTEGER DEFAULT 0,
            mode TEXT DEFAULT 'studio',
            broker TEXT DEFAULT 'longport',
            allocation TEXT DEFAULT '10000',
            backtest_results_json TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Bot processes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            strategy_id TEXT,
            pid INTEGER,
            status TEXT DEFAULT 'stopped',
            master_script_path TEXT,
            log_path TEXT,
            started_at TIMESTAMPTZ,
            stopped_at TIMESTAMPTZ,
            error_msg TEXT,
            last_heartbeat TIMESTAMPTZ
        )
    """)

    # Bot state (restart-recovery)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            strategy_id TEXT NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_id, strategy_id)
        )
    """)

    # Trades
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            strategy_id TEXT,
            symbol TEXT,
            side TEXT,
            price REAL,
            qty REAL,
            pnl REAL,
            cumulative_pnl REAL,
            timestamp TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    log.info("PostgreSQL tables initialized")
    print("[DB] PostgreSQL tables initialized")


def cleanup_expired_oauth_states() -> int:
    """Purge expired oauth_states rows. Returns count deleted. No-op in SQLite mode."""
    if not USE_POSTGRES:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM oauth_states WHERE expires_at < NOW()")
    n = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return n
