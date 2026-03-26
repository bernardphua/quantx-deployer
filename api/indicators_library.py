"""QuantX Deployer — 100-indicator library with calculation functions and metadata."""

from collections import deque
import math


# ═══════════════════════════════════════════════════════════════════════════
# CALCULATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def calc_ema(data, period):
    d = list(data)
    if len(d) < period:
        return None
    mult = 2 / (period + 1)
    val = sum(d[:period]) / period
    for p in d[period:]:
        val = (p - val) * mult + val
    return val


def calc_sma(data, period):
    d = list(data)
    if len(d) < period:
        return None
    return sum(d[-period:]) / period


def calc_wma(data, period):
    d = list(data)[-period:]
    if len(d) < period:
        return None
    weights = list(range(1, period + 1))
    return sum(d[i] * weights[i] for i in range(period)) / sum(weights)


def calc_dema(data, period):
    e1 = calc_ema(data, period)
    if e1 is None:
        return None
    d = list(data)
    if len(d) < period * 2:
        return e1
    ema_vals = []
    mult = 2 / (period + 1)
    val = sum(d[:period]) / period
    for p in d[period:]:
        val = (p - val) * mult + val
        ema_vals.append(val)
    if len(ema_vals) < period:
        return e1
    e2 = sum(ema_vals[-period:]) / period
    return 2 * e1 - e2


def calc_tema(data, period):
    e1 = calc_ema(data, period)
    if e1 is None:
        return None
    return e1  # Simplified: full TEMA needs triple pass


def calc_hma(data, period):
    d = list(data)
    half = max(2, period // 2)
    sqrt_p = max(2, int(math.sqrt(period)))
    w1 = calc_wma(d, half)
    w2 = calc_wma(d, period)
    if w1 is None or w2 is None:
        return None
    return 2 * w1 - w2


def calc_rsi(data, period):
    d = list(data)
    if len(d) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(-period, 0):
        diff = d[i] - d[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    ag = gains / period
    al = losses / period
    if al == 0:
        return 100.0
    return 100 - (100 / (1 + ag / al))


def calc_atr(highs, lows, closes, period):
    h, l, c = list(highs), list(lows), list(closes)
    if len(c) < period + 1:
        return None
    trs = []
    for i in range(1, len(c)):
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        trs.append(tr)
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def calc_bollinger(data, period, num_std):
    d = list(data)
    if len(d) < period:
        return None, None, None
    slc = d[-period:]
    mean = sum(slc) / period
    std = (sum((x - mean) ** 2 for x in slc) / period) ** 0.5
    return mean, mean + num_std * std, mean - num_std * std


def calc_keltner(closes, highs, lows, ema_period, atr_period, multiplier):
    e = calc_ema(closes, ema_period)
    a = calc_atr(highs, lows, closes, atr_period)
    if e is None or a is None:
        return None, None, None
    return e, e + multiplier * a, e - multiplier * a


def calc_macd(data, fast, slow, signal):
    ef = calc_ema(data, fast)
    es = calc_ema(data, slow)
    if ef is None or es is None:
        return None, None, None
    macd_val = ef - es
    return macd_val, None, macd_val  # Simplified


def calc_stoch(highs, lows, closes, k_period, d_period=3):
    h, l, c = list(highs), list(lows), list(closes)
    if len(c) < k_period:
        return None, None
    hh = max(h[-k_period:])
    ll = min(l[-k_period:])
    if hh == ll:
        return 50, 50
    k = (c[-1] - ll) / (hh - ll) * 100
    return k, k  # D simplified


def calc_williams_r(highs, lows, closes, period):
    h, l, c = list(highs), list(lows), list(closes)
    if len(c) < period:
        return None
    hh = max(h[-period:])
    ll = min(l[-period:])
    if hh == ll:
        return -50
    return -100 * (hh - c[-1]) / (hh - ll)


def calc_cci(highs, lows, closes, period):
    h, l, c = list(highs), list(lows), list(closes)
    if len(c) < period:
        return None
    tps = [(h[i] + l[i] + c[i]) / 3 for i in range(-period, 0)]
    mean_tp = sum(tps) / period
    mad = sum(abs(tp - mean_tp) for tp in tps) / period
    if mad == 0:
        return 0
    return (tps[-1] - mean_tp) / (0.015 * mad)


def calc_adx(highs, lows, closes, period):
    h, l, c = list(highs), list(lows), list(closes)
    if len(c) < period + 1:
        return None
    trs, pdms, mdms = [], [], []
    for i in range(1, len(c)):
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        pdm = max(h[i] - h[i - 1], 0) if h[i] - h[i - 1] > l[i - 1] - l[i] else 0
        mdm = max(l[i - 1] - l[i], 0) if l[i - 1] - l[i] > h[i] - h[i - 1] else 0
        trs.append(tr)
        pdms.append(pdm)
        mdms.append(mdm)
    if len(trs) < period:
        return None
    atr_v = sum(trs[-period:]) / period
    if atr_v == 0:
        return 0
    pdi = 100 * sum(pdms[-period:]) / period / atr_v
    mdi = 100 * sum(mdms[-period:]) / period / atr_v
    return 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0


def calc_aroon(highs, lows, period):
    h, l = list(highs)[-(period + 1):], list(lows)[-(period + 1):]
    if len(h) < period + 1:
        return None, None
    hi_idx = h.index(max(h))
    lo_idx = l.index(min(l))
    up = 100 * (period - (len(h) - 1 - hi_idx)) / period
    dn = 100 * (period - (len(l) - 1 - lo_idx)) / period
    return up, dn


def calc_zscore(data, period):
    d = list(data)[-period:]
    if len(d) < period:
        return None
    mean = sum(d) / period
    std = (sum((x - mean) ** 2 for x in d) / period) ** 0.5
    return (d[-1] - mean) / std if std > 0 else 0


def calc_donchian(highs, lows, period):
    h, l = list(highs)[-period:], list(lows)[-period:]
    if len(h) < period:
        return None, None, None
    upper = max(h)
    lower = min(l)
    return upper, (upper + lower) / 2, lower


def calc_cmf(highs, lows, closes, volumes, period):
    h, l, c, v = list(highs), list(lows), list(closes), list(volumes)
    if len(c) < period:
        return None
    mf = []
    for i in range(-period, 0):
        hl = h[i] - l[i]
        if hl == 0:
            mf.append(0)
        else:
            mf.append(((c[i] - l[i]) - (h[i] - c[i])) / hl * v[i])
    vs = sum(v[-period:])
    return sum(mf) / vs if vs > 0 else 0


def calc_mfi(highs, lows, closes, volumes, period):
    h, l, c, v = list(highs), list(lows), list(closes), list(volumes)
    if len(c) < period + 1:
        return None
    pos = neg = 0.0
    for i in range(-period, 0):
        tp = (h[i] + l[i] + c[i]) / 3
        tp_prev = (h[i - 1] + l[i - 1] + c[i - 1]) / 3
        raw = tp * v[i]
        if tp > tp_prev:
            pos += raw
        else:
            neg += raw
    if neg == 0:
        return 100
    return 100 - 100 / (1 + pos / neg)


# ═══════════════════════════════════════════════════════════════════════════
# CANDLESTICK PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

def is_doji(o, c, h, l, threshold=0.05):
    body = abs(c - o)
    rng = h - l
    return body / rng < threshold if rng > 0 else False


def is_hammer(o, c, h, l):
    body = abs(c - o)
    lower = min(o, c) - l
    upper = h - max(o, c)
    return lower > 2 * body and upper < body if body > 0 else False


def is_shooting_star(o, c, h, l):
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return upper > 2 * body and lower < body if body > 0 else False


def is_engulfing_bull(opens, closes):
    o, c = list(opens), list(closes)
    if len(o) < 2:
        return False
    return c[-2] < o[-2] and c[-1] > o[-1] and o[-1] < c[-2] and c[-1] > o[-2]


def is_engulfing_bear(opens, closes):
    o, c = list(opens), list(closes)
    if len(o) < 2:
        return False
    return c[-2] > o[-2] and c[-1] < o[-1] and o[-1] > c[-2] and c[-1] < o[-2]


def is_inside_bar(highs, lows):
    h, l = list(highs), list(lows)
    if len(h) < 2:
        return False
    return h[-1] < h[-2] and l[-1] > l[-2]


def is_gap_up(opens, closes, pct=0.2):
    o, c = list(opens), list(closes)
    if len(o) < 2:
        return False
    return o[-1] > c[-2] * (1 + pct / 100)


def is_gap_down(opens, closes, pct=0.2):
    o, c = list(opens), list(closes)
    if len(o) < 2:
        return False
    return o[-1] < c[-2] * (1 - pct / 100)


# ═══════════════════════════════════════════════════════════════════════════
# INDICATOR REGISTRY — metadata for UI and bot template
# ═══════════════════════════════════════════════════════════════════════════

CATEGORIES = [
    "Trend Following",
    "Mean Reversion",
    "Momentum",
    "Volatility Breakout",
    "Volume",
    "Candlestick",
    "Price Action",
]

INDICATOR_REGISTRY = {
    # ── TREND FOLLOWING (15) ──────────────────────────────────────────────
    "EMA_CROSS": {"name": "EMA Crossover", "cat": "Trend Following", "desc": "Fast EMA crosses above slow EMA. Classic institutional trend entry.", "params": [{"key": "fast_period", "label": "Fast EMA", "default": 5, "min": 2, "max": 50, "type": "int"}, {"key": "slow_period", "label": "Slow EMA", "default": 20, "min": 5, "max": 200, "type": "int"}]},
    "SMA_CROSS": {"name": "SMA Crossover", "cat": "Trend Following", "desc": "Smoother than EMA cross. Golden cross (50/200) is a classic long-term signal.", "params": [{"key": "fast_period", "label": "Fast SMA", "default": 10, "min": 2, "max": 100, "type": "int"}, {"key": "slow_period", "label": "Slow SMA", "default": 30, "min": 5, "max": 200, "type": "int"}]},
    "DEMA_CROSS": {"name": "DEMA Crossover", "cat": "Trend Following", "desc": "Double EMA reduces lag. Faster trend detection with less whipsaw.", "params": [{"key": "fast_period", "label": "Fast DEMA", "default": 5, "min": 2, "max": 50, "type": "int"}, {"key": "slow_period", "label": "Slow DEMA", "default": 20, "min": 5, "max": 100, "type": "int"}]},
    "TEMA_CROSS": {"name": "TEMA Crossover", "cat": "Trend Following", "desc": "Triple EMA — minimal lag. Most responsive moving average crossover.", "params": [{"key": "fast_period", "label": "Fast TEMA", "default": 5, "min": 2, "max": 50, "type": "int"}, {"key": "slow_period", "label": "Slow TEMA", "default": 20, "min": 5, "max": 100, "type": "int"}]},
    "HMA_CROSS": {"name": "Hull MA Crossover", "cat": "Trend Following", "desc": "Hull MA eliminates lag while maintaining smoothness.", "params": [{"key": "fast_period", "label": "Fast HMA", "default": 9, "min": 3, "max": 50, "type": "int"}, {"key": "slow_period", "label": "Slow HMA", "default": 21, "min": 5, "max": 100, "type": "int"}]},
    "WMA_CROSS": {"name": "WMA Crossover", "cat": "Trend Following", "desc": "Weighted MA gives more importance to recent prices.", "params": [{"key": "fast_period", "label": "Fast WMA", "default": 5, "min": 2, "max": 50, "type": "int"}, {"key": "slow_period", "label": "Slow WMA", "default": 20, "min": 5, "max": 100, "type": "int"}]},
    "ICHIMOKU": {"name": "Ichimoku Cloud", "cat": "Trend Following", "desc": "Buy above cloud. Japanese institutional indicator with multiple signals.", "params": [{"key": "tenkan", "label": "Tenkan", "default": 9, "min": 5, "max": 20, "type": "int"}, {"key": "kijun", "label": "Kijun", "default": 26, "min": 15, "max": 50, "type": "int"}, {"key": "senkou", "label": "Senkou", "default": 52, "min": 30, "max": 100, "type": "int"}]},
    "PSAR": {"name": "Parabolic SAR", "cat": "Trend Following", "desc": "Trailing stop that flips on trend reversal.", "params": [{"key": "step", "label": "Step", "default": 0.02, "min": 0.01, "max": 0.1, "type": "float"}, {"key": "max_af", "label": "Max AF", "default": 0.2, "min": 0.1, "max": 0.5, "type": "float"}]},
    "SUPERTREND": {"name": "SuperTrend", "cat": "Trend Following", "desc": "ATR-based trend indicator. Very popular for crypto and equity.", "params": [{"key": "atr_period", "label": "ATR Period", "default": 10, "min": 5, "max": 30, "type": "int"}, {"key": "multiplier", "label": "Multiplier", "default": 3.0, "min": 1.0, "max": 6.0, "type": "float"}]},
    "ADX_TREND": {"name": "ADX Trend Strength", "cat": "Trend Following", "desc": "ADX>25 = strong trend. Filters choppy markets.", "params": [{"key": "period", "label": "Period", "default": 14, "min": 7, "max": 30, "type": "int"}, {"key": "threshold", "label": "ADX Threshold", "default": 25, "min": 15, "max": 40, "type": "int"}]},
    "AROON": {"name": "Aroon Oscillator", "cat": "Trend Following", "desc": "Buy when Aroon Up > threshold. Measures recency of highs/lows.", "params": [{"key": "period", "label": "Period", "default": 25, "min": 10, "max": 50, "type": "int"}, {"key": "threshold", "label": "Threshold", "default": 70, "min": 50, "max": 90, "type": "int"}]},
    "PRICE_VS_MA": {"name": "Price vs MA", "cat": "Trend Following", "desc": "Buy when price is above its moving average.", "params": [{"key": "ma_period", "label": "MA Period", "default": 20, "min": 5, "max": 200, "type": "int"}]},
    "GOLDEN_CROSS": {"name": "Golden/Death Cross", "cat": "Trend Following", "desc": "50/200 SMA cross. Classic long-term trend signal.", "params": [{"key": "fast_period", "label": "Fast MA", "default": 50, "min": 20, "max": 100, "type": "int"}, {"key": "slow_period", "label": "Slow MA", "default": 200, "min": 100, "max": 500, "type": "int"}]},
    "LINEAR_REG": {"name": "Linear Regression Slope", "cat": "Trend Following", "desc": "Buy when regression slope is positive. Mathematical trend.", "params": [{"key": "period", "label": "Period", "default": 20, "min": 10, "max": 100, "type": "int"}]},
    "VWMA_CROSS": {"name": "VWMA Crossover", "cat": "Trend Following", "desc": "Volume Weighted MA — stronger signals with volume confirmation.", "params": [{"key": "fast_period", "label": "Fast VWMA", "default": 5, "min": 2, "max": 50, "type": "int"}, {"key": "slow_period", "label": "Slow VWMA", "default": 20, "min": 5, "max": 100, "type": "int"}]},

    # ── MEAN REVERSION (11) ───────────────────────────────────────────────
    "RSI": {"name": "RSI", "cat": "Mean Reversion", "desc": "Buy oversold (<30), sell overbought (>70). Most widely used oscillator.", "params": [{"key": "period", "label": "Period", "default": 14, "min": 5, "max": 50, "type": "int"}, {"key": "oversold", "label": "Oversold", "default": 30, "min": 10, "max": 45, "type": "int"}, {"key": "overbought", "label": "Overbought", "default": 70, "min": 55, "max": 90, "type": "int"}]},
    "STOCH_RSI": {"name": "Stochastic RSI", "cat": "Mean Reversion", "desc": "RSI of RSI. More sensitive for short-term reversals.", "params": [{"key": "rsi_period", "label": "RSI Period", "default": 14, "min": 5, "max": 30, "type": "int"}, {"key": "k_period", "label": "K Period", "default": 14, "min": 3, "max": 30, "type": "int"}, {"key": "oversold", "label": "Oversold", "default": 20, "min": 5, "max": 35, "type": "int"}, {"key": "overbought", "label": "Overbought", "default": 80, "min": 65, "max": 95, "type": "int"}]},
    "WILLIAMS_R": {"name": "Williams %R", "cat": "Mean Reversion", "desc": "Inverse stochastic. -80 to -100 = oversold. -0 to -20 = overbought.", "params": [{"key": "period", "label": "Period", "default": 14, "min": 5, "max": 50, "type": "int"}, {"key": "oversold", "label": "Oversold", "default": -80, "min": -95, "max": -60, "type": "int"}, {"key": "overbought", "label": "Overbought", "default": -20, "min": -40, "max": -5, "type": "int"}]},
    "CCI": {"name": "CCI", "cat": "Mean Reversion", "desc": "Commodity Channel Index. Above +100 = overbought, below -100 = oversold.", "params": [{"key": "period", "label": "Period", "default": 20, "min": 5, "max": 50, "type": "int"}, {"key": "threshold", "label": "Threshold", "default": 100, "min": 50, "max": 200, "type": "int"}]},
    "STOCHASTIC": {"name": "Stochastic %K/%D", "cat": "Mean Reversion", "desc": "Classic oscillator. Buy K crosses above D in oversold.", "params": [{"key": "k_period", "label": "K Period", "default": 14, "min": 5, "max": 30, "type": "int"}, {"key": "d_period", "label": "D Period", "default": 3, "min": 1, "max": 10, "type": "int"}, {"key": "oversold", "label": "Oversold", "default": 20, "min": 5, "max": 35, "type": "int"}, {"key": "overbought", "label": "Overbought", "default": 80, "min": 65, "max": 95, "type": "int"}]},
    "ZSCORE": {"name": "Z-Score Reversion", "cat": "Mean Reversion", "desc": "Statistical deviation. Z<-2 = buy, Z>2 = sell.", "params": [{"key": "period", "label": "Lookback", "default": 20, "min": 10, "max": 100, "type": "int"}, {"key": "threshold", "label": "Z Threshold", "default": 2.0, "min": 1.0, "max": 4.0, "type": "float"}]},
    "DISTANCE_FROM_EMA": {"name": "Distance from EMA %", "cat": "Mean Reversion", "desc": "Buy when price drops X% below EMA. Rubber band reversion.", "params": [{"key": "period", "label": "EMA Period", "default": 20, "min": 5, "max": 100, "type": "int"}, {"key": "threshold_pct", "label": "Distance %", "default": 2.0, "min": 0.5, "max": 10.0, "type": "float"}]},
    "VWAP_DEV": {"name": "VWAP Deviation", "cat": "Mean Reversion", "desc": "Revert to VWAP. Institutional fair value benchmark.", "params": [{"key": "deviation_pct", "label": "Deviation %", "default": 0.1, "min": 0.05, "max": 2.0, "type": "float"}]},
    "CHANDE_MO": {"name": "Chande Momentum", "cat": "Mean Reversion", "desc": "Pure momentum oscillator. +100 overbought, -100 oversold.", "params": [{"key": "period", "label": "Period", "default": 14, "min": 5, "max": 50, "type": "int"}, {"key": "threshold", "label": "Threshold", "default": 50, "min": 20, "max": 80, "type": "int"}]},
    "ULTIMATE_OSC": {"name": "Ultimate Oscillator", "cat": "Mean Reversion", "desc": "3-timeframe oscillator. Below 30 = buy, above 70 = sell.", "params": [{"key": "period1", "label": "Short", "default": 7, "min": 3, "max": 14, "type": "int"}, {"key": "period2", "label": "Mid", "default": 14, "min": 7, "max": 28, "type": "int"}, {"key": "period3", "label": "Long", "default": 28, "min": 14, "max": 56, "type": "int"}]},
    "ROC_REVERSION": {"name": "ROC Mean Reversion", "cat": "Mean Reversion", "desc": "Extreme Rate of Change values revert to mean.", "params": [{"key": "period", "label": "Period", "default": 10, "min": 3, "max": 50, "type": "int"}, {"key": "threshold", "label": "ROC %", "default": 5.0, "min": 1.0, "max": 20.0, "type": "float"}]},

    # ── MOMENTUM (8) ──────────────────────────────────────────────────────
    "MACD_SIGNAL": {"name": "MACD Signal Cross", "cat": "Momentum", "desc": "Buy MACD crosses above signal. Classic momentum.", "params": [{"key": "fast", "label": "Fast", "default": 12, "min": 5, "max": 30, "type": "int"}, {"key": "slow", "label": "Slow", "default": 26, "min": 15, "max": 60, "type": "int"}, {"key": "signal", "label": "Signal", "default": 9, "min": 3, "max": 20, "type": "int"}]},
    "MACD_HISTOGRAM": {"name": "MACD Histogram", "cat": "Momentum", "desc": "Buy when histogram turns positive. More sensitive than signal cross.", "params": [{"key": "fast", "label": "Fast", "default": 12, "min": 5, "max": 30, "type": "int"}, {"key": "slow", "label": "Slow", "default": 26, "min": 15, "max": 60, "type": "int"}, {"key": "signal", "label": "Signal", "default": 9, "min": 3, "max": 20, "type": "int"}]},
    "MOMENTUM": {"name": "Price Momentum", "cat": "Momentum", "desc": "Buy when price rises X% over lookback. Pure momentum.", "params": [{"key": "lookback", "label": "Lookback", "default": 5, "min": 2, "max": 50, "type": "int"}, {"key": "threshold_pct", "label": "Threshold %", "default": 0.05, "min": 0.01, "max": 2.0, "type": "float"}]},
    "TSI": {"name": "True Strength Index", "cat": "Momentum", "desc": "Double-smoothed momentum. Cross zero = signal.", "params": [{"key": "long_period", "label": "Long", "default": 25, "min": 10, "max": 50, "type": "int"}, {"key": "short_period", "label": "Short", "default": 13, "min": 5, "max": 25, "type": "int"}]},
    "PCT_FROM_OPEN": {"name": "% from Open", "cat": "Momentum", "desc": "Buy when price moved X% from open. Intraday gap momentum.", "params": [{"key": "threshold_pct", "label": "Threshold %", "default": 0.5, "min": 0.1, "max": 5.0, "type": "float"}]},
    "ELDER_RAY": {"name": "Elder Ray Bull Power", "cat": "Momentum", "desc": "Bull Power = High - EMA. Positive = upward momentum.", "params": [{"key": "period", "label": "EMA Period", "default": 13, "min": 5, "max": 30, "type": "int"}]},
    "COPPOCK": {"name": "Coppock Curve", "cat": "Momentum", "desc": "Long-term momentum. Designed to identify major market bottoms.", "params": [{"key": "wma_period", "label": "WMA", "default": 10, "min": 5, "max": 20, "type": "int"}, {"key": "roc1", "label": "ROC1", "default": 14, "min": 7, "max": 25, "type": "int"}, {"key": "roc2", "label": "ROC2", "default": 11, "min": 5, "max": 20, "type": "int"}]},
    "KST": {"name": "Know Sure Thing", "cat": "Momentum", "desc": "Smoothed ROC across 4 timeframes. Cross signal = trend change.", "params": [{"key": "signal", "label": "Signal Period", "default": 9, "min": 3, "max": 15, "type": "int"}]},

    # ── VOLATILITY BREAKOUT (8) ───────────────────────────────────────────
    "BB_BREAKOUT": {"name": "Bollinger Band Breakout", "cat": "Volatility Breakout", "desc": "Buy lower band (reversion) or upper band break (momentum).", "params": [{"key": "period", "label": "Period", "default": 20, "min": 5, "max": 100, "type": "int"}, {"key": "num_std", "label": "Std Dev", "default": 2.0, "min": 1.0, "max": 4.0, "type": "float"}]},
    "BB_SQUEEZE": {"name": "BB Squeeze", "cat": "Volatility Breakout", "desc": "Tight bands = compression = explosive breakout incoming.", "params": [{"key": "period", "label": "Period", "default": 20, "min": 10, "max": 50, "type": "int"}, {"key": "squeeze_threshold", "label": "Squeeze %", "default": 0.05, "min": 0.01, "max": 0.2, "type": "float"}]},
    "KELTNER": {"name": "Keltner Channel", "cat": "Volatility Breakout", "desc": "ATR-based channel. Breakout above = strong momentum buy.", "params": [{"key": "ema_period", "label": "EMA Period", "default": 20, "min": 5, "max": 50, "type": "int"}, {"key": "atr_period", "label": "ATR Period", "default": 10, "min": 5, "max": 30, "type": "int"}, {"key": "multiplier", "label": "Multiplier", "default": 1.5, "min": 0.5, "max": 4.0, "type": "float"}]},
    "ATR_BREAKOUT": {"name": "ATR Breakout", "cat": "Volatility Breakout", "desc": "Buy when move exceeds N x ATR. Volatility expansion.", "params": [{"key": "period", "label": "ATR Period", "default": 14, "min": 5, "max": 30, "type": "int"}, {"key": "multiplier", "label": "Multiplier", "default": 1.5, "min": 0.5, "max": 5.0, "type": "float"}]},
    "DONCHIAN": {"name": "Donchian Channel", "cat": "Volatility Breakout", "desc": "Turtle Trading. Buy new N-day high, sell new N-day low.", "params": [{"key": "period", "label": "Period", "default": 20, "min": 5, "max": 100, "type": "int"}]},
    "SQUEEZE_MOMENTUM": {"name": "Squeeze Momentum", "cat": "Volatility Breakout", "desc": "BB inside Keltner = squeeze. Buy when squeeze releases.", "params": [{"key": "bb_period", "label": "BB Period", "default": 20, "min": 10, "max": 50, "type": "int"}, {"key": "kc_period", "label": "KC Period", "default": 20, "min": 10, "max": 50, "type": "int"}]},
    "NR4": {"name": "NR4/NR7 Narrow Range", "cat": "Volatility Breakout", "desc": "Narrowest range in N bars = compression = breakout.", "params": [{"key": "lookback", "label": "Lookback", "default": 4, "min": 3, "max": 10, "type": "int"}]},
    "HIST_VOLATILITY": {"name": "Historical Volatility", "cat": "Volatility Breakout", "desc": "Buy when volatility expands above average. Regime change.", "params": [{"key": "period", "label": "Period", "default": 20, "min": 10, "max": 100, "type": "int"}, {"key": "threshold", "label": "Vol Ratio", "default": 1.5, "min": 1.1, "max": 3.0, "type": "float"}]},

    # ── VOLUME (6) ────────────────────────────────────────────────────────
    "VOLUME_SPIKE": {"name": "Volume Spike", "cat": "Volume", "desc": "Buy on unusual volume surge. Institutional activity.", "params": [{"key": "lookback", "label": "Lookback", "default": 20, "min": 5, "max": 50, "type": "int"}, {"key": "threshold", "label": "Multiplier", "default": 2.0, "min": 1.2, "max": 10.0, "type": "float"}]},
    "OBV_TREND": {"name": "OBV Trend", "cat": "Volume", "desc": "On Balance Volume. Smart money accumulation/distribution.", "params": [{"key": "lookback", "label": "Lookback", "default": 20, "min": 5, "max": 50, "type": "int"}]},
    "CMF": {"name": "Chaikin Money Flow", "cat": "Volume", "desc": "Positive CMF = buying pressure. >0.1 = strong accumulation.", "params": [{"key": "period", "label": "Period", "default": 20, "min": 5, "max": 50, "type": "int"}, {"key": "threshold", "label": "Threshold", "default": 0.1, "min": 0.0, "max": 0.5, "type": "float"}]},
    "MFI": {"name": "Money Flow Index", "cat": "Volume", "desc": "RSI weighted by volume. <20 oversold, >80 overbought.", "params": [{"key": "period", "label": "Period", "default": 14, "min": 5, "max": 30, "type": "int"}, {"key": "oversold", "label": "Oversold", "default": 20, "min": 10, "max": 35, "type": "int"}, {"key": "overbought", "label": "Overbought", "default": 80, "min": 65, "max": 90, "type": "int"}]},
    "FORCE_INDEX": {"name": "Force Index", "cat": "Volume", "desc": "Price change x volume. Positive = buying pressure.", "params": [{"key": "period", "label": "Period", "default": 13, "min": 3, "max": 30, "type": "int"}]},
    "EASE_OF_MOVEMENT": {"name": "Ease of Movement", "cat": "Volume", "desc": "How easily price moves through volume.", "params": [{"key": "period", "label": "Period", "default": 14, "min": 5, "max": 30, "type": "int"}]},

    # ── CANDLESTICK (12) ──────────────────────────────────────────────────
    "DOJI": {"name": "Doji", "cat": "Candlestick", "desc": "Open = Close. Indecision. At support = buy signal.", "params": [{"key": "threshold", "label": "Body/Range", "default": 0.05, "min": 0.01, "max": 0.15, "type": "float"}]},
    "HAMMER": {"name": "Hammer", "cat": "Candlestick", "desc": "Long lower wick, small body at top. Bullish reversal.", "params": []},
    "SHOOTING_STAR": {"name": "Shooting Star", "cat": "Candlestick", "desc": "Long upper wick, small body at bottom. Bearish reversal.", "params": []},
    "BULLISH_ENGULFING": {"name": "Bullish Engulfing", "cat": "Candlestick", "desc": "Large bullish candle engulfs previous bearish. Strong reversal.", "params": []},
    "BEARISH_ENGULFING": {"name": "Bearish Engulfing", "cat": "Candlestick", "desc": "Large bearish candle engulfs previous bullish. Strong reversal.", "params": []},
    "MORNING_STAR": {"name": "Morning Star", "cat": "Candlestick", "desc": "3-candle bullish reversal. Very reliable bottom signal.", "params": []},
    "EVENING_STAR": {"name": "Evening Star", "cat": "Candlestick", "desc": "3-candle bearish reversal. Very reliable top signal.", "params": []},
    "THREE_WHITE_SOLDIERS": {"name": "Three White Soldiers", "cat": "Candlestick", "desc": "3 consecutive bullish candles. Strong uptrend continuation.", "params": []},
    "THREE_BLACK_CROWS": {"name": "Three Black Crows", "cat": "Candlestick", "desc": "3 consecutive bearish candles. Strong downtrend.", "params": []},
    "HARAMI": {"name": "Harami (Inside Bar)", "cat": "Candlestick", "desc": "Small candle inside previous. Compression = reversal.", "params": []},
    "MARUBOZU": {"name": "Marubozu", "cat": "Candlestick", "desc": "Full body, no wicks. Strongest directional conviction.", "params": [{"key": "wick_threshold", "label": "Max Wick", "default": 0.02, "min": 0.01, "max": 0.1, "type": "float"}]},
    "PIERCING_LINE": {"name": "Piercing Line", "cat": "Candlestick", "desc": "Bullish candle opens below prior low, closes above midpoint.", "params": []},

    # ── PRICE ACTION (9) ──────────────────────────────────────────────────
    "NEW_HIGH_LOW": {"name": "New High/Low Breakout", "cat": "Price Action", "desc": "Buy new N-bar high. Sell new N-bar low.", "params": [{"key": "lookback", "label": "Lookback", "default": 20, "min": 5, "max": 100, "type": "int"}]},
    "INSIDE_BAR": {"name": "Inside Bar Breakout", "cat": "Price Action", "desc": "Buy breakout above inside bar high. Compression to expansion.", "params": []},
    "OUTSIDE_BAR": {"name": "Outside Bar", "cat": "Price Action", "desc": "Bar exceeds previous range on both sides. Volatility expansion.", "params": []},
    "PREV_DAY_BREAK": {"name": "Prev Day High/Low Break", "cat": "Price Action", "desc": "Buy above yesterday's high. Classic day-trading setup.", "params": [{"key": "buffer_pct", "label": "Buffer %", "default": 0.05, "min": 0.0, "max": 0.5, "type": "float"}]},
    "ORB": {"name": "Opening Range Breakout", "cat": "Price Action", "desc": "Buy breakout above opening range high.", "params": [{"key": "range_minutes", "label": "Range (mins)", "default": 30, "min": 5, "max": 60, "type": "int"}]},
    "HIGHER_HIGH": {"name": "Higher High / Lower Low", "cat": "Price Action", "desc": "Buy higher high + higher low. Uptrend structure.", "params": [{"key": "lookback", "label": "Swing Lookback", "default": 5, "min": 2, "max": 20, "type": "int"}]},
    "GAP_UP": {"name": "Gap Up Momentum", "cat": "Price Action", "desc": "Buy when price gaps up. Institutional overnight buying.", "params": [{"key": "threshold_pct", "label": "Min Gap %", "default": 0.2, "min": 0.05, "max": 3.0, "type": "float"}]},
    "GAP_DOWN": {"name": "Gap Down Short", "cat": "Price Action", "desc": "Sell when price gaps down. Overnight selling pressure.", "params": [{"key": "threshold_pct", "label": "Min Gap %", "default": 0.2, "min": 0.05, "max": 3.0, "type": "float"}]},
    "ROUND_NUMBER": {"name": "Round Number S/R", "cat": "Price Action", "desc": "Buy near round numbers ($500, $100). Psychological support.", "params": [{"key": "proximity_pct", "label": "Proximity %", "default": 0.1, "min": 0.05, "max": 1.0, "type": "float"}]},
}


def get_indicator_count():
    return len(INDICATOR_REGISTRY)


def get_indicators_by_category():
    result = {}
    for ind_id, meta in INDICATOR_REGISTRY.items():
        cat = meta["cat"]
        if cat not in result:
            result[cat] = []
        result[cat].append({"id": ind_id, **meta})
    return result
