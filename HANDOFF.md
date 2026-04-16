# QuantX Deployer -- Project Handoff

**Version:** 1.1.0
**Last updated:** 2026-04-15
**Author:** Sean (SIAS instructor)
**Stack:** Python 3.11 / FastAPI / SQLite / Vanilla JS / LongPort + IBKR APIs

---

## 1. Project Overview

QuantX Deployer is a **student-facing desktop application** for algorithmic trading education at SIAS University (~114 students). It is one of two apps in the QuantX ecosystem:

| App | Purpose | Hosting |
|---|---|---|
| **quantx-central** | Instructor dashboard, student monitoring, heartbeats | Railway (cloud) |
| **quantx-deployer** (this repo) | Strategy creation, backtesting, optimization, live bot deployment | Local (student PC/VPS) |

Students use this app to:
1. Connect broker accounts (LongPort for HK/SG/US, IBKR for global+options)
2. Choose or build trading strategies (library presets or visual Builder)
3. Backtest strategies with historical data
4. Deploy live bots that trade automatically
5. Monitor positions and P&L

**Architecture split:** Backtesting runs on Railway (cloud) for shared data access. Trading always runs locally on the student's machine for latency and credential safety.

---

## 2. Architecture Diagram

```
+------------------------------------------------------------------+
|                     STUDENT PC / VPS                              |
|  +------------------------------------------------------------+  |
|  |  quantx-deployer  (localhost:8080)                         |  |
|  |                                                            |  |
|  |  FastAPI server (api/main.py)                              |  |
|  |    |-- Static frontend (static/index.html)                 |  |
|  |    |-- SQLite DB (quantx_deployer.db)                      |  |
|  |    |-- Bot processes (bots/*.py, managed via subprocess)    |  |
|  |    |-- Trade logs (trades/*.csv)                           |  |
|  |    |-- Bot state (state/*.json)                            |  |
|  |    |-- Bot logs (logs/*.log)                               |  |
|  +----+---------+---------+-----------------------------------+  |
|       |         |         |                                      |
|       v         v         v                                      |
|   LongPort    IBKR     Browser                                   |
|   (HK/SG/US) (TWS/GW) (localhost:8080)                          |
+-------+---------+-------------------------------------------------+
        |         |
        v         v
+----------------+     +-------------------------------------------+
| LongPort API   |     | IBKR TWS / Gateway                        |
| (WebSocket x2) |     | (localhost:7497 paper / 7496 live)        |
+----------------+     +-------------------------------------------+

                           CLOUD (Railway)
+------------------------------------------------------------------+
|  quantx-central (backtesting + instructor dashboard)             |
|    |-- FMP API (historical OHLCV)                                |
|    |-- Cloudflare R2 (S3-compatible parquet data warehouse)      |
|    |-- Yahoo Finance (fallback data)                             |
+------------------------------------------------------------------+
```

**Data waterfall for backtesting:**
`Local SQLite cache -> IBKR -> R2 parquet -> Yahoo Finance -> FMP API`

**Connection model:**
- LongPort: ONE master process with 2 WebSocket connections (quote + trade) regardless of strategy count
- IBKR: One subprocess per strategy, each with unique clientId (hash-based, 100-899)

---

## 3. File Inventory

### Root files

| File | Description |
|---|---|
| `run.py` | Entry point: starts uvicorn, opens browser |
| `install.ps1` | Windows VPS installer: installs Python, copies files, creates scheduled task |
| `Procfile` | Railway deployment command |
| `railway.json` | Railway build/deploy config (Nixpacks, health check) |
| `requirements.txt` | Python dependencies (17 packages) |
| `strategies_library.json` | 14 pre-built strategy definitions with parameters, risk, learning content |
| `.env` | Local environment overrides (CENTRAL_API_URL, PORT) |
| `.fernet.key` | Auto-generated Fernet encryption key for credential storage |
| `.gitignore` | Excludes db, keys, bots, logs, trades, state, __pycache__ |
| `quantx_deployer.db` | SQLite database (gitignored but present locally) |
| `test_grid.py` | Test script for grid bot strategy |
| `test_ibkr.py` | Test script for IBKR connectivity |
| `test_ibkr_order.py` | Test script for IBKR order placement |
| `test_lp_order.py` | Test script for LongPort order placement |
| `test_lp_simple.py` | Test script for simple LongPort flow |

### `api/` -- Backend

| File | Lines | Description |
|---|---|---|
| `main.py` | 1878 | FastAPI app with 55+ routes: strategies, deploy, backtest, brokers, indicators, data, logs |
| `backtest.py` | 1411 | Backtest engine: 20 indicators, portfolio tracking, walk-forward, Monte Carlo, R2/FMP data |
| `database.py` | 583 | SQLite schema (7 tables), Fernet encrypt/decrypt, all CRUD helpers |
| `config.py` | 71 | Central config: paths, env vars, version, directory creation |
| `generate.py` | 559 | Bot script generators: LP master, IBKR prod, simple LP/IBKR, options, signal code gen |
| `data_manager.py` | 287 | Data waterfall: local cache -> IBKR -> R2 -> Yahoo -> FMP, with TTL caching |
| `bot_template.py` | 650 | LongPort master bot (old format, str.format). StrategyRunner + GridRunner classes |
| `bot_template_lp_master.py` | 532 | LongPort master bot (new, __PLACEHOLDER__). Shared connections, per-strategy compute_signals |
| `bot_template_ibkr_prod.py` | 519 | IBKR production bot: async bar loop, 15 indicator funcs, risk mgmt, position reconciliation |
| `bot_template_simple.py` | 245 | Simple test bots: LP (limit buy, wait, cancel) and IBKR (market buy, wait, cancel) |
| `bot_template_options.py` | 997 | SPX 0DTE options bot: iron condors, spreads, delta selection, BAG combos, VIX filter |
| `bot_template_ibkr.py` | ~400 | IBKR master bot (old format, str.format) -- superseded by ibkr_prod |
| `ibkr_connector.py` | 143 | IBKRConnector class wrapping ib_insync for quotes, orders, positions |
| `screener.py` | 341 | Famous investor bot screeners: Buffett, Graham, Livermore, Dalio, Simons, Turtle, Soros |
| `universe.py` | 42 | Default stock universes (30 US, 20 HK) and bot-type preferences |
| `indicators_seed.py` | 113 | 16 built-in indicator definitions seeded to DB on startup |
| `indicators_library.py` | ~400 | AI-powered indicator registration: validates code, parses parameters, generates usage |
| `__init__.py` | 0 | Package marker |

### `static/` -- Frontend

| File | Lines | Description |
|---|---|---|
| `index.html` | 2170 | Complete SPA: sidebar nav, 5 pages (Home, Bots, Backtester, Brokers, Settings), Strategy Builder, modals |
| `symbols.json` | ~2000 | Symbol lookup table for HK/SG/US markets with broker tags |

### `generator/` -- Legacy

| File | Description |
|---|---|
| `__init__.py` | Package marker |
| `bot_template_grid.py` | Standalone grid bot template (ATR-based, daily reset). Used by old grid deploy flow |

---

## 4. Database Schema

### `students`
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| email | TEXT UNIQUE | Student identifier (login key) |
| name | TEXT | Display name |
| app_key_enc | TEXT | LongPort app key (Fernet encrypted) |
| app_secret_enc | TEXT | LongPort app secret (Fernet encrypted) |
| access_token_enc | TEXT | LongPort access token (Fernet encrypted) |
| central_api_url | TEXT | Railway URL for backtesting |
| created_at | TEXT | ISO timestamp |

### `strategies`
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| email | TEXT FK | Owner |
| strategy_id | TEXT UNIQUE | e.g. "EMA_CROSS_700HK_1234" |
| strategy_name | TEXT | Display name |
| symbol | TEXT | e.g. "700.HK", "AAPL.US" |
| arena | TEXT | US, HK, SG |
| timeframe | TEXT | 1m, 5m, 15m, 30m, 1h, 1d |
| conditions_json | TEXT | Builder conditions (entry/exit rules as JSON) |
| exit_rules_json | TEXT | Exit rule overrides |
| risk_json | TEXT | {lots, tp_pct, sl_pct, trail_pct} |
| is_active | INTEGER | 0/1 toggle |
| mode | TEXT | "library", "builder", "script", "quick_test", "options" |
| library_id | TEXT | e.g. "EMA_CROSS", "RSI_MEAN_REVERSION" |
| custom_script | TEXT | User Python code (for script mode) |
| broker | TEXT | "longport" or "ibkr" |
| allocation | TEXT | Capital allocation (default 10000) |
| backtest_results_json | TEXT | Cached backtest results |
| live_results_json | TEXT | Live performance data |
| trade_log_json | TEXT | Trade history |
| created_at | TEXT | ISO timestamp |

### `processes`
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| email | TEXT FK | Owner |
| pid | INTEGER | OS process ID |
| status | TEXT | "running", "stopped", "error" |
| master_script_path | TEXT | Path to generated bot script |
| log_path | TEXT | Path to bot log file |
| started_at | TEXT | ISO timestamp |
| stopped_at | TEXT | ISO timestamp |
| error_msg | TEXT | Last error message |

### `trades`
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| email | TEXT FK | Owner |
| strategy_id | TEXT | Strategy that triggered the trade |
| symbol | TEXT | Traded symbol |
| side | TEXT | "buy" or "sell" |
| price | REAL | Fill price |
| qty | REAL | Quantity |
| pnl | REAL | Realized P&L for this trade |
| cumulative_pnl | REAL | Running total P&L |
| timestamp | TEXT | ISO timestamp |

### `ibkr_configs`
| Column | Type | Purpose |
|---|---|---|
| email | TEXT PK | Student email |
| host | TEXT | TWS/Gateway host (default 127.0.0.1) |
| port | INTEGER | TWS port (7497=paper, 7496=live) |
| client_id | INTEGER | IBKR client ID |
| updated_at | TEXT | ISO timestamp |

### `broker_accounts` (NEW -- multi-account)
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| email | TEXT | Owner |
| broker | TEXT | "longport" or "ibkr" |
| account_type | TEXT | "paper" or "live" |
| account_id | TEXT | Broker's account ID (auto-filled on test) |
| nickname | TEXT | User-facing label |
| app_key_enc | TEXT | LongPort app key (encrypted) |
| app_secret_enc | TEXT | LongPort app secret (encrypted) |
| access_token_enc | TEXT | LongPort access token (encrypted) |
| ibkr_host | TEXT | IBKR TWS host |
| ibkr_port | INTEGER | IBKR TWS port |
| is_connected | INTEGER | 0/1 last test result |
| last_tested | TEXT | ISO timestamp of last test |
| last_error | TEXT | Last connection error |
| created_at | TEXT | ISO timestamp |
| UNIQUE(email, broker, account_type) | | One account per type per broker |

### `data_cache`
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| symbol | TEXT | e.g. "700.HK" |
| timeframe | TEXT | e.g. "1day" |
| source | TEXT | Where data came from ("ibkr", "yahoo", "r2", "fmp") |
| bar_count | INTEGER | Number of bars cached |
| bars_json | TEXT | JSON array of OHLCV bars |
| fetched_at | TEXT | ISO timestamp (TTL basis) |
| UNIQUE(symbol, timeframe) | | One cache entry per symbol+timeframe |

### `indicators`
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| indicator_id | TEXT UNIQUE | e.g. "EMA", "RSI", "CUSTOM_XYZ" |
| name | TEXT | Full name |
| display_name | TEXT | Short display label |
| category | TEXT | "trend", "momentum", "volatility", "volume", "custom" |
| description | TEXT | What it does |
| output_type | TEXT | "single", "dual", "triple" |
| output_labels | TEXT | JSON array of output names |
| params | TEXT | JSON array of parameter definitions |
| calc_code | TEXT | Python calculation code |
| usage_example | TEXT | e.g. "calc_ema(close, 20)" |
| pine_script_equivalent | TEXT | TradingView equivalent |
| tradingview_name | TEXT | TV indicator name |
| created_by | TEXT | "system" or student email |
| created_at | TEXT | ISO timestamp |
| is_builtin | INTEGER | 1 for seeded indicators |
| is_approved | INTEGER | 1 if approved for use |
| usage_count | INTEGER | How many strategies use it |

---

## 5. API Routes

### Health & Debug
| Method | Path | Description |
|---|---|---|
| GET | `/health`, `/api/health` | Health check with architecture info (Railway/local detection) |
| GET | `/api/debug-fmp` | FMP API connectivity test |
| GET | `/api/debug-env` | Environment variable dump (FMP, R2, HOSTING) |
| GET | `/api/config` | Public config: version, hosting, architecture |

### Auth & Registration
| Method | Path | Description |
|---|---|---|
| POST | `/api/login` | Email-based login (no password) |
| GET | `/api/me` | Get student profile |
| POST | `/api/register` | Register student with LP credentials |
| POST | `/api/settings` | Update settings (central URL, etc.) |

### Strategies
| Method | Path | Description |
|---|---|---|
| GET | `/api/strategies-library` | Returns strategies_library.json |
| POST | `/api/strategy` | Create/update strategy |
| DELETE | `/api/strategy/{id}` | Delete strategy |
| PUT | `/api/strategy/{id}/toggle` | Activate/deactivate strategy |
| GET | `/api/strategies/{email}` | List all strategies for a student |
| GET | `/api/strategies/{id}/detail` | Single strategy with full config |
| PUT | `/api/strategies/{id}/backtest-results` | Store backtest results on strategy |
| PUT | `/api/strategies/{id}/allocation` | Update capital allocation |
| POST | `/api/strategies/{id}/trade` | Log a manual trade against a strategy |

### Backtesting
| Method | Path | Description |
|---|---|---|
| POST | `/api/backtest/run` | Run backtest with library/builder strategy |
| POST | `/api/backtest/optimize` | Walk-forward optimization + Monte Carlo |
| POST | `/api/backtest/run-script` | Run backtest with custom Python script |
| POST | `/api/backtest/sweep-script` | Parameter sweep for script strategies |
| POST | `/api/backtest/prewarm-bulk` | Pre-cache data for multiple symbols |
| GET | `/api/backtest/cache-inventory` | List cached data symbols |

### Deployment
| Method | Path | Description |
|---|---|---|
| POST | `/api/deploy` | Deploy all active strategies as bot processes |
| POST | `/api/stop` | Stop running bot processes |
| POST | `/api/restart` | Stop + redeploy |
| GET | `/api/status/{email}` | Bot status, PID check via psutil |
| GET | `/api/logs/{email}` | Master bot log tail |
| GET | `/api/logs/{email}/{strategy_id}` | Per-strategy log tail |
| POST | `/api/download-script` | Download standalone bot script |

### Brokers
| Method | Path | Description |
|---|---|---|
| POST | `/api/ibkr-config` | Save IBKR connection config |
| GET | `/api/ibkr-config` | Get IBKR config |
| POST | `/api/test-ibkr-connection` | Test IBKR connectivity |
| POST | `/api/test-connection` | Test LongPort connectivity |
| GET | `/api/broker-accounts` | List all broker accounts for student |
| POST | `/api/broker-accounts` | Add broker account |
| DELETE | `/api/broker-accounts/{id}` | Remove broker account |
| POST | `/api/broker-accounts/{id}/test` | Test broker account connection |

### Data
| Method | Path | Description |
|---|---|---|
| GET | `/api/data-cache` | List cached data entries |
| DELETE | `/api/data-cache` | Clear cache for a symbol |
| POST | `/api/data-prefetch` | Prefetch data for a symbol via waterfall |
| GET | `/api/fundamentals/{symbol}` | Company fundamentals from FMP |

### Indicators
| Method | Path | Description |
|---|---|---|
| GET | `/api/indicators` | List all indicators (appears twice - line 755 and 1371) |
| GET | `/api/indicators/{id}` | Single indicator detail |
| POST | `/api/indicators` | Register new custom indicator |
| DELETE | `/api/indicators/{id}` | Delete indicator |

### Screener
| Method | Path | Description |
|---|---|---|
| POST | `/api/screen-now` | Run screener for a bot type on a universe |
| GET | `/api/screener-results` | Get stored screener results |
| GET | `/api/approval-status` | Check instructor approval status |

### Trades & Misc
| Method | Path | Description |
|---|---|---|
| GET | `/api/trades/{email}` | Get trade history |
| POST | `/api/trade` | Record a trade (from bot or manual) |
| GET | `/api/symbol-search` | Search symbols.json |
| POST | `/api/validate-script` | Validate custom Python script syntax |
| GET | `/` | Serve static/index.html |

---

## 6. Bot Templates

| File | Broker | Style | Key Placeholders |
|---|---|---|---|
| `bot_template_lp_master.py` | LongPort | `__PLACEHOLDER__` | `__EMAIL__`, `__APP_KEY__`, `__APP_SECRET__`, `__ACCESS_TOKEN__`, `__STRATEGIES_LIST__`, `__SIGNAL_FUNCTIONS__` |
| `bot_template.py` | LongPort | `str.format()` | `{email}`, `{app_key}`, `{strategies_json}` (old, kept for download endpoint) |
| `bot_template_ibkr_prod.py` | IBKR | `__PLACEHOLDER__` | `__STRATEGY_NAME__`, `__SYMBOL__`, `__PORT__`, `__CLIENT_ID__`, `__SIGNAL_CODE__`, `__LOT_SIZE__`, `__STOP_LOSS_PCT__`, `__TAKE_PROFIT_PCT__` |
| `bot_template_simple.py` | LP + IBKR | `__PLACEHOLDER__` | `__EMAIL__`, `__SYMBOL__`, `__LOG_DIR__` (test bots: place one order, wait 30s, cancel) |
| `bot_template_options.py` | IBKR | `__PLACEHOLDER__` | `__UNDERLYING__`, `__STRATEGY_TYPE__`, `__PUT_DELTA__`, `__CALL_DELTA__`, `__DRY_RUN__` |
| `bot_template_ibkr.py` | IBKR | `str.format()` | Old IBKR master (superseded by ibkr_prod) |
| `generator/bot_template_grid.py` | LongPort | `str.format()` | ATR-based grid, daily reset (standalone legacy) |

---

## 7. Strategy Library

| ID | Name | Category | Description |
|---|---|---|---|
| `EMA_CROSS` | EMA Crossover | Trend Following | Fast/slow EMA crossover |
| `RSI_MEAN_REVERSION` | RSI Mean Reversion | Mean Reversion | Buy oversold, sell overbought |
| `BB_GRID` | Bollinger Band Grid | Grid Trading | Grid within BB bands |
| `MOMENTUM_BREAKOUT` | Momentum Breakout | Breakout | RSI > 55 entry |
| `MACD_MOMENTUM` | MACD Momentum | Momentum | MACD line/signal crossover |
| `VWAP_REVERSION` | VWAP Reversion | VWAP | Mean reversion to VWAP |
| `SYMMETRIC_GRID` | Symmetric Grid | Grid Trading | ATR-spaced buy grid with TP sells |
| `BUFFETT_BOT` | Buffett Bot | Quality + Trend | SMA200, RSI fair zone, OBV accumulation |
| `GRAHAM_BOT` | Graham Bot | Deep Value | Near 52w low, RSI oversold, below SMA200 |
| `LIVERMORE_BOT` | Livermore Bot | Pivot Breakout | New highs, volume surge, ATR expansion |
| `DALIO_BOT` | Dalio Bot | All Weather | SMA50 trend, low ATR, balanced volume |
| `SIMONS_BOT` | Simons Bot | Statistical Reversion | Z-score, RSI oversold, low volume pullback |
| `TURTLE_TRADER` | Turtle Trader | Donchian Breakout | N-bar high breakout with volume confirm |
| `SOROS_BOT` | Soros Bot | Reflexivity Momentum | Full EMA alignment, MACD positive, volume surge |

---

## 8. What's Confirmed Working (code evidence)

- **FastAPI server** starts and serves frontend (`run.py`, `main.py`)
- **SQLite database** initializes all 7 tables with migrations (`database.py:init_db`)
- **Fernet encryption** for credentials with auto-key generation (`database.py`)
- **Strategy CRUD** with full JSON serialization (`database.py`, `main.py`)
- **Backtest engine** with 20+ indicators, commission/slippage, next-bar-open execution (`backtest.py`)
- **Signal code generation** from Builder conditions to Python (`generate.py:generate_signal_code`)
- **Library -> Builder** condition mapping for 13 library strategies (`generate.py:_LIBRARY_CONDITIONS`)
- **IBKR production bot** generation with `__PLACEHOLDER__` substitution and verification (`generate.py:generate_ibkr_bot_prod`)
- **LongPort master bot** with shared connections (`generate.py:generate_lp_master_bot`)
- **Options bot** generation for SPX 0DTE with iron condors, spreads (`generate.py:generate_options_bot`)
- **Data waterfall** through 5 sources with local caching + TTL (`data_manager.py`)
- **Process management** with subprocess launch, PID tracking via psutil (`main.py`)
- **IBKR connector** with quote, order, and position APIs (`ibkr_connector.py`)
- **Stock screener** for 7 famous investor styles (`screener.py`)
- **16 built-in indicators** seeded on startup (`indicators_seed.py`)
- **Multi-account broker system** with DB, API, and frontend (`database.py`, `main.py`, `index.html`)
- **Windows installer** with Python auto-install, scheduled task creation (`install.ps1`)
- **Railway deployment** config with health check (`railway.json`, `Procfile`)
- **Position reconciliation** at bot startup compares local vs IBKR state (`bot_template_ibkr_prod.py`)
- **Enhanced trade logging** with CSV audit trail including indicator values, bar date (`bot_template_ibkr_prod.py`)

---

## 9. Known Issues / TODOs

### From code comments
- `backtest.py:514` -- `TODO: Wire GET /api/fundamentals/{symbol} to filter entries` (Buffett/Graham screener)
- `backtest.py:529` -- Same TODO duplicated

### Duplicate route
- `/api/indicators` is registered twice (line 755 and 1371 in main.py). The second will shadow the first.

### Old bot template still used
- `generate_master_bot()` (old LP template using `str.format()`) is still called at line 405 for the download-script endpoint. Works fine for downloads but uses the legacy StrategyRunner which has simpler signal logic.

### Broker accounts UNIQUE constraint
- `broker_accounts` has `UNIQUE(email, broker, account_type)` which means a student can only have one paper and one live account per broker. If multiple paper IBKR accounts are needed (different ports), this constraint will block.

### Deploy fallback
- If `generate_lp_master_bot()` fails, the deploy endpoint falls back to the old `generate_master_bot()` which doesn't use Builder compute_signals.

### Frontend: old broker JS references
- Some test files may reference old DOM IDs (`lp-connected`, `lp-form`, etc.) that no longer exist since the Brokers page was rewritten to multi-account.

### Grid bot
- `generator/bot_template_grid.py` is a standalone legacy template not integrated into the main deploy flow. The `SYMMETRIC_GRID` strategy uses `GridRunner` in `bot_template.py` instead.

### R2 credentials
- R2 env vars (`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`) are read at import time in `backtest.py`, not lazy-loaded. If set after import, they won't take effect.

---

## 10. Data Flow

### Backtest Request
```
Browser                FastAPI (main.py)           Railway / Local
   |                        |                           |
   |-- POST /backtest/run ->|                           |
   |                        |-- fetch_bars_waterfall -->|
   |                        |   1. Local SQLite cache   |
   |                        |   2. IBKR (if connected)  |
   |                        |   3. R2 parquet (boto3)   |
   |                        |   4. Yahoo Finance        |
   |                        |   5. FMP API              |
   |                        |<-- OHLCV bars ------------|
   |                        |                           |
   |                        |-- run_backtest()          |
   |                        |   (indicators, signals,   |
   |                        |    portfolio tracking,    |
   |                        |    commission/slippage)   |
   |                        |                           |
   |<-- JSON results -------|                           |
```

### Trade Signal (IBKR)
```
IBKR prod bot (subprocess)
   |
   |-- bar_loop(): poll every N minutes
   |   |-- ib.reqHistoricalDataAsync() -> new bars
   |   |-- compute_signals(data_buffer)
   |   |   (generated from Builder conditions)
   |   |
   |   |-- signal fires? -> place_order()
   |       |-- ib.placeOrder(contract, MarketOrder)
   |       |-- wait for fill (30s timeout)
   |       |-- capture: execId, fill price, commission
   |       |-- log_trade() -> trades/trades_XXXX_all.csv
   |       |-- POST /api/trade -> local app (Trades tab)
   |       |-- POST /api/trade -> central (instructor dashboard)
   |       |-- save_state() -> state/pos_XXXX.json
```

### Trade Signal (LongPort Master)
```
LP master bot (subprocess)
   |
   |-- bar_loop() thread: poll every 60s
   |   |-- for each StrategyState:
   |       |-- quote_ctx.candlesticks() -> new bars
   |       |-- compute_signals_XXXX(data_buffer)
   |       |
   |       |-- signal fires? -> place_order()
   |           |-- quote_ctx.quote() -> get current price
   |           |-- trade_ctx.submit_order() (limit, 0.2% from market)
   |           |-- log_trade() -> trades/trades_XXXX_all.csv
   |           |-- POST /api/trade -> local + central
   |           |-- save_state() -> state/pos_XXXX.json
```

---

## 11. Environment Variables

| Variable | Default | Where Used | Purpose |
|---|---|---|---|
| `PORT` | `8080` | config.py, run.py, main.py | FastAPI server port |
| `CENTRAL_API_URL` | `""` | config.py, main.py | Railway URL for backtesting + heartbeats |
| `FMP_API_KEY` | `""` | config.py, backtest.py | Financial Modeling Prep API key for OHLCV data |
| `FERNET_KEY` | `""` | config.py | Fernet encryption key (Railway env). If empty, reads `.fernet.key` file |
| `DB_PATH` | `./quantx_deployer.db` | config.py | SQLite database path |
| `APP_BASE_DIR` | script parent | config.py | Override base directory |
| `DATA_DIR` | same as BASE_DIR | config.py | Override data directory (Railway volume) |
| `ADMIN_PIN` | `quantx2025` | config.py | Admin authentication PIN |
| `HOSTING` | `vps` | config.py | "vps" or "railway" mode |
| `INSTRUCTOR_KEY` | `quantx2025` | main.py | Bulk prewarm auth key |
| `R2_ENDPOINT_URL` | `""` | backtest.py | Cloudflare R2 S3-compatible endpoint |
| `R2_ACCESS_KEY_ID` | `""` | backtest.py | R2 access key |
| `R2_SECRET_ACCESS_KEY` | `""` | backtest.py | R2 secret key |
| `R2_BACKTEST_BUCKET` | `backtest-data` | backtest.py | R2 bucket name for cached data |

---

## 12. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.111.0 | Web framework |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `pydantic` | 2.7.1 | Request/response validation |
| `cryptography` | 42.0.7 | Fernet encryption for credentials |
| `longport` | 3.0.23 | LongPort OpenAPI SDK (HK/SG/US trading) |
| `python-multipart` | 0.0.9 | Form data parsing |
| `httpx` | 0.27.0 | HTTP client (heartbeats, LP template) |
| `requests` | 2.31.0 | HTTP client (trade reporting, FMP) |
| `boto3` | 1.34.100 | AWS S3 SDK (Cloudflare R2 access) |
| `numpy` | 1.26.4 | Numerical operations (backtest engine) |
| `pandas` | 2.2.1 | DataFrame operations (backtest) |
| `ib_insync` | 0.9.86 | IBKR TWS API wrapper |
| `nest-asyncio` | 1.6.0 | Allow nested event loops (ib_insync compat) |
| `psutil` | 5.9.8 | Process status checking (PID monitoring) |
| `yfinance` | 0.2.54 | Yahoo Finance data fallback |
| `pytz` | 2024.1 | Timezone handling (US/Eastern, Asia/Singapore) |

---

## 13. Setup / Run Instructions (Windows)

### Quick start (developer)
```bash
cd quantx-deployer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Create .env file:
echo CENTRAL_API_URL=https://quantx-deploy.up.railway.app > .env
echo PORT=8080 >> .env
# Run:
python run.py
# Opens http://localhost:8080 in browser
```

### Student VPS install
```powershell
# From the quantx-deployer directory:
.\install.ps1 -CentralApiUrl "https://quantx-deploy.up.railway.app"
# This will:
#   1. Install Python 3.11 if missing
#   2. Copy files to C:\QuantXDeployer
#   3. pip install dependencies
#   4. Create Windows Scheduled Task (auto-start on boot)
#   5. Start the server
#   6. Open browser
```

### IBKR setup
1. Install TWS or IB Gateway
2. Enable API connections: TWS > File > Global Config > API > Settings
3. Check "Enable ActiveX and Socket Clients"
4. Port: 7497 (paper), 7496 (live)
5. In QuantX: Brokers tab > Add Account > IBKR > enter host:port > Test

### LongPort setup
1. Register at longport.com, get App Key, App Secret, Access Token
2. In QuantX: Brokers tab > Add Account > LongPort > enter credentials > Test

---

## 14. Pending Work

### In-progress (from this session)
1. **Commit and push** -- all three fixes (enhanced trade logging, position reconciliation, LP master template) plus broker JS functions and deploy endpoint update are coded but not committed.

### Not yet implemented
1. **New Bot modal account selector** -- should show actual connected broker_accounts instead of LP/IBKR pill toggle. Currently the deploy endpoint still reads credentials from the `students` table, not `broker_accounts`.
2. **Deploy using broker_accounts credentials** -- the deploy endpoint should look up broker account by ID for LP credentials, not rely solely on the legacy `students` table.
3. **Multiple paper accounts** -- `UNIQUE(email, broker, account_type)` constraint limits to one paper + one live per broker. May need to relax.
4. **LongPort candlestick bar periods** -- the LP master template maps timeframe strings to `Period` enum, but the strategy risk config stores timeframe differently than the candlestick API expects. Needs validation.
5. **Frontend: Brokers page delete confirmation** -- `deleteBrokerAccount()` passes `esc(nickname)` into a string literal in an onclick, which will break if nickname contains single quotes.
6. **Options backtester** (separate project `quantx-options-backtester/`) -- Layers 3-5 (simulate_one_day, date-range loop, Streamlit UI) are not yet built.
7. **Duplicate `/api/indicators` route** -- needs deduplication (line 755 vs 1371).

---

*Document generated 2026-04-15 by Claude Code audit.*
