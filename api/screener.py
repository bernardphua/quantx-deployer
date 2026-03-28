"""QuantX Deployer — Two-phase stock screener for Famous Investor Bots."""

import sqlite3
import math
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))


# ── Helpers ──────────────────────────────────────────────────────────────────

def calc_sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def calc_ema(data, period):
    if len(data) < period:
        return None
    k = 2.0 / (period + 1)
    ema = sum(data[:period]) / period
    for p in data[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def calc_rsi(data, period=14):
    if len(data) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = data[i] - data[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    ag = gains / period
    al = losses / period
    for i in range(period + 1, len(data)):
        d = data[i] - data[i - 1]
        if d > 0:
            ag = (ag * (period - 1) + d) / period
            al = al * (period - 1) / period
        else:
            ag = ag * (period - 1) / period
            al = (al * (period - 1) - d) / period
    if al == 0:
        return 100
    return 100 - 100 / (1 + ag / al)


def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return None
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
           for i in range(1, len(closes))]
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def calc_zscore(data, period=20):
    if len(data) < period:
        return None
    d = data[-period:]
    mean = sum(d) / period
    std = (sum((x - mean) ** 2 for x in d) / period) ** 0.5
    return (d[-1] - mean) / std if std > 0 else 0


def calc_obv_trend(closes, volumes, period=10):
    if len(closes) < period + 1:
        return None
    obv = 0
    obvs = []
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv += volumes[i]
        elif closes[i] < closes[i - 1]:
            obv -= volumes[i]
        obvs.append(obv)
    if len(obvs) < period:
        return None
    recent = obvs[-period // 2:]
    older = obvs[-period:-period // 2]
    return sum(recent) / len(recent) > sum(older) / len(older) if older else None


def calc_macd_hist(closes, fast=12, slow=26):
    ef = calc_ema(closes, fast)
    es = calc_ema(closes, slow)
    if ef is None or es is None:
        return None
    return ef - es


# ── Fetch bars ───────────────────────────────────────────────────────────────

def fetch_daily_bars(quote_ctx, symbol, count=60):
    try:
        from longport.openapi import Period, AdjustType
        bars = quote_ctx.history_candlesticks_by_offset(symbol, Period.Day, AdjustType.NoAdjust, count)
        if not bars or len(bars) < 20:
            return None
        return {
            "closes": [float(b.close) for b in bars],
            "highs": [float(b.high) for b in bars],
            "lows": [float(b.low) for b in bars],
            "volumes": [float(b.volume) for b in bars],
        }
    except Exception as e:
        print(f"[SCREENER] {symbol}: {e}")
        return None


# ── Scoring ──────────────────────────────────────────────────────────────────

def score_buffett(bars):
    c, h, l, v = bars["closes"], bars["highs"], bars["lows"], bars["volumes"]
    score, reasons = 0, []
    price = c[-1]
    sma200 = calc_sma(c, min(200, len(c)))
    rsi14 = calc_rsi(c, 14)
    atr14 = calc_atr(h, l, c, 14)
    if sma200 and price > sma200:
        score += 1; reasons.append(f"Price > SMA200")
    sma50 = calc_sma(c, min(50, len(c)))
    if sma50 and price > sma50:
        score += 1; reasons.append(f"Price > SMA50")
    if rsi14 and 40 <= rsi14 <= 65:
        score += 1; reasons.append(f"RSI {rsi14:.0f} in fair zone")
    high52 = max(h[-min(252, len(h)):])
    if price >= high52 * 0.90:
        score += 1; reasons.append(f"Near 52w high")
    if calc_obv_trend(c, v):
        score += 1; reasons.append(f"OBV up (accumulation)")
    if atr14:
        avg_moves = calc_sma([abs(c[i] - c[i - 1]) for i in range(1, len(c))], 20)
        if avg_moves and atr14 < avg_moves * 1.3:
            score += 1; reasons.append(f"ATR calm")
    return score, 6, reasons


def score_graham(bars):
    c, h, l, v = bars["closes"], bars["highs"], bars["lows"], bars["volumes"]
    score, reasons = 0, []
    price = c[-1]
    rsi14 = calc_rsi(c, 14)
    low52 = min(l[-min(252, len(l)):])
    high52 = max(h[-min(252, len(h)):])
    prox = (price - low52) / low52 * 100 if low52 > 0 else 100
    decline = (high52 - price) / high52 * 100 if high52 > 0 else 0
    if prox <= 20:
        score += 1; reasons.append(f"Within 20% of low")
    if rsi14 and rsi14 < 40:
        score += 1; reasons.append(f"RSI {rsi14:.0f} oversold")
    sma200 = calc_sma(c, min(200, len(c)))
    if sma200 and price < sma200:
        score += 1; reasons.append(f"Below SMA200")
    if decline >= 15:
        score += 1; reasons.append(f"Down {decline:.0f}% from high")
    if len(v) >= 20:
        rv = sum(v[-5:]) / 5
        ov = sum(v[-20:-5]) / 15
        if rv < ov * 0.9:
            score += 1; reasons.append(f"Volume declining")
    atr_r = calc_atr(h[-15:], l[-15:], c[-15:], 10) if len(c) >= 15 else None
    atr_o = calc_atr(h[-30:-15], l[-30:-15], c[-30:-15], 10) if len(c) >= 30 else None
    if atr_r and atr_o and atr_r < atr_o:
        score += 1; reasons.append(f"ATR declining")
    return score, 6, reasons


def score_livermore(bars):
    c, h, l, v = bars["closes"], bars["highs"], bars["lows"], bars["volumes"]
    score, reasons = 0, []
    price = c[-1]
    avg_vol = sum(v[-20:]) / min(20, len(v))
    if len(h) >= 21 and price > max(h[-21:-1]):
        score += 1; reasons.append(f"New 20-bar high")
    if avg_vol > 0 and v[-1] > avg_vol * 1.5:
        score += 1; reasons.append(f"Volume surge")
    atr14 = calc_atr(h, l, c, 14)
    atr_old = calc_atr(h[:-5], l[:-5], c[:-5], 14) if len(c) > 20 else None
    if atr14 and atr_old and atr14 > atr_old:
        score += 1; reasons.append(f"ATR expanding")
    sma20 = calc_sma(c, 20)
    if sma20 and price > sma20:
        score += 1; reasons.append(f"Price > SMA20")
    rsi14 = calc_rsi(c, 14)
    if rsi14 and rsi14 > 55:
        score += 1; reasons.append(f"RSI {rsi14:.0f} momentum")
    if len(c) >= 2 and c[-1] > c[-2] * 1.002:
        score += 1; reasons.append(f"Gap up")
    return score, 6, reasons


def score_dalio(bars):
    c, h, l, v = bars["closes"], bars["highs"], bars["lows"], bars["volumes"]
    score, reasons = 0, []
    price = c[-1]
    sma50 = calc_sma(c, min(50, len(c)))
    rsi14 = calc_rsi(c, 14)
    atr14 = calc_atr(h, l, c, 14)
    if sma50 and price > sma50:
        score += 1; reasons.append(f"Price > SMA50")
    if rsi14 and 45 <= rsi14 <= 60:
        score += 1; reasons.append(f"RSI {rsi14:.0f} equilibrium")
    avg_m = calc_sma([abs(c[i] - c[i - 1]) for i in range(1, len(c))], 20)
    if atr14 and avg_m and atr14 < avg_m * 1.1:
        score += 1; reasons.append(f"ATR calm")
    avg_vol = sum(v[-20:]) / min(20, len(v))
    if avg_vol > 0 and 0.7 < v[-1] / avg_vol < 1.3:
        score += 1; reasons.append(f"Normal volume")
    sma50p = calc_sma(c[:-5], min(50, len(c) - 5))
    if sma50 and sma50p and sma50 > sma50p:
        score += 1; reasons.append(f"SMA50 rising")
    if calc_obv_trend(c, v):
        score += 1; reasons.append(f"OBV up")
    return score, 6, reasons


def score_simons(bars):
    c, h, l, v = bars["closes"], bars["highs"], bars["lows"], bars["volumes"]
    score, reasons = 0, []
    z = calc_zscore(c, min(20, len(c)))
    rsi14 = calc_rsi(c, 14)
    if z and z < -1.5:
        score += 1; reasons.append(f"Z-score {z:.2f}")
    if rsi14 and rsi14 < 35:
        score += 1; reasons.append(f"RSI {rsi14:.0f} oversold")
    if calc_obv_trend(c, v):
        score += 1; reasons.append(f"OBV positive")
    avg_vol = sum(v[-20:]) / min(20, len(v))
    if avg_vol > 0 and v[-1] < avg_vol * 0.8:
        score += 1; reasons.append(f"Low volume pullback")
    mean20 = calc_sma(c, min(20, len(c)))
    if mean20 and c[-1] < mean20 * 0.98:
        score += 1; reasons.append(f"Below 20d mean")
    atr14 = calc_atr(h, l, c, 14)
    avg_m = calc_sma([abs(c[i] - c[i - 1]) for i in range(1, len(c))], 20)
    if atr14 and avg_m and atr14 < avg_m:
        score += 1; reasons.append(f"ATR below avg")
    return score, 6, reasons


def score_turtle(bars):
    c, h, l, v = bars["closes"], bars["highs"], bars["lows"], bars["volumes"]
    score, reasons = 0, []
    price = c[-1]
    lb = min(55, len(h) - 1)
    if lb >= 10 and price > max(h[-lb - 1:-1]):
        score += 1; reasons.append(f"New {lb}-bar high")
    avg_vol = sum(v[-20:]) / min(20, len(v))
    if avg_vol > 0 and v[-1] > avg_vol * 1.2:
        score += 1; reasons.append(f"Volume confirmed")
    sma20 = calc_sma(c, 20)
    sma50 = calc_sma(c, min(50, len(c)))
    if sma20 and price > sma20:
        score += 1; reasons.append(f"Price > SMA20")
    if sma50 and price > sma50:
        score += 1; reasons.append(f"Price > SMA50")
    atr14 = calc_atr(h, l, c, 14)
    avg_m = calc_sma([abs(c[i] - c[i - 1]) for i in range(1, len(c))], 20)
    if atr14 and avg_m and atr14 > avg_m:
        score += 1; reasons.append(f"ATR expanding")
    rsi14 = calc_rsi(c, 14)
    if rsi14 and rsi14 > 50:
        score += 1; reasons.append(f"RSI {rsi14:.0f} positive")
    return score, 6, reasons


def score_soros(bars):
    c, h, l, v = bars["closes"], bars["highs"], bars["lows"], bars["volumes"]
    score, reasons = 0, []
    ema5 = calc_ema(c, min(5, len(c)))
    ema20 = calc_ema(c, min(20, len(c)))
    ema50 = calc_ema(c, min(50, len(c)))
    if ema5 and ema20 and ema50 and ema5 > ema20 > ema50:
        score += 1; reasons.append(f"Full EMA alignment")
    macd_h = calc_macd_hist(c)
    if macd_h and macd_h > 0:
        score += 1; reasons.append(f"MACD positive")
    avg_vol = sum(v[-20:]) / min(20, len(v))
    if avg_vol > 0 and v[-1] > avg_vol * 1.2:
        score += 1; reasons.append(f"Volume expanding")
    rsi14 = calc_rsi(c, 14)
    if rsi14 and 55 <= rsi14 <= 75:
        score += 1; reasons.append(f"RSI {rsi14:.0f} momentum zone")
    if len(c) >= 4 and all(c[i] > c[i - 1] for i in range(-3, 0)):
        score += 1; reasons.append(f"3 consecutive up days")
    atr14 = calc_atr(h, l, c, 14)
    avg_m = calc_sma([abs(c[i] - c[i - 1]) for i in range(1, len(c))], 20)
    if atr14 and avg_m and atr14 > avg_m:
        score += 1; reasons.append(f"ATR expanding")
    return score, 6, reasons


BOT_THRESHOLDS = {"BUFFETT_BOT": 4, "GRAHAM_BOT": 4, "LIVERMORE_BOT": 3, "DALIO_BOT": 4, "SIMONS_BOT": 3, "TURTLE_TRADER": 4, "SOROS_BOT": 4}
BOT_SCORERS = {"BUFFETT_BOT": score_buffett, "GRAHAM_BOT": score_graham, "LIVERMORE_BOT": score_livermore, "DALIO_BOT": score_dalio, "SIMONS_BOT": score_simons, "TURTLE_TRADER": score_turtle, "SOROS_BOT": score_soros}


def run_screener(quote_ctx, bot_type, universe, db_path, email, strategy_id):
    scorer = BOT_SCORERS.get(bot_type)
    threshold = BOT_THRESHOLDS.get(bot_type, 4)
    if not scorer:
        return {"error": f"Unknown bot type: {bot_type}"}
    now_sgt = datetime.now(SGT).strftime("%Y-%m-%d %H:%M SGT")
    results = []
    print(f"[SCREENER] Running {bot_type} on {len(universe)} stocks...")
    for symbol in universe:
        try:
            bars = fetch_daily_bars(quote_ctx, symbol, 60)
            if not bars:
                results.append({"symbol": symbol, "score": 0, "max_score": 6, "shortlisted": False, "reasons": ["No data"], "price": 0, "error": True})
                continue
            sc, mx, reasons = scorer(bars)
            results.append({"symbol": symbol, "score": sc, "max_score": mx, "shortlisted": sc >= threshold, "reasons": reasons, "price": bars["closes"][-1], "error": False})
            print(f"[SCREENER] {symbol}: {sc}/{mx} {'PASS' if sc >= threshold else ''}")
        except Exception as e:
            results.append({"symbol": symbol, "score": 0, "max_score": 6, "shortlisted": False, "reasons": [str(e)], "price": 0, "error": True})
    shortlisted = [r for r in results if r["shortlisted"]]
    _save_results(db_path, email, strategy_id, bot_type, results, now_sgt)
    print(f"[SCREENER] Done: {len(shortlisted)}/{len(universe)} shortlisted")
    return {"shortlisted": shortlisted, "all_scores": results, "run_at": now_sgt, "bot_type": bot_type, "threshold": threshold, "total_screened": len(universe), "total_shortlisted": len(shortlisted)}


def _save_results(db_path, email, strategy_id, bot_type, results, run_at):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS screener_results (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, strategy_id TEXT, bot_type TEXT, symbol TEXT, score INTEGER, max_score INTEGER, shortlisted INTEGER, reasons TEXT, price REAL, run_at TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("DELETE FROM screener_results WHERE email=? AND strategy_id=?", (email, strategy_id))
        for r in results:
            conn.execute("INSERT INTO screener_results (email,strategy_id,bot_type,symbol,score,max_score,shortlisted,reasons,price,run_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (email, strategy_id, bot_type, r["symbol"], r["score"], r["max_score"], int(r["shortlisted"]), ", ".join(r["reasons"]), r.get("price", 0), run_at))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SCREENER] Save failed: {e}")
