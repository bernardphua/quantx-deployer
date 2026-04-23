"""QuantX Deployer — Centralized configuration.
Works on both Windows VPS and Railway Linux.

Architecture:
  RAILWAY (remote) = backtesting only (FMP data, R2 cache)
  LOCAL            = everything else (deploy, trade, broker, logs)
"""

import os
import sys
from pathlib import Path

# Load .env file if it exists (for student installs)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# Base directory
BASE_DIR = Path(os.environ.get("APP_BASE_DIR", str(Path(__file__).parent.parent)))

# Data directory — use Railway volume or local
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR)))

# Database
DB_PATH = os.environ.get("DB_PATH", str(DATA_DIR / "quantx_deployer.db"))

# Key file for Fernet encryption
KEY_FILE = str(DATA_DIR / ".fernet.key")

# Fernet key from env (Railway) or file (VPS)
FERNET_KEY = os.environ.get("FERNET_KEY", "")

# Generated scripts and logs
BOTS_DIR = DATA_DIR / "bots"
LOGS_DIR = DATA_DIR / "logs"
TRADES_DIR = DATA_DIR / "trades"
STATE_DIR = DATA_DIR / "state"

# ── Architecture split ──────────────────────────────────────────────────────
# Railway (remote) — backtesting only
CENTRAL_API_URL = os.environ.get("CENTRAL_API_URL", "")
BACKTEST_URL = CENTRAL_API_URL  # all backtest calls route here when set

# Local — everything else (deploy, stop, strategies, trades, logs, brokers)
LOCAL_API_PORT = int(os.environ.get("PORT", 8080))

# Admin
ADMIN_PIN = os.environ.get("ADMIN_PIN", "quantx2025")

# Hosting mode. Explicit HOSTING env var wins; otherwise auto-detect Railway
# via the RAILWAY_ENVIRONMENT var Railway injects automatically.
HOSTING = os.environ.get("HOSTING") or (
    "railway" if os.environ.get("RAILWAY_ENVIRONMENT") else "vps"
)

# FMP API
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")

# Version
VERSION = "1.2.0"

# Dev mode (enables --reload in run.py)
DEV_MODE = os.environ.get("DEV_MODE", "0") == "1"


# ── Timeframe normalization ────────────────────────────────────────────────
# DB stores "1m", "5m", "1h", "1d" but data APIs need "1min", "5min", "1hour", "1day"

_TF_MAP = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1hour", "4h": "4hour", "1d": "1day", "1w": "1week",
    # Already canonical — pass through
    "1min": "1min", "5min": "5min", "15min": "15min", "30min": "30min",
    "1hour": "1hour", "4hour": "4hour", "1day": "1day", "1week": "1week",
    # Extra variants
    "60m": "1hour", "60min": "1hour", "240m": "4hour", "daily": "1day",
    "weekly": "1week", "d": "1day", "w": "1week",
}


def normalize_timeframe(tf: str) -> str:
    """Map any timeframe string to the canonical format used by data APIs.

    Examples: "1m" -> "1min", "1h" -> "1hour", "1d" -> "1day"
    """
    return _TF_MAP.get(tf.lower().strip(), tf)

# Python executable
PYTHON_EXE = sys.executable

# Ensure directories exist
BOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TRADES_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
