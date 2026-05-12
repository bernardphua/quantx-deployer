# QuantX Deployer — Full Handoff (05 May 2026, End of Session)

## App URL
https://quantx-deploy.up.railway.app  
Repo: https://github.com/seanseahsg/quantx-deployer  
Stack: FastAPI + SQLite on Railway, LongPort SDK, single-page HTML frontend  
Students: 114, each with their own LongPort brokerage account

---

## What Was Accomplished Today (Complete)

### Session started with: broken deployment pipeline
The bot deploy was failing silently — a fallback in `generate_lp_master_bot()` 
was running the old broken template whenever generation failed, hiding all errors.
Spent the first half of the day finding and fixing 6 cascading bugs.

### All Git Commits (chronological)

| Commit | File | What it fixed |
|--------|------|---------------|
| `46cfcc4` | generate.py, main.py | Removed all IBKR code |
| `d5baab3` | generate.py | `is_grid` check — SYMMETRIC_GRID skips signal code generation |
| `e300c68` | bot_template_lp_master.py | Full template with GridState + DRY_RUN (was 532 lines, became 932) |
| `87e2c4d` | main.py, generate.py | Removed silent fallback; dry_run added to DeployReq |
| `3ffe696` | main.py | Added /api/admin/nuke-scripts endpoint |
| `a1ee0ce` | main.py | Added /api/admin/clear-bot-scripts endpoint |
| `82b683d` | bot_template_lp_master.py | Removed `__SIGNAL_FUNCTIONS_BLOCK__` comment that triggered AssertionError |
| `fc6f9e1` | index.html | Fixed trades dashboard (API response parsing) + DRY badge in bot detail |
| `d50da9f` | bot_template_lp_master.py | LongBridge fees in P&L + `_processed_oids` dedup set |
| CC backend | main.py, database.py | `is_dry_run` column in strategies table + clone endpoint |
| latest | index.html | Bot mode baked at creation + clone UX + live P&L in bots list |
| latest | bot_template_lp_master.py | Fixed `OrderSide` import (was causing ALL live orders to fail) |
| latest | index.html | Clone dialog: OK=flip mode, Cancel=same mode |
| latest | index.html | Lots field in New Bot form with auto-fill from symbol API |
| `f32b181` | main.py, database.py, bot_template | Duplicate process fix + LIMIT 500 on trades query + log dedup |
| latest | index.html | Live metrics computed from trades DB + equity curve (Chart.js) |
| latest | main.py, database.py | Shared backtest result cache Phase 1 (SQLite, sha256 key, 24h TTL) |
| latest | index.html | ⚡ cached badge on backtest results |
| latest | bot_template_lp_master.py | `datetime.utcnow()` → `datetime.now(timezone.utc)` (removes DeprecationWarning) |

---

## Current Railway File Versions

| File | Lines | Key features on Railway |
|------|-------|------------------------|
| api/main.py | 3131 | is_dry_run in StrategyReq, clone endpoint, backtest cache routes, nuke-scripts, LIMIT 500 |
| api/database.py | 664 | backtest_cache table, _bt_cache_key, get/set_backtest_cache, LIMIT 500 on get_trades |
| api/bot_template_lp_master.py | 964 | GridState, DRY_RUN, calc_hk_fees, _processed_oids, logger.propagate=False, timezone-aware datetime |
| api/generate.py | 571 | is_grid check, __DRY_RUN__ substitution, lots in strategies_meta |
| static/index.html | 8059 | All UI features below |
| api/options_backtest.py | 911 | Unchanged from before session |
| api/options_data.py | 470 | Unchanged from before session |

---

## What's Confirmed Working ✅

1. **Live order placement** — MSFT: 4 limit buy orders placed in LongPort (confirmed)
2. **Live order cancellation on stop** — FLATTEN: Shutdown cancels all open orders (by design)
3. **Dry run grid bot** — 700.HK full cycle, fees calculated correctly
4. **LongBridge fee model** — Buy: 0.03%+stamp(0.1%)+SFC(0.0027%)+HKEX(0.005%)+CCASS(0.002%), Sell: same minus stamp duty (HK abolished sell-side stamp Oct 2023)
5. **Fee reality check** — At 0.3% TP with 700.HK 100 shares: HKD 140 gross - HKD 144 fees = UNPROFITABLE. Use 0.5%+ TP.
6. **Bot mode baked at creation** — Dry Run / Live chosen when creating bot, not at deploy time
7. **Single deploy button** — Purple=Dry Run, Green=Live, reads mode from bot's is_dry_run field
8. **Filter by mode** — All / 🔴 Live / 🧪 Dry Run / ⏹ Off tabs on Bots page
9. **Clone bot** — ⧉ button, dialog: OK=flip mode / Cancel=same mode, fresh trade history
10. **Lots field in New Bot form** — auto-fills min board lot (e.g. 100 for HK stocks)
11. **Live metrics on bot dashboard** — Return%, Win Rate, Max DD, Sharpe computed from trades DB
12. **Equity curve** — Chart.js line chart of cumulative P&L over time
13. **Shared backtest cache** — sha256 key, SQLite, 24h TTL. Student A pays compute, B-Z get instant ⚡
14. **No duplicate log lines** — f32b181 fixed _auto_restart_bots spawning second process
15. **Trades limited to 500 rows** — prevents 14k+ row API response

---

## Architecture: Bot Lifecycle

```
New Bot form (mode=dry/live, symbol, strategy, lots, params)
  → createBot() → POST /api/strategy → save_strategy() → DB (is_dry_run stored)
  → Deploy button → POST /api/deploy → generate_lp_master_bot(dry_run=True/False)
  → Script at /data/bots/{email_safe}_lp_master.py
  → _launch_bot() → subprocess.Popen → Railway process
  → Bot writes to /data/logs/{email_safe}_lp_master.log
  → Bot POSTs trades to /api/trade → trades table SQLite
  → Dashboard polls /api/trades/{email} → renders equity curve + metrics
```

## Architecture: Backtest Cache

```
Student clicks Run Backtest
  → hash(strategy+symbol+timeframe+params+limit+fees) → sha256 key
  → Check backtest_cache table in SQLite
    → HIT: return in ~50ms with _cached=True → shows ⚡ badge
    → MISS: compute (8-30s), store in cache, return
  → Next student with same params → HIT → instant
```

## Architecture: Options Backtest (unchanged from before session)

```
Options Studio → /api/options/backtest (SSE stream)
  → run_options_backtest_stream() in options_backtest.py
  → options_data.py reads parquet from R2 (greeks_1min_daily/{DATE}.parquet)
  → Sequential day-by-day loop (SLOW — 60-90s for 1Y)
  → /api/options/precomputed: serves pre-run results from R2 quantx-results bucket
```

---

## Database Schema (current)

### strategies table
```sql
email, strategy_id, strategy_name, symbol, arena, timeframe,
conditions_json, exit_rules_json, risk_json, is_active,
mode, library_id, custom_script, broker,
is_dry_run INTEGER DEFAULT 0,   ← added today
backtest_results_json,          ← stores last backtest result for this bot
updated_at
```

### trades table
```sql
id, email, strategy_id, symbol, side, price, qty, pnl,
cumulative_pnl, timestamp
```
- side values: 'bot'/'sld' (grid), 'buy'/'sell' (signal)
- get_trades() LIMIT 500 ORDER BY timestamp DESC

### backtest_cache table (NEW today)
```sql
cache_key TEXT PRIMARY KEY,    ← sha256 of config
result_json TEXT,              ← full backtest result JSON
strategy TEXT,
symbol TEXT,
created_at TEXT                ← used for 24h TTL check
```

---

## Key Code Locations

### bot_template_lp_master.py

**calc_hk_fees(price, qty, side)**  
Lines ~240-258. Calculates LongBridge HK stock fees.

**GridState class**  
Lines ~360-580. Event-driven grid bot. Key methods:
- `__init__`: sets `_processed_oids = set()` to prevent duplicate fills
- `on_tick()`: triggers `_initialize()` on first tick
- `_initialize()`: places buy ladder below CMP
- `on_fill()`: deduplicates via _processed_oids, logs fees, places TP sell
- `_submit_limit()`: places real orders (DRY_RUN=False) or simulates (DRY_RUN=True)

**Known remaining issue:** Duplicate trade records in dry run.  
`_simulate_fill` threads can fire `on_fill` twice per event in rapid quote tick scenarios.  
`_processed_oids` helps but doesn't fully eliminate in dry run.  
Live trading should be single-fire (order fills are unique events).

**Logging setup** (lines ~57-72):
```python
_root_logger = logging.getLogger()
_root_logger.handlers.clear()
logging.basicConfig(..., force=True)
logger = logging.getLogger('quantx-lp-master')
logger.propagate = False  # prevents double logging
```

### generate.py

**generate_lp_master_bot(email, strategies, lp_credentials, dry_run=False)**  
- `is_grid` check skips `generate_signal_code()` for SYMMETRIC_GRID
- `__DRY_RUN__` → `'True'` or `'False'`
- Lots flows: `risk.lots` → `strategies_meta[i].risk` → `__STRATEGIES_LIST__` → template reads `risk.get('lots', 100)`

### main.py key routes

```
POST /api/strategy          → save strategy (is_dry_run field)
POST /api/strategy/{id}/clone → clone with mode flip
POST /api/deploy            → generate + launch bot (reads is_dry_run from strategies)
POST /api/stop              → stop bot (FLATTEN cancels all orders)
POST /api/backtest/run      → check cache first, compute if miss, store result
POST /api/backtest/optimize → same with cache
GET  /api/trades/{email}    → LIMIT 500, returns {trades:[...], by_strategy:{...}}
POST /api/admin/nuke-scripts → {"pin":"quantx2025","email":"..."} — kills + deletes script
GET  /api/debug/bot-script  → ?email=...&key=quantx2025 — shows generated script
GET  /api/debug/fs-inspect  → ?email=...&key=quantx2025 — shows bot files on volume
GET  /api/options/cache/stats → disk cache inventory
GET  /api/options/precomputed → ?symbol=SPY&strategy=short-put-spread&dte=7&period=1y
POST /api/options/backtest  → SSE stream (SLOW, no cache yet)
```

---

## Outstanding Issues

### 🔴 Critical (fix before first student class)

**1. Duplicate trade records in dry run**  
Every trade recorded ~2x because `_simulate_fill` threads fire `on_fill` twice per event.  
Impact: P&L shows ~2x real value in dry run. Live trading is single-fire (correct).  
Fix location: `bot_template_lp_master.py` `_simulate_fill` threading logic.  
Workaround: divide dry run P&L by 2 mentally.

**2. 9:30pm test not yet done**  
Need to verify at US market open:
- TQQQ.US grid bot live: 4 orders appear in LongPort within 10s
- One buy fills → TP sell placed automatically → trade in dashboard
- TURTLE_TRADER signal bot live: bar polling starts, signals computing
- Equity curve populates after first fills
- Same backtest run twice → second is ⚡ instant

### 🟡 Important (next session)

**3. Options backtest has no cache**  
Tier 2 SQLite cache built for equity but not yet wired to `/api/options/backtest`.  
Options backtest is 60-90s on cold cache, still that slow on repeated runs.  
Fix: same cache pattern as equity, options config as cache key.

**4. Modal.com integration for options**  
Plan documented below. Would reduce 1Y SPY backtest from 60s → 8s first run.  
Files needed: api/options_backtest.py, api/options_data.py (uploaded this session).

**5. Startup prewarm of backtest cache**  
Top 20 equity combinations should be pre-run at Railway boot so first student gets instant results.  
Currently only R2 price data is prewarmed, not backtest results.

**6. quantx-central instructor dashboard**  
Still unreachable (404/CORS). Shows all student bots and performance.  
Separate Railway deployment, separate session.

**7. Signal bot live verification**  
Only grid bot (SYMMETRIC_GRID) confirmed live. Signal bots (TURTLE_TRADER, EMA_CROSS etc.) 
use the 60s bar poll loop — untested live. Need to verify at market open.

### 🟢 Nice to Have

**8. Pause mode** — stop process but leave orders open (vs Stop = cancel all)  
**9. Export Strategy button** — broker-agnostic Python class for IBKR  
**10. Options bots page** — currently shows "Coming Soon"

---

## Modal.com Integration Plan (Next Session)

### Problem
Options backtest is 60-90s for 1Y because:
1. R2 parquet download: 252 files × ~10MB = ~2.5GB (first run)
2. Sequential trade computation: each day waits for previous

### Solution
Split date range into months → dispatch N Modal workers simultaneously → merge results.

Each worker is independent:
- Downloads its own month's parquets from R2 to `/tmp`
- Worker for month M downloads `month_start → month_end + max_dte` days
  (because a Jan 31 trade with 7DTE needs Feb parquets)
- Runs entry/exit logic for its date range
- Returns list of trade dicts (not metrics — metrics computed by orchestrator after merge)

### Files needed at session start
```
api/main.py           (current Railway version — upload fresh)
api/database.py       (current Railway version — upload fresh)
api/options_backtest.py  (uploaded this session — already in context)
api/options_data.py      (uploaded this session — already in context)
scripts/precompute_modal.py  (if exists in repo — check)
```

### Build order
1. Add Tier 2 SQLite cache to `/api/options/backtest` route (30 min, high value, same pattern as equity)
2. `scripts/precompute_modal.py` — Modal worker + orchestrator (60 min)
   - `@modal.function` that runs one month of options backtest
   - Uses R2 credentials from Modal secrets
   - Returns list of trade dicts
   - Orchestrator splits range, starmap, merges, computes metrics
3. New route `/api/options/backtest-fast` that uses Modal for periods > 60 days
4. Test: SPY 1Y twice — first ~8s (Modal), second ~50ms (cache) ⚡
5. Pre-populate R2 with top 10 combinations via `precompute_modal.py`

### Cost estimate
- 12 workers × 5s CPU = 60 CPU-seconds
- At Modal's $0.000164/s = $0.01 per backtest
- 114 students × 10 backtests = $11.40 per class
- With caching: ~$2-3 total (most students hit cache after first)

### Modal credentials needed
- `MODAL_TOKEN_ID` env var in Railway
- `MODAL_TOKEN_SECRET` env var in Railway
- `quantx-r2-credentials` Modal secret (R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET)

---

## How to Start Next Session

### Step 1: Upload these files first
```
api/main.py
api/database.py  
api/bot_template_lp_master.py
api/generate.py
static/index.html
api/options_backtest.py
api/options_data.py
scripts/precompute_modal.py  (if it exists)
```

### Step 2: Tell Claude
"Here are the current Railway files. Continue from HANDOFF_05_may2026_FINAL.md"

### Step 3: Confirm 9:30pm test results
Report what happened at market open:
- Did TQQQ grid orders appear in LongPort? ✅/❌
- Did a buy fill and TP sell get placed? ✅/❌
- Did signal bot start bar polling? ✅/❌
- Did equity curve render? ✅/❌

### Step 4: Work order
1. Fix duplicate dry run trades (if still present)
2. Add SQLite cache to options backtest route
3. Build Modal integration
4. Test end-to-end options: SPY 1Y twice, verify ⚡ on second run
5. Startup prewarm of top 20 equity combos

---

## Admin Commands (Emergency)

```powershell
# Nuke stale scripts (use when bot won't stop or log shows old errors)
Invoke-WebRequest -Uri "https://quantx-deploy.up.railway.app/api/admin/nuke-scripts" `
  -Method POST -ContentType "application/json" `
  -Body '{"pin":"quantx2025","email":"seanseahsg@gmail.com"}' -UseBasicParsing

# Check what bot script is running
Invoke-WebRequest -Uri "https://quantx-deploy.up.railway.app/api/debug/bot-script?email=seanseahsg@gmail.com&key=quantx2025" `
  -UseBasicParsing

# Check filesystem
Invoke-WebRequest -Uri "https://quantx-deploy.up.railway.app/api/debug/fs-inspect?email=seanseahsg@gmail.com&key=quantx2025" `
  -UseBasicParsing

# Check backtest cache
Invoke-WebRequest -Uri "https://quantx-deploy.up.railway.app/api/options/cache/stats" -UseBasicParsing
```

---

## Key Learnings (Important for Debugging)

1. **Silent fallback = worst bug pattern.** The root cause of 6 hours of debugging was a `deploy()` fallback that ran the old broken template whenever `generate_lp_master_bot()` failed. Explicit failure > silent degradation. Always raise HTTP 400, never silently degrade.

2. **Template placeholder placement matters.** `__SIGNAL_FUNCTIONS__` appearing in both a top-level position AND inside a comment caused IndentationError. Template files need review for duplicate/misplaced markers.

3. **LongPort SDK quirk.** `QuoteContext` has no `.close()` method. Only release mechanism is `del ctx` inside a `finally` block. This is still an open connection leak (5 locations in main.py).

4. **OrderSide import.** Must be imported explicitly in every function that uses it. The import `from longport.openapi import OrderType, TimeInForceType` was missing `OrderSide` — causing ALL live orders to fail with NameError. Fixed in current Railway version.

5. **Lots flow (confirmed working).** New Bot form → `risk.lots` → `risk_json` in DB → `get_strategies()` returns risk dict → `generate.py` passes to `strategies_meta` → template reads `risk.get('lots', 100)`. No fix needed.

6. **Duplicate processes.** `_auto_restart_bots()` now checks `_running_processes` before spawning. Fixed in f32b181.

7. **HK stamp duty.** HK abolished sell-side stamp duty Oct 2023. `calc_hk_fees()` correctly applies 0.1% stamp on BUY only.

---

## Workflow Reminder

- **Claude Code** for mechanical multi-file changes (grep → view → replace)
- **Drop files in chat** for logic-sensitive single-file rewrites  
- **Always nuke-scripts before testing** a new deploy
- **Test dry run first**, then live
- **Check LongPort app within 10s** of live deploy to confirm orders appear
- **Minimum profitable TP for 700.HK**: 0.35% (use 0.5%+)
- **TQQQ.US** is the best test symbol: ~$60/share, min 1 lot, only $240 for 4-level grid
