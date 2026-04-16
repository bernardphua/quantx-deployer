"""QuantX -- LongPort master bot template.

One process, one QuoteContext, one TradeContext, multiple strategies.
Uses __PLACEHOLDER__ substitution (same pattern as IBKR prod template).
"""

LP_MASTER_TEMPLATE = r'''#!/usr/bin/env python3
"""
================================================================================
QuantX LongPort Master Bot
Email     : __EMAIL__
Strategies: __STRATEGY_COUNT__
Generated : by QuantX Deployer
================================================================================

Architecture:
  ONE QuoteContext  -- shared by all strategies (1 WebSocket)
  ONE TradeContext  -- shared by all strategies (1 WebSocket)
  Total connections: 2 (well within LongPort's 10-connection limit)
"""
import os, sys, json, math, csv, time, signal as _signal, logging, threading, decimal
from collections import deque
from datetime import datetime, timezone, timedelta

import requests

EMAIL          = '__EMAIL__'
CENTRAL_API_URL = '__CENTRAL_API_URL__'
LOCAL_API_URL  = 'http://127.0.0.1:8080'
APP_KEY        = '__APP_KEY__'
APP_SECRET     = '__APP_SECRET__'
ACCESS_TOKEN   = '__ACCESS_TOKEN__'

LOG_DIR    = '__LOG_DIR__'
TRADES_DIR = '__TRADES_DIR__'
STATE_DIR  = '__STATE_DIR__'
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(TRADES_DIR, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)

SGT = timezone(timedelta(hours=8))
HEARTBEAT_INTERVAL = 60

# Strategies list -- injected at generation time
STRATEGIES = __STRATEGIES_LIST__

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, '__LOG_NAME__'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('quantx-lp-master')

_shutdown = threading.Event()

def _handle_signal(signum, frame):
    logger.warning('Signal %s -- shutting down', signum)
    _shutdown.set()

_signal.signal(_signal.SIGTERM, _handle_signal)
_signal.signal(_signal.SIGINT, _handle_signal)


# ── Indicator functions (same as IBKR prod) ───────────────────────────────

def calc_ema(vals, period):
    r = [None]*len(vals); k = 2.0/(period+1)
    for i in range(len(vals)):
        if i < period-1: continue
        if r[i-1] is None: r[i] = sum(vals[max(0,i-period+1):i+1])/period
        else: r[i] = vals[i]*k + r[i-1]*(1-k)
    return r

def calc_sma(vals, period):
    r = [None]*len(vals)
    for i in range(period-1, len(vals)): r[i] = sum(vals[i-period+1:i+1])/period
    return r

def calc_rsi(vals, period=14):
    r = [None]*len(vals)
    for i in range(period, len(vals)):
        g = [max(0, vals[j]-vals[j-1]) for j in range(i-period+1, i+1)]
        l = [max(0, vals[j-1]-vals[j]) for j in range(i-period+1, i+1)]
        ag, al = sum(g)/period, sum(l)/period
        r[i] = 100.0 if al == 0 else 100 - 100/(1 + ag/al)
    return r

def calc_macd(vals, fast=12, slow=26, sig=9):
    ef, es = calc_ema(vals, fast), calc_ema(vals, slow)
    ml = [None if a is None or b is None else a-b for a,b in zip(ef, es)]
    sl = [None]*len(ml); k = 2.0/(sig+1); sv = None
    for i, v in enumerate(ml):
        if v is None: continue
        sv = v if sv is None else v*k + sv*(1-k)
        sl[i] = sv
    hist = [None if a is None or b is None else a-b for a,b in zip(ml, sl)]
    return ml, sl, hist

def calc_bbands(vals, period=20, std=2.0):
    mid = calc_sma(vals, period); u=[None]*len(vals); l=[None]*len(vals)
    for i in range(period-1, len(vals)):
        if mid[i] is None: continue
        sd = math.sqrt(sum((vals[i-j]-mid[i])**2 for j in range(period))/period)
        u[i] = mid[i]+std*sd; l[i] = mid[i]-std*sd
    return u, mid, l

def calc_atr(highs, lows, closes, period=14):
    trs = [None]; r = [None]*len(closes)
    for i in range(1, len(closes)):
        trs.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
    for i in range(period, len(trs)):
        if None in trs[i-period+1:i+1]: continue
        r[i] = sum(trs[i-period+1:i+1])/period
    return r

def calc_roc(vals, period=10):
    r = [None]*len(vals)
    for i in range(period, len(vals)):
        if vals[i-period] and vals[i-period] != 0:
            r[i] = (vals[i]-vals[i-period])/vals[i-period]*100
    return r

def calc_zscore(vals, period=20):
    r = [None]*len(vals)
    for i in range(period, len(vals)):
        w = vals[i-period+1:i+1]; m = sum(w)/period
        s = (sum((x-m)**2 for x in w)/period)**0.5
        r[i] = (vals[i]-m)/s if s > 0 else 0
    return r

def calc_obv(closes, volumes):
    r = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]: r.append(r[-1]+volumes[i])
        elif closes[i] < closes[i-1]: r.append(r[-1]-volumes[i])
        else: r.append(r[-1])
    return r

def calc_vwap(highs, lows, closes, volumes):
    r = [None]*len(closes); ctv = cv = 0.0
    for i in range(len(closes)):
        tp = (highs[i]+lows[i]+closes[i])/3; ctv += tp*volumes[i]; cv += volumes[i]
        r[i] = ctv/cv if cv > 0 else closes[i]
    return r

def calc_stoch(highs, lows, closes, k_period=14, d_period=3):
    kl = [None]*len(closes)
    for i in range(k_period-1, len(closes)):
        h = max(highs[i-k_period+1:i+1]); l = min(lows[i-k_period+1:i+1])
        kl[i] = (closes[i]-l)/(h-l)*100 if h != l else 50
    dl = [None]*len(closes)
    for i in range(k_period+d_period-2, len(closes)):
        vs = [kl[j] for j in range(i-d_period+1,i+1) if kl[j] is not None]
        if len(vs) == d_period: dl[i] = sum(vs)/d_period
    return kl, dl

def calc_williams_r(highs, lows, closes, period=14):
    r = [None]*len(closes)
    for i in range(period-1, len(closes)):
        h = max(highs[i-period+1:i+1]); l = min(lows[i-period+1:i+1])
        r[i] = (h-closes[i])/(h-l)*-100 if h != l else -50
    return r

def calc_donchian(highs, lows, period=20):
    u = [None]*len(highs); l = [None]*len(lows)
    for i in range(period-1, len(highs)):
        u[i] = max(highs[i-period+1:i+1]); l[i] = min(lows[i-period+1:i+1])
    return u, l

def calc_wma(vals, period):
    r = [None]*len(vals); wts = list(range(1,period+1)); ws = sum(wts)
    for i in range(period-1, len(vals)):
        r[i] = sum(vals[i-period+1+j]*wts[j] for j in range(period))/ws
    return r

def calc_hma(vals, period):
    h = period//2; sq = max(int(period**0.5),1)
    wh = calc_wma(vals, h); wf = calc_wma(vals, period)
    d = [2*wh[i]-wf[i] if wh[i] is not None and wf[i] is not None else 0 for i in range(len(vals))]
    return calc_wma(d, sq)

def calc_supertrend(highs, lows, closes, period=10, mult=3.0):
    atr_v = calc_atr(highs, lows, closes, period)
    di = [1]*len(closes); st = [None]*len(closes)
    ub = [None]*len(closes); lb = [None]*len(closes)
    for i in range(period, len(closes)):
        if atr_v[i] is None: continue
        mid = (highs[i]+lows[i])/2
        ub[i] = mid+mult*atr_v[i]; lb[i] = mid-mult*atr_v[i]
        if i == period: di[i]=1; st[i]=lb[i]; continue
        if di[i-1] == 1:
            if lb[i-1]: lb[i] = max(lb[i], lb[i-1])
            if closes[i] < lb[i]: di[i]=-1; st[i]=ub[i]
            else: di[i]=1; st[i]=lb[i]
        else:
            if ub[i-1]: ub[i] = min(ub[i], ub[i-1])
            if closes[i] > ub[i]: di[i]=1; st[i]=lb[i]
            else: di[i]=-1; st[i]=ub[i]
    return st, di


# ── Per-strategy signal functions (GENERATED) ─────────────────────────────
__SIGNAL_FUNCTIONS__


# ── HK tick rounding ──────────────────────────────────────────────────────

def hk_tick_round(p):
    if p < 0.25: tick = 0.001
    elif p < 0.5: tick = 0.005
    elif p < 10: tick = 0.010
    elif p < 20: tick = 0.020
    elif p < 100: tick = 0.050
    elif p < 200: tick = 0.100
    elif p < 500: tick = 0.200
    elif p < 1000: tick = 0.500
    elif p < 2000: tick = 1.000
    elif p < 5000: tick = 2.000
    else: tick = 5.000
    return round(math.floor(p / tick) * tick, 4)


# ── Trade CSV logging ─────────────────────────────────────────────────────

CSV_FIELDS = ['execId','order_id','datetime','bar_date','strategy','symbol',
              'side','quantity','price','commission','pnl','signal',
              'indicator_values','bar_close','orderRef']

def ensure_csv(trades_file):
    if not os.path.exists(trades_file):
        with open(trades_file, 'w', newline='') as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()

def log_trade(strategy_id, symbol, side, qty, price, pnl=0.0, signal='',
              bar_date='', indicator_values='', bar_close=0.0, order_id=''):
    trades_file = os.path.join(TRADES_DIR, f'trades_{strategy_id}_all.csv')
    ensure_csv(trades_file)
    eid = f'{strategy_id}_{datetime.utcnow():%Y%m%d%H%M%S%f}'
    with open(trades_file, 'a', newline='') as f:
        csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow({
            'execId': eid, 'order_id': order_id or eid,
            'datetime': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'bar_date': bar_date, 'strategy': strategy_id,
            'symbol': symbol, 'side': side,
            'quantity': qty, 'price': round(price, 6),
            'commission': 0, 'pnl': round(pnl, 2), 'signal': signal,
            'indicator_values': indicator_values,
            'bar_close': round(bar_close, 6), 'orderRef': strategy_id})
    logger.info(f'[TRADE][{strategy_id}] {side} {qty} {symbol} @ {price:.4f} | pnl=${pnl:+.2f} | signal={signal}')
    _payload = {'email': EMAIL, 'strategy_id': strategy_id, 'symbol': symbol,
                'side': side.lower(), 'price': float(price), 'qty': float(qty), 'pnl': float(pnl)}
    try: requests.post(f'{LOCAL_API_URL}/api/trade', json=_payload, timeout=2)
    except Exception: pass
    if CENTRAL_API_URL:
        try: requests.post(f'{CENTRAL_API_URL}/api/trade', json=_payload, timeout=3)
        except Exception: pass


# ── Strategy state ─────────────────────────────────────────────────────────

class StrategyState:
    """Per-strategy position and data tracking."""
    def __init__(self, config, compute_fn):
        self.sid = config['strategy_id']
        self.symbol = config['symbol']
        self.arena = config.get('arena', 'HK')
        self.timeframe = config.get('timeframe', '1day')
        self.compute_fn = compute_fn
        self.risk = config.get('risk', {})
        self.lot_size = int(self.risk.get('lots', 100))
        self.tp_pct = float(self.risk.get('tp_pct', 5)) / 100
        self.sl_pct = float(self.risk.get('sl_pct', 2)) / 100
        if self.tp_pct > 1: self.tp_pct /= 100
        if self.sl_pct > 1: self.sl_pct /= 100
        self.has_short = bool(config.get('has_short', False))

        # Position state: first check injected initial state, then state file
        self.current_position = int(config.get('initial_position', 0))
        self.entry_price = float(config.get('initial_entry_price', 0.0))
        self.data_buffer = deque(maxlen=500)

        self.pos_file = os.path.join(STATE_DIR, f'pos_{self.sid}.json')
        self._load_state()

    def _load_state(self):
        """Load from state file. Only overrides if file has a non-zero position
        and we don't already have an injected position."""
        try:
            if os.path.exists(self.pos_file):
                s = json.load(open(self.pos_file))
                file_pos = int(s.get('current_position', 0))
                file_entry = float(s.get('entry_price', 0.0))
                # State file takes precedence (it's the most recent truth)
                if file_pos != 0:
                    self.current_position = file_pos
                    self.entry_price = file_entry
                    logger.info(f'[{self.sid}] Restored from file: pos={self.current_position} entry={self.entry_price:.4f}')
                elif self.current_position != 0:
                    logger.info(f'[{self.sid}] Using injected state: pos={self.current_position} entry={self.entry_price:.4f}')
        except Exception as e:
            logger.warning(f'[{self.sid}] State load failed: {e}')
            if self.current_position != 0:
                logger.info(f'[{self.sid}] Falling back to injected state: pos={self.current_position}')

    def save_state(self):
        try:
            json.dump({'current_position': self.current_position,
                       'entry_price': self.entry_price}, open(self.pos_file, 'w'))
        except Exception as e:
            logger.warning(f'[{self.sid}] State save failed: {e}')


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    logger.info('='*72)
    logger.info('QuantX LongPort Master Bot -- %s', EMAIL)
    logger.info('Strategies: %d', len(STRATEGIES))
    logger.info('='*72)

    # LongPort imports
    try:
        from longport.openapi import (
            Config, QuoteContext, TradeContext, SubType, TopicType,
            OrderSide, OrderType, TimeInForceType, OrderStatus,
        )
    except ImportError:
        logger.error('longport package not installed')
        return

    # ONE connection for everything
    cfg = Config(app_key=APP_KEY, app_secret=APP_SECRET, access_token=ACCESS_TOKEN)
    quote_ctx = QuoteContext(cfg)
    trade_ctx = TradeContext(cfg)
    logger.info('LongPort connected (2 connections: quote + trade)')

    # Build strategy states with their compute_signals functions
    # The __SIGNAL_FUNCTIONS__ block defines compute_signals_XXXX for each strategy
    states = []
    for s in STRATEGIES:
        fn_name = f'compute_signals_{s["strategy_id"]}'
        fn = globals().get(fn_name)
        if fn is None:
            logger.warning(f'[{s["strategy_id"]}] No compute function {fn_name}, skipping')
            continue
        st = StrategyState(s, fn)
        states.append(st)
        logger.info(f'[{st.sid}] {st.symbol} lot={st.lot_size} tp={st.tp_pct*100:.1f}% sl={st.sl_pct*100:.1f}%')

    if not states:
        logger.error('No valid strategies. Exiting.')
        return

    # Subscribe ALL symbols at once
    all_symbols = list(set(st.symbol for st in states))
    logger.info('Subscribing to %d symbols: %s', len(all_symbols), all_symbols)

    # Fetch initial quotes
    try:
        quotes = quote_ctx.quote(all_symbols)
        for q in quotes:
            logger.info('Initial: %s = %s', q.symbol, q.last_done)
    except Exception as e:
        logger.warning('Initial quote fetch failed: %s', e)

    # Fetch warmup bars for each strategy using candlestick API
    from longport.openapi import Period, AdjustType
    period_map = {'1min': Period.Min_1, '5min': Period.Min_5,
                  '15min': Period.Min_15, '30min': Period.Min_30,
                  '1hour': Period.Min_60, '4hour': Period.Min_60,
                  '1day': Period.Day, '1week': Period.Week}

    for st in states:
        try:
            p = period_map.get(st.timeframe, Period.Day)
            candles = quote_ctx.candlesticks(st.symbol, p, 200, AdjustType.ForwardAdjust)
            bars = [{'date': str(c.timestamp), 'open': float(c.open),
                     'high': float(c.high), 'low': float(c.low),
                     'close': float(c.close), 'volume': float(c.volume)}
                    for c in candles]
            st.data_buffer = deque(bars, maxlen=500)
            logger.info(f'[{st.sid}] Warmup: {len(bars)} bars, last close={bars[-1]["close"]:.4f}')
        except Exception as e:
            logger.warning(f'[{st.sid}] Warmup failed: {e} -- will start from scratch')

    # Order placement helper using shared trade_ctx
    def place_order(st, action, signal='', bar_date='', indicator_values='', bar_close=0.0):
        """Place a limit order 2% below/above market via shared trade_ctx."""
        try:
            quotes = quote_ctx.quote([st.symbol])
            price = float(quotes[0].last_done) if quotes else 0
            if price <= 0:
                logger.warning(f'[{st.sid}] No price for {st.symbol}, cannot place order')
                return

            if st.symbol.endswith('.HK'):
                if action == 'BUY':
                    limit_price = hk_tick_round(price * 0.998)
                else:
                    limit_price = round(math.ceil(price * 1.002 / 0.01) * 0.01, 4)
            else:
                limit_price = round(price * (0.998 if action == 'BUY' else 1.002), 2)

            side = OrderSide.Buy if action == 'BUY' else OrderSide.Sell
            resp = trade_ctx.submit_order(
                symbol=st.symbol,
                order_type=OrderType.LO,
                side=side,
                submitted_quantity=st.lot_size,
                time_in_force=TimeInForceType.Day,
                submitted_price=decimal.Decimal(str(limit_price)),
                remark=f'QuantX {st.sid}'
            )
            order_id = str(resp.order_id)
            logger.info(f'[{st.sid}] ORDER {action} {st.lot_size} {st.symbol} @ {limit_price} | oid={order_id} | signal={signal}')

            # Update position state
            pnl = 0.0
            if action == 'SELL' and st.current_position == 1 and st.entry_price > 0:
                pnl = (price - st.entry_price) * st.lot_size
            elif action == 'BUY' and st.current_position == -1 and st.entry_price > 0:
                pnl = (st.entry_price - price) * st.lot_size
            if action == 'BUY':
                st.current_position = 1
                st.entry_price = price
            else:
                st.current_position = 0
                st.entry_price = 0.0
            st.save_state()

            log_trade(st.sid, st.symbol,
                      'BOT' if action == 'BUY' else 'SLD',
                      st.lot_size, price, pnl, signal,
                      bar_date=bar_date, indicator_values=indicator_values,
                      bar_close=bar_close, order_id=order_id)

        except Exception as e:
            logger.error(f'[{st.sid}] Order failed: {e}')

    def capture_indicator_context(buf_list):
        if not buf_list: return ''
        try:
            close = [b['close'] for b in buf_list]
            parts = [f'bar_close={close[-1]:.4f}']
            try:
                e20 = calc_ema(close, 20)
                if e20[-1] is not None: parts.append(f'ema_20={e20[-1]:.4f}')
            except Exception: pass
            try:
                r14 = calc_rsi(close, 14)
                if r14[-1] is not None: parts.append(f'rsi_14={r14[-1]:.2f}')
            except Exception: pass
            return ','.join(parts)
        except Exception: return ''

    # Bar polling loop -- fetches new bars for ALL strategies
    def bar_loop():
        logger.info('Bar loop started')
        last_dates = {st.sid: (list(st.data_buffer)[-1]['date'] if st.data_buffer else '') for st in states}
        while not _shutdown.is_set():
            _shutdown.wait(60)  # poll every 60s
            if _shutdown.is_set(): break
            for st in states:
                try:
                    p = period_map.get(st.timeframe, Period.Day)
                    candles = quote_ctx.candlesticks(st.symbol, p, 10, AdjustType.ForwardAdjust)
                    bars = [{'date': str(c.timestamp), 'open': float(c.open),
                             'high': float(c.high), 'low': float(c.low),
                             'close': float(c.close), 'volume': float(c.volume)}
                            for c in candles]
                    new = [b for b in bars if b['date'] > last_dates.get(st.sid, '')]
                    if not new: continue
                    st.data_buffer.extend(new)
                    last_dates[st.sid] = new[-1]['date']
                    logger.info(f'[{st.sid}] Bar: {new[-1]["date"]} close={new[-1]["close"]:.4f}')

                    buf_list = list(st.data_buffer)
                    sigs = st.compute_fn(buf_list)
                    if not sigs or sigs[-1] is None: continue
                    sig = sigs[-1]
                    price = buf_list[-1]['close']
                    bar_dt = buf_list[-1]['date']
                    ind_ctx = capture_indicator_context(buf_list)

                    if sig == 'buy' and st.current_position == 0:
                        place_order(st, 'BUY', 'entry_long', bar_dt, ind_ctx, price)
                    elif sig == 'sell' and st.current_position == 1:
                        place_order(st, 'SELL', 'exit_long', bar_dt, ind_ctx, price)
                    elif sig == 'short' and st.current_position == 0 and st.has_short:
                        place_order(st, 'SELL', 'entry_short', bar_dt, ind_ctx, price)
                    elif sig == 'cover' and st.current_position == -1 and st.has_short:
                        place_order(st, 'BUY', 'exit_short', bar_dt, ind_ctx, price)

                    # SL/TP check
                    if st.current_position != 0 and st.entry_price > 0:
                        if st.current_position == 1:
                            if st.sl_pct > 0 and price <= st.entry_price*(1-st.sl_pct):
                                place_order(st, 'SELL', 'stop_loss', bar_dt, ind_ctx, price)
                            elif st.tp_pct > 0 and price >= st.entry_price*(1+st.tp_pct):
                                place_order(st, 'SELL', 'take_profit', bar_dt, ind_ctx, price)
                        elif st.current_position == -1:
                            if st.sl_pct > 0 and price >= st.entry_price*(1+st.sl_pct):
                                place_order(st, 'BUY', 'stop_loss', bar_dt, ind_ctx, price)
                            elif st.tp_pct > 0 and price <= st.entry_price*(1-st.tp_pct):
                                place_order(st, 'BUY', 'take_profit', bar_dt, ind_ctx, price)
                except Exception as e:
                    logger.exception(f'[{st.sid}] Bar loop error: {e}')

    # Heartbeat
    def heartbeat_loop():
        while not _shutdown.is_set():
            _shutdown.wait(HEARTBEAT_INTERVAL)
            if _shutdown.is_set(): break
            for st in states:
                d = {1:'LONG',-1:'SHORT',0:'FLAT'}.get(st.current_position,'?')
                logger.info(f'[HB][{st.sid}] pos={d} entry={st.entry_price:.4f}')

    # Start threads
    bar_t = threading.Thread(target=bar_loop, daemon=True)
    hb_t = threading.Thread(target=heartbeat_loop, daemon=True)
    bar_t.start()
    hb_t.start()

    logger.info('Bot is LIVE. %d strategies, %d symbols, 2 LP connections.', len(states), len(all_symbols))

    try:
        while not _shutdown.is_set():
            _shutdown.wait(1)
    except KeyboardInterrupt:
        pass

    logger.info('Shutting down...')
    for st in states:
        st.save_state()
    logger.info('Bot stopped.')


if __name__ == '__main__':
    main()
'''
