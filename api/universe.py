"""QuantX Deployer — Default stock universes per bot type."""

DEFAULT_UNIVERSE = {
    "US": [
        "AAPL.US", "MSFT.US", "NVDA.US", "GOOGL.US", "META.US", "AMZN.US",
        "TSLA.US", "JPM.US", "V.US", "JNJ.US", "UNH.US", "KO.US",
        "XOM.US", "GS.US", "BAC.US", "WMT.US", "COST.US", "HD.US",
        "AVGO.US", "NFLX.US", "AMD.US", "CRM.US", "ADBE.US", "PYPL.US",
        "INTC.US", "PG.US", "MA.US", "MRK.US", "CVX.US", "ABBV.US",
    ],
    "HK": [
        "700.HK", "9988.HK", "9618.HK", "3690.HK", "1810.HK", "0005.HK",
        "1299.HK", "2318.HK", "0388.HK", "0939.HK", "0016.HK", "0823.HK",
        "1109.HK", "0857.HK", "0941.HK", "6862.HK", "2331.HK", "2020.HK",
        "2800.HK", "0066.HK",
    ],
}

BOT_UNIVERSE_PREFERENCE = {
    "BUFFETT_BOT": {"preferred": ["AAPL.US", "MSFT.US", "KO.US", "JNJ.US", "700.HK", "0005.HK"]},
    "GRAHAM_BOT": {"preferred": ["9988.HK", "INTC.US", "BAC.US", "XOM.US", "0939.HK"]},
    "LIVERMORE_BOT": {"preferred": ["TSLA.US", "NVDA.US", "AMD.US", "NFLX.US", "META.US"]},
    "DALIO_BOT": {"preferred": ["SPY.US", "QQQ.US", "2800.HK", "GLD.US", "0005.HK"]},
    "SIMONS_BOT": {"preferred": ["TQQQ.US", "SOXL.US", "700.HK", "SPY.US", "QQQ.US"]},
    "TURTLE_TRADER": {"preferred": ["TQQQ.US", "NVDA.US", "700.HK", "QQQ.US", "9988.HK"]},
    "SOROS_BOT": {"preferred": ["TQQQ.US", "700.HK", "9988.HK", "NVDA.US", "META.US"]},
}


def get_universe(bot_type: str, arena: str, custom_tickers: list = None) -> list:
    base = []
    if arena in ("US", "BOTH"):
        base.extend(DEFAULT_UNIVERSE["US"])
    if arena in ("HK", "BOTH"):
        base.extend(DEFAULT_UNIVERSE["HK"])
    if custom_tickers:
        for t in custom_tickers:
            t = t.strip().upper()
            if t and t not in base:
                base.append(t)
    return list(dict.fromkeys(base))
