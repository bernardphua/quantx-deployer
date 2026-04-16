"""QuantX Data Manager — Waterfall data fetcher for backtests.
Priority: 1. Local SQLite cache → 2. LongPort → 3. IBKR → 4. R2 → 5. Yahoo → 6. FMP
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("quantx-data")

SOURCE_MESSAGES = {
    "local_cache": "Loading from local cache...",
    "ibkr": "Fetching from your IBKR account...",
    "longport": "Fetched from LongPort API (paginated history)",
    "r2": "Loading from QuantX data library...",
    "yahoo": "Fetching from Yahoo Finance...",
    "fmp": "Fetching from QuantX data server...",
    "none": "No data available for this symbol/timeframe.",
}

CACHE_TTL = {
    "1min": 3600, "5min": 3600, "15min": 14400, "30min": 14400,
    "1hour": 86400, "4hour": 86400, "1day": 86400 * 7, "1week": 86400 * 30,
}


# ── Local SQLite cache ────────────────────────────────────────────────────────

def init_data_cache(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS data_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            source TEXT NOT NULL,
            bar_count INTEGER DEFAULT 0,
            bars_json TEXT NOT NULL,
            fetched_at TEXT DEFAULT (datetime('now')),
            UNIQUE(symbol, timeframe)
        );
        CREATE INDEX IF NOT EXISTS idx_data_cache_sym ON data_cache(symbol, timeframe);
    """)
    conn.commit()


def load_from_local_cache(db_path, symbol, timeframe):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT bars_json, source, fetched_at FROM data_cache WHERE symbol=? AND timeframe=?",
            (symbol, timeframe)).fetchone()
        conn.close()
        if not row:
            return None
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        ttl = CACHE_TTL.get(timeframe, 86400)
        if (datetime.utcnow() - fetched_at).total_seconds() > ttl:
            log.info("Cache expired for %s/%s", symbol, timeframe)
            return None
        bars = json.loads(row["bars_json"])
        log.info("Cache hit: %s/%s — %d bars from %s", symbol, timeframe, len(bars), row["source"])
        return bars, "local_cache"
    except Exception as e:
        log.warning("Local cache read failed: %s", e)
        return None


def save_to_local_cache(db_path, symbol, timeframe, bars, source):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            """INSERT INTO data_cache (symbol, timeframe, source, bar_count, bars_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(symbol, timeframe) DO UPDATE SET
                 source=excluded.source, bar_count=excluded.bar_count,
                 bars_json=excluded.bars_json, fetched_at=excluded.fetched_at""",
            (symbol, timeframe, source, len(bars), json.dumps(bars)))
        conn.commit()
        conn.close()
        log.info("Saved %d bars for %s/%s to local cache (source: %s)", len(bars), symbol, timeframe, source)
    except Exception as e:
        log.warning("Local cache write failed: %s", e)


# ── IBKR data fetch ──────────────────────────────────────────────────────────

def fetch_from_ibkr(symbol, timeframe, limit, host="127.0.0.1", port=7497, client_id=99):
    try:
        import asyncio
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        from ib_insync import IB, Stock

        tf_map = {
            "1min": ("1 min", "1 D"), "5min": ("5 mins", "5 D"),
            "15min": ("15 mins", "10 D"), "30min": ("30 mins", "20 D"),
            "1hour": ("1 hour", "30 D"), "4hour": ("4 hours", "60 D"),
            "1day": ("1 day", "5 Y"), "1week": ("1 week", "10 Y"),
        }
        bar_size, duration = tf_map.get(timeframe, ("1 day", "5 Y"))
        if timeframe == "1day":
            duration = f"{max(1, min(20, limit // 252 + 1))} Y"

        ib = IB()
        ib.connect(host, port, clientId=client_id, timeout=10)
        if not ib.isConnected():
            return None

        if symbol.endswith(".HK"):
            contract = Stock(symbol.replace(".HK", ""), "SEHK", "HKD")
        elif symbol.endswith(".SI"):
            contract = Stock(symbol.replace(".SI", ""), "SGX", "SGD")
        elif symbol.endswith(".US"):
            contract = Stock(symbol.replace(".US", ""), "SMART", "USD")
        else:
            contract = Stock(symbol, "SMART", "USD")

        ib.qualifyContracts(contract)
        raw = ib.reqHistoricalData(contract, endDateTime="", durationStr=duration,
                                    barSizeSetting=bar_size, whatToShow="MIDPOINT",
                                    useRTH=True, formatDate=1)
        ib.disconnect()
        if not raw:
            return None
        bars = [{"date": str(b.date), "open": float(b.open), "high": float(b.high),
                 "low": float(b.low), "close": float(b.close),
                 "volume": float(b.volume) if b.volume != -1 else 0} for b in raw]
        if len(bars) > limit:
            bars = bars[-limit:]
        log.info("IBKR: %d bars for %s/%s", len(bars), symbol, timeframe)
        return bars
    except Exception as e:
        log.warning("IBKR fetch failed %s/%s: %s", symbol, timeframe, e)
        return None


# ── Yahoo Finance ─────────────────────────────────────────────────────────────

def fetch_from_yahoo(symbol, timeframe, limit):
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed. Run: pip install yfinance")
        return None
    try:
        yf_sym = symbol
        if symbol.endswith(".HK"):
            code = symbol.replace(".HK", "").zfill(4)
            yf_sym = f"{code}.HK"
        elif symbol.endswith(".US"):
            yf_sym = symbol.replace(".US", "")

        interval_map = {"1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
                        "1hour": "1h", "4hour": "1h", "1day": "1d", "1week": "1wk"}
        interval = interval_map.get(timeframe, "1d")

        if timeframe in ("1min", "5min", "15min", "30min"):
            period = "60d"
        elif timeframe in ("1hour", "4hour"):
            period = "730d"
        else:
            period = f"{max(1, min(25, limit // 252 + 1))}y"

        df = yf.Ticker(yf_sym).history(period=period, interval=interval, auto_adjust=True, actions=False)
        if df is None or len(df) == 0:
            return None

        bars = [{"date": str(idx)[:10], "open": round(float(row["Open"]), 4),
                 "high": round(float(row["High"]), 4), "low": round(float(row["Low"]), 4),
                 "close": round(float(row["Close"]), 4),
                 "volume": float(row.get("Volume", 0))}
                for idx, row in df.iterrows() if float(row["Close"]) > 0]
        if len(bars) > limit:
            bars = bars[-limit:]
        log.info("Yahoo: %d bars for %s/%s (yf: %s)", len(bars), symbol, timeframe, yf_sym)
        return bars
    except Exception as e:
        log.warning("Yahoo fetch failed %s/%s: %s", symbol, timeframe, e)
        return None


# ── LongPort data fetch ──────────────────────────────────────────────────────

def fetch_from_longport(symbol, timeframe, limit, lp_credentials):
    """Fetch OHLCV bars from LongPort using paginated history_candlesticks_by_offset.

    Uses del ctx (not .close()) to release the connection -- QuoteContext has no close().
    Max 1000 bars per page, up to 20 pages = 20,000 bars max.
    """
    try:
        from longport.openapi import Config, QuoteContext, Period, AdjustType
        from .config import normalize_timeframe

        tf = normalize_timeframe(timeframe)
        period_map = {
            "1min": Period.Min_1, "5min": Period.Min_5,
            "15min": Period.Min_15, "30min": Period.Min_30,
            "1hour": Period.Min_60, "1day": Period.Day, "1week": Period.Week,
        }
        period = period_map.get(tf)
        if period is None:
            log.warning("LongPort: unsupported timeframe %s (normalized: %s)", timeframe, tf)
            return None

        cfg = Config(
            app_key=lp_credentials["app_key"],
            app_secret=lp_credentials["app_secret"],
            access_token=lp_credentials["access_token"],
        )
        ctx = QuoteContext(cfg)

        try:
            all_candles = []
            anchor_time = None
            max_pages = 20

            for page in range(max_pages):
                batch = ctx.history_candlesticks_by_offset(
                    symbol, period, AdjustType.ForwardAdjust,
                    forward=False, count=1000, time=anchor_time,
                )
                if not batch:
                    break

                all_candles = list(batch) + all_candles  # prepend older data

                if len(batch) < 1000:
                    break  # reached beginning of available data

                anchor_time = batch[0].timestamp

                if len(all_candles) >= limit:
                    break
        finally:
            del ctx  # correct way to release QuoteContext -- no .close() method

        if not all_candles:
            return None

        bars = []
        for c in all_candles:
            ts = c.timestamp
            date_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)[:19]
            bars.append({
                "date": date_str,
                "open": round(float(c.open), 4),
                "high": round(float(c.high), 4),
                "low": round(float(c.low), 4),
                "close": round(float(c.close), 4),
                "volume": float(c.volume) if hasattr(c, "volume") else 0.0,
            })

        if len(bars) > limit:
            bars = bars[-limit:]

        log.info("LongPort: %d bars for %s/%s | %s -> %s",
                 len(bars), symbol, timeframe,
                 bars[0]["date"][:10] if bars else "?",
                 bars[-1]["date"][:10] if bars else "?")
        return bars

    except Exception as e:
        log.warning("LongPort fetch failed %s/%s: %s", symbol, timeframe, e)
        return None


# ── Main waterfall ────────────────────────────────────────────────────────────

def fetch_bars_waterfall_sync(symbol, timeframe, limit, db_path,
                               ibkr_config=None, lp_credentials=None,
                               skip_cache=False):
    """Synchronous waterfall fetch — call from executor thread."""
    from .config import normalize_timeframe
    symbol = symbol.upper().strip()
    timeframe = normalize_timeframe(timeframe)
    base = {"symbol": symbol, "timeframe": timeframe, "bars": [],
            "source": None, "source_message": "", "bar_count": 0, "error": None}

    # 1. Local cache — only use if it has enough bars for what was requested
    if not skip_cache:
        cached = load_from_local_cache(db_path, symbol, timeframe)
        if cached:
            bars, src = cached
            if len(bars) >= limit:
                return {**base, "bars": bars[-limit:], "source": src,
                        "source_message": SOURCE_MESSAGES["local_cache"], "bar_count": len(bars)}
            elif len(bars) >= 50:
                log.info("Cache has %d bars but %d requested -- re-fetching for more data",
                         len(bars), limit)

    # 2. LongPort (if credentials provided)
    if lp_credentials and lp_credentials.get("app_key"):
        log.info("Trying LongPort for %s/%s...", symbol, timeframe)
        bars = fetch_from_longport(symbol, timeframe, limit, lp_credentials)
        if bars and len(bars) >= 20:
            save_to_local_cache(db_path, symbol, timeframe, bars, "longport")
            return {**base, "bars": bars, "source": "longport",
                    "source_message": SOURCE_MESSAGES["longport"], "bar_count": len(bars)}
        log.warning("LongPort fetch returned insufficient data for %s/%s -- falling through", symbol, timeframe)

    # 3. IBKR
    if ibkr_config and ibkr_config.get("host"):
        log.info("Trying IBKR for %s/%s...", symbol, timeframe)
        bars = fetch_from_ibkr(symbol, timeframe, limit,
                                host=ibkr_config.get("host", "127.0.0.1"),
                                port=int(ibkr_config.get("port", 7497)),
                                client_id=int(ibkr_config.get("client_id", 99)))
        if bars and len(bars) >= 20:
            save_to_local_cache(db_path, symbol, timeframe, bars, "ibkr")
            return {**base, "bars": bars, "source": "ibkr",
                    "source_message": SOURCE_MESSAGES["ibkr"], "bar_count": len(bars)}

    # 4. R2
    log.info("Trying R2 for %s/%s...", symbol, timeframe)
    try:
        from .backtest import load_from_r2
        r2_result = load_from_r2(symbol, timeframe)
        if r2_result:
            bars, _ = r2_result
            if bars and len(bars) >= 20:
                trimmed = bars[-limit:] if len(bars) > limit else bars
                save_to_local_cache(db_path, symbol, timeframe, trimmed, "r2")
                return {**base, "bars": trimmed, "source": "r2",
                        "source_message": SOURCE_MESSAGES["r2"], "bar_count": len(trimmed)}
    except Exception as e:
        log.warning("R2 failed: %s", e)

    # 5. Yahoo Finance
    log.info("Trying Yahoo for %s/%s...", symbol, timeframe)
    bars = fetch_from_yahoo(symbol, timeframe, limit)
    if bars and len(bars) >= 20:
        save_to_local_cache(db_path, symbol, timeframe, bars, "yahoo")
        return {**base, "bars": bars, "source": "yahoo",
                "source_message": SOURCE_MESSAGES["yahoo"], "bar_count": len(bars)}

    # 6. FMP
    log.info("Trying FMP for %s/%s...", symbol, timeframe)
    try:
        from .backtest import _fetch_from_fmp
        bars, src = _fetch_from_fmp(symbol, timeframe, limit)
        if bars and len(bars) >= 20:
            save_to_local_cache(db_path, symbol, timeframe, bars, "fmp")
            return {**base, "bars": bars, "source": "fmp",
                    "source_message": SOURCE_MESSAGES["fmp"], "bar_count": len(bars)}
    except Exception as e:
        log.warning("FMP failed: %s", e)

    # No data
    is_intraday_hk_sg = timeframe not in ("1day", "1week") and (symbol.endswith(".HK") or symbol.endswith(".SI"))
    error = (f"No intraday data for {symbol}/{timeframe}. Connect IBKR for HK/SG intraday."
             if is_intraday_hk_sg else
             f"No data for {symbol}/{timeframe}. Check symbol format (700.HK, D05.SI, AAPL.US).")
    return {**base, "source": "none", "source_message": SOURCE_MESSAGES["none"], "error": error}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_cached_symbols(db_path):
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT symbol, timeframe, source, bar_count, fetched_at FROM data_cache ORDER BY fetched_at DESC"
        ).fetchall()
        conn.close()
        return [{"symbol": r[0], "timeframe": r[1], "source": r[2], "bars": r[3], "fetched_at": r[4]} for r in rows]
    except Exception:
        return []


def clear_cached_symbol(db_path, symbol, timeframe=None):
    try:
        conn = sqlite3.connect(db_path)
        if timeframe:
            conn.execute("DELETE FROM data_cache WHERE symbol=? AND timeframe=?", (symbol, timeframe))
        else:
            conn.execute("DELETE FROM data_cache WHERE symbol=?", (symbol,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("Cache clear failed: %s", e)
