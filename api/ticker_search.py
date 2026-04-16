"""QuantX -- Ticker search with local index + LongPort static_info fallback."""

import logging

log = logging.getLogger("quantx-ticker-search")

# ── Bundled search index ──────────────────────────────────────────────────────
# Common HK + US stocks pre-loaded so search works without LP connection

TICKER_INDEX = [
    # HK Stocks
    {"symbol": "700.HK",   "name": "Tencent Holdings",       "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["tencent", "0700"]},
    {"symbol": "9988.HK",  "name": "Alibaba Group",           "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["alibaba", "baba"]},
    {"symbol": "0005.HK",  "name": "HSBC Holdings",           "market": "HK", "lot": 400, "currency": "HKD", "aliases": ["hsbc"]},
    {"symbol": "1299.HK",  "name": "AIA Group",               "market": "HK", "lot": 200, "currency": "HKD", "aliases": ["aia"]},
    {"symbol": "0388.HK",  "name": "Hong Kong Exchanges",     "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["hkex", "hkse"]},
    {"symbol": "2318.HK",  "name": "Ping An Insurance",       "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["pingan", "ping an"]},
    {"symbol": "0941.HK",  "name": "China Mobile",            "market": "HK", "lot": 500, "currency": "HKD", "aliases": ["china mobile"]},
    {"symbol": "3690.HK",  "name": "Meituan",                 "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["meituan"]},
    {"symbol": "9618.HK",  "name": "JD.com",                  "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["jd", "jdcom"]},
    {"symbol": "0016.HK",  "name": "Sun Hung Kai Properties", "market": "HK", "lot": 500, "currency": "HKD", "aliases": ["shkp", "sun hung kai"]},
    {"symbol": "0001.HK",  "name": "CK Hutchison Holdings",   "market": "HK", "lot": 500, "currency": "HKD", "aliases": ["ck hutchison", "cheung kong"]},
    {"symbol": "2800.HK",  "name": "Tracker Fund of HK",      "market": "HK", "lot": 500, "currency": "HKD", "aliases": ["tracker", "hsi etf"]},
    {"symbol": "3032.HK",  "name": "CSOP Hang Seng TECH ETF", "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["hstech etf"]},
    {"symbol": "0883.HK",  "name": "CNOOC",                   "market": "HK", "lot": 1000, "currency": "HKD", "aliases": ["cnooc"]},
    {"symbol": "2382.HK",  "name": "Sunny Optical",           "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["sunny optical"]},
    {"symbol": "1810.HK",  "name": "Xiaomi",                  "market": "HK", "lot": 200, "currency": "HKD", "aliases": ["xiaomi"]},
    {"symbol": "9999.HK",  "name": "NetEase",                 "market": "HK", "lot": 10,  "currency": "HKD", "aliases": ["netease"]},
    {"symbol": "0011.HK",  "name": "Hang Seng Bank",          "market": "HK", "lot": 100, "currency": "HKD", "aliases": ["hang seng bank"]},
    {"symbol": "2269.HK",  "name": "WuXi Biologics",          "market": "HK", "lot": 500, "currency": "HKD", "aliases": ["wuxi"]},
    {"symbol": "0960.HK",  "name": "Longfor Group",           "market": "HK", "lot": 500, "currency": "HKD", "aliases": ["longfor"]},
    # SG Stocks
    {"symbol": "D05.SI",   "name": "DBS Group Holdings",      "market": "SG", "lot": 100, "currency": "SGD", "aliases": ["dbs"]},
    {"symbol": "O39.SI",   "name": "OCBC Bank",               "market": "SG", "lot": 100, "currency": "SGD", "aliases": ["ocbc"]},
    {"symbol": "U11.SI",   "name": "United Overseas Bank",    "market": "SG", "lot": 100, "currency": "SGD", "aliases": ["uob"]},
    {"symbol": "Z74.SI",   "name": "Singtel",                 "market": "SG", "lot": 100, "currency": "SGD", "aliases": ["singtel"]},
    {"symbol": "C6L.SI",   "name": "Singapore Airlines",      "market": "SG", "lot": 100, "currency": "SGD", "aliases": ["sia", "singapore airlines"]},
    # US Stocks
    {"symbol": "AAPL.US",  "name": "Apple Inc.",              "market": "US", "lot": 1, "currency": "USD", "aliases": ["apple"]},
    {"symbol": "MSFT.US",  "name": "Microsoft Corporation",   "market": "US", "lot": 1, "currency": "USD", "aliases": ["microsoft"]},
    {"symbol": "NVDA.US",  "name": "NVIDIA Corporation",      "market": "US", "lot": 1, "currency": "USD", "aliases": ["nvidia"]},
    {"symbol": "TSLA.US",  "name": "Tesla Inc.",              "market": "US", "lot": 1, "currency": "USD", "aliases": ["tesla"]},
    {"symbol": "AMZN.US",  "name": "Amazon.com Inc.",         "market": "US", "lot": 1, "currency": "USD", "aliases": ["amazon"]},
    {"symbol": "GOOGL.US", "name": "Alphabet Inc.",           "market": "US", "lot": 1, "currency": "USD", "aliases": ["google", "alphabet"]},
    {"symbol": "META.US",  "name": "Meta Platforms Inc.",     "market": "US", "lot": 1, "currency": "USD", "aliases": ["meta", "facebook"]},
    {"symbol": "BRK.B.US", "name": "Berkshire Hathaway B",   "market": "US", "lot": 1, "currency": "USD", "aliases": ["berkshire"]},
    {"symbol": "JPM.US",   "name": "JPMorgan Chase",          "market": "US", "lot": 1, "currency": "USD", "aliases": ["jpmorgan", "jp morgan"]},
    {"symbol": "V.US",     "name": "Visa Inc.",               "market": "US", "lot": 1, "currency": "USD", "aliases": ["visa"]},
    {"symbol": "SPY.US",   "name": "SPDR S&P 500 ETF",       "market": "US", "lot": 1, "currency": "USD", "aliases": ["spy", "sp500 etf"]},
    {"symbol": "QQQ.US",   "name": "Invesco QQQ Trust",      "market": "US", "lot": 1, "currency": "USD", "aliases": ["qqq", "nasdaq etf"]},
    {"symbol": "TQQQ.US",  "name": "ProShares UltraPro QQQ", "market": "US", "lot": 1, "currency": "USD", "aliases": ["tqqq"]},
    {"symbol": "GLD.US",   "name": "SPDR Gold Shares",       "market": "US", "lot": 1, "currency": "USD", "aliases": ["gold etf", "gld"]},
    {"symbol": "SOFI.US",  "name": "SoFi Technologies",      "market": "US", "lot": 1, "currency": "USD", "aliases": ["sofi"]},
    {"symbol": "PLTR.US",  "name": "Palantir Technologies",  "market": "US", "lot": 1, "currency": "USD", "aliases": ["palantir"]},
    {"symbol": "AMD.US",   "name": "Advanced Micro Devices", "market": "US", "lot": 1, "currency": "USD", "aliases": ["amd"]},
    {"symbol": "NFLX.US",  "name": "Netflix Inc.",           "market": "US", "lot": 1, "currency": "USD", "aliases": ["netflix"]},
    {"symbol": "DIS.US",   "name": "Walt Disney Co.",        "market": "US", "lot": 1, "currency": "USD", "aliases": ["disney"]},
    {"symbol": "BAC.US",   "name": "Bank of America",        "market": "US", "lot": 1, "currency": "USD", "aliases": ["bank of america", "bofa"]},
    {"symbol": "COIN.US",  "name": "Coinbase Global",        "market": "US", "lot": 1, "currency": "USD", "aliases": ["coinbase"]},
    {"symbol": "INTC.US",  "name": "Intel Corporation",      "market": "US", "lot": 1, "currency": "USD", "aliases": ["intel"]},
    {"symbol": "CRM.US",   "name": "Salesforce Inc.",        "market": "US", "lot": 1, "currency": "USD", "aliases": ["salesforce"]},
    {"symbol": "ADBE.US",  "name": "Adobe Inc.",             "market": "US", "lot": 1, "currency": "USD", "aliases": ["adobe"]},
    {"symbol": "KO.US",    "name": "Coca-Cola Company",      "market": "US", "lot": 1, "currency": "USD", "aliases": ["coca cola", "coke"]},
    {"symbol": "XOM.US",   "name": "Exxon Mobil",            "market": "US", "lot": 1, "currency": "USD", "aliases": ["exxon"]},
]


def search_local(query: str, limit: int = 10) -> list:
    """Fuzzy search local index by symbol, name, or alias."""
    q = query.lower().strip()
    if not q:
        return []

    results = []
    for t in TICKER_INDEX:
        score = 0
        sym_lower = t["symbol"].lower().replace(".hk", "").replace(".us", "").replace(".si", "")
        sym_padded = sym_lower.zfill(4) if sym_lower.isdigit() else sym_lower
        name_lower = t["name"].lower()
        q_stripped = q.lstrip("0") if q.replace("0", "").isdigit() and q.isdigit() else q

        if q == sym_lower or q == t["symbol"].lower():
            score = 100
        elif q.isdigit() and q_stripped == sym_lower.lstrip("0"):
            score = 95  # "0700" matches "700.HK"
        elif sym_lower.startswith(q):
            score = 80
        elif name_lower.startswith(q):
            score = 70
        elif q in [a.lower() for a in t.get("aliases", [])]:
            score = 90
        elif q in sym_lower:
            score = 60
        elif q in name_lower:
            score = 50
        elif any(q in a.lower() for a in t.get("aliases", [])):
            score = 40

        if score > 0:
            results.append({**t, "_score": score})

    results.sort(key=lambda x: -x["_score"])
    return results[:limit]


def lookup_lp(symbols: list, lp_credentials: dict) -> list:
    """Look up symbols from LongPort static_info one by one.
    Skips symbols that don't exist. Uses del ctx for cleanup."""
    if not symbols or not lp_credentials.get("app_key"):
        return []

    results = []
    ctx = None
    try:
        from longport.openapi import Config, QuoteContext
        cfg = Config(
            app_key=lp_credentials["app_key"],
            app_secret=lp_credentials["app_secret"],
            access_token=lp_credentials["access_token"],
        )
        ctx = QuoteContext(cfg)

        for sym in symbols:
            try:
                r = ctx.static_info([sym])
                if r:
                    for item in r:
                        market = "HK" if item.symbol.endswith(".HK") else \
                                 "US" if item.symbol.endswith(".US") else \
                                 "SG" if item.symbol.endswith(".SI") else "OTHER"
                        results.append({
                            "symbol": item.symbol,
                            "name": getattr(item, "name_en", "") or item.symbol,
                            "market": market,
                            "lot": getattr(item, "lot_size", 1),
                            "currency": getattr(item, "currency", ""),
                            "exchange": str(getattr(item, "exchange", "")),
                            "aliases": [],
                        })
                        log.info("LP lookup found: %s (%s)", item.symbol,
                                 getattr(item, "name_en", ""))
            except Exception as e:
                log.debug("LP static_info miss for %s: %s", sym, e)
                continue
    except Exception as e:
        log.warning("LP QuoteContext failed: %s", e)
    finally:
        if ctx is not None:
            del ctx

    return results


def search_ticker(query: str, lp_credentials: dict = None, limit: int = 10) -> list:
    """Main search function.
    1. Search local index first (instant)
    2. If no results and query looks like a symbol, try LP static_info
    3. Cache LP results into local index for this session
    """
    q = query.strip()
    if len(q) < 1:
        return []

    # Layer 1: local index (fast, offline)
    local_results = search_local(q, limit)
    if local_results:
        return [{k: v for k, v in r.items() if k != "_score"}
                for r in local_results]

    # Layer 2: LP static_info with smart candidate generation
    if lp_credentials and len(q) >= 1:
        q_upper = q.upper().strip()
        candidates = []

        if q_upper.endswith(".US") or q_upper.endswith(".HK") or q_upper.endswith(".SI"):
            candidates = [q_upper]
        elif q_upper.isdigit():
            padded = q_upper.zfill(4)
            candidates = [f"{padded}.HK"]
            if padded != q_upper:
                candidates.append(f"{q_upper}.HK")
        else:
            candidates = [f"{q_upper}.US", f"{q_upper}.HK", f"{q_upper}.SI"]

        lp_results = lookup_lp(candidates, lp_credentials)
        if lp_results:
            for t in lp_results:
                if not any(x["symbol"] == t["symbol"] for x in TICKER_INDEX):
                    TICKER_INDEX.append(t)
            return lp_results[:limit]

    return []
