"""
Fetch daily K-line data from exchange APIs and calculate:
  - Price Position at Listing (vs first lister)
  - Post-Listing Return (1d, 7d, 14d, 30d)
"""
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from database import get_conn, _use_pg
PROXIES = {"http": None, "https": None}
KRW_USD = 1 / 1380  # approximate, will fetch real rate

# ── Exchange API adapters ────────────────────────────────────────────────────

def fetch_coinbase(symbol, start_date, end_date):
    """Returns list of (date_str, open, high, low, close)."""
    pair = f"{symbol}-USD"
    candles = []
    # Coinbase returns max 300 candles per call
    cur_start = start_date
    while cur_start < end_date:
        cur_end = min(cur_start + timedelta(days=299), end_date)
        r = requests.get("https://api.exchange.coinbase.com/products/{}/candles".format(pair), params={
            "granularity": 86400,
            "start": cur_start.strftime("%Y-%m-%dT00:00:00Z"),
            "end": cur_end.strftime("%Y-%m-%dT00:00:00Z"),
        }, proxies=PROXIES, timeout=15)
        if r.status_code == 404:
            # Try with USDT
            pair = f"{symbol}-USDT"
            r = requests.get("https://api.exchange.coinbase.com/products/{}/candles".format(pair), params={
                "granularity": 86400,
                "start": cur_start.strftime("%Y-%m-%dT00:00:00Z"),
                "end": cur_end.strftime("%Y-%m-%dT00:00:00Z"),
            }, proxies=PROXIES, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        if not isinstance(data, list) or not data:
            break
        for c in data:
            dt = datetime.fromtimestamp(c[0], tz=timezone.utc).strftime("%Y-%m-%d")
            candles.append((dt, float(c[3]), float(c[2]), float(c[1]), float(c[4])))
        cur_start = cur_end + timedelta(days=1)
        time.sleep(0.2)
    return candles


def fetch_bybit(symbol, start_date, end_date):
    pair = f"{symbol}USDT"
    candles = []
    cur_start = start_date
    while cur_start < end_date:
        cur_end = min(cur_start + timedelta(days=199), end_date)
        r = requests.get("https://api.bybit.com/v5/market/kline", params={
            "category": "spot",
            "symbol": pair,
            "interval": "D",
            "start": int(cur_start.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "end": int(cur_end.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "limit": 200,
        }, proxies=PROXIES, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        items = data.get("result", {}).get("list", [])
        if not items:
            break
        for c in items:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            candles.append((dt, float(c[1]), float(c[2]), float(c[3]), float(c[4])))
        cur_start = cur_end + timedelta(days=1)
        time.sleep(0.2)
    return candles


def fetch_okx(symbol, start_date, end_date):
    pair = f"{symbol}-USDT"
    candles = []
    # OKX: 'after' = newer bound (exclusive), 'before' = older bound (exclusive)
    # Paginate backwards from end_date
    cursor_ts = int(end_date.replace(tzinfo=timezone.utc).timestamp() * 1000) + 86400000
    limit_ts = int(start_date.replace(tzinfo=timezone.utc).timestamp() * 1000) - 86400000
    while True:
        r = requests.get("https://www.okx.com/api/v5/market/history-candles", params={
            "instId": pair,
            "bar": "1D",
            "after": str(cursor_ts),
            "before": str(limit_ts),
            "limit": "100",
        }, proxies=PROXIES, timeout=15)
        if r.status_code != 200:
            break
        data = r.json().get("data", [])
        if not data:
            break
        for c in data:
            dt = datetime.fromtimestamp(int(c[0]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            candles.append((dt, float(c[1]), float(c[2]), float(c[3]), float(c[4])))
        oldest_ts = min(int(c[0]) for c in data)
        if oldest_ts <= limit_ts + 86400000:
            break
        cursor_ts = oldest_ts
        time.sleep(0.2)
    return candles


def fetch_binance(symbol, start_date, end_date):
    pair = f"{symbol}USDT"
    candles = []
    cur_start = start_date
    while cur_start < end_date:
        cur_end = min(cur_start + timedelta(days=499), end_date)
        r = requests.get("https://api.binance.com/api/v3/klines", params={
            "symbol": pair,
            "interval": "1d",
            "startTime": int(cur_start.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "endTime": int(cur_end.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "limit": 500,
        }, proxies=PROXIES, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        if not isinstance(data, list) or not data:
            break
        for c in data:
            dt = datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            candles.append((dt, float(c[1]), float(c[2]), float(c[3]), float(c[4])))
        cur_start = cur_end + timedelta(days=1)
        time.sleep(0.2)
    return candles


def fetch_upbit(symbol, start_date, end_date):
    pair = f"KRW-{symbol}"
    candles = []
    cursor = end_date + timedelta(days=1)
    while cursor > start_date:
        r = requests.get("https://api.upbit.com/v1/candles/days", params={
            "market": pair,
            "to": cursor.strftime("%Y-%m-%dT00:00:00Z"),
            "count": 200,
        }, proxies=PROXIES, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        if not isinstance(data, list) or not data:
            break
        for c in data:
            dt = c["candle_date_time_utc"][:10]
            candles.append((dt,
                            float(c["opening_price"]) * KRW_USD,
                            float(c["high_price"]) * KRW_USD,
                            float(c["low_price"]) * KRW_USD,
                            float(c["trade_price"]) * KRW_USD))
        oldest = min(c["candle_date_time_utc"][:10] for c in data)
        cursor = datetime.strptime(oldest, "%Y-%m-%d") - timedelta(days=1)
        time.sleep(0.2)
    return candles


def fetch_bithumb(symbol, start_date, end_date):
    pair = f"{symbol}_KRW"
    r = requests.get(f"https://api.bithumb.com/public/candlestick/{pair}/24h",
                     proxies=PROXIES, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json().get("data", [])
    candles = []
    for c in data:
        dt = datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        candles.append((dt,
                        float(c[1]) * KRW_USD,
                        float(c[3]) * KRW_USD,
                        float(c[4]) * KRW_USD,
                        float(c[2]) * KRW_USD))
    return candles


FETCHERS = {
    "Coinbase Exchange": fetch_coinbase,
    "ByBit": fetch_bybit,
    "OKX": fetch_okx,
    "Binance": fetch_binance,
    "Upbit": fetch_upbit,
    "Bithumb": fetch_bithumb,
}

# ── Main logic ───────────────────────────────────────────────────────────────

def get_krw_usd_rate():
    """Fetch current KRW/USD rate."""
    try:
        r = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            proxies=PROXIES, timeout=10,
        )
        rate = r.json()["rates"]["KRW"]
        return 1 / rate
    except Exception:
        return 1 / 1380


def build_tasks():
    """Build list of tokens and their listing events."""
    conn = get_conn()
    listings = pd.read_sql_query("SELECT ticker, exchange, listing_date FROM listings", conn)
    conn.close()

    df = listings[listings["exchange"] != "Binance Perps"].copy()
    df["listing_date"] = pd.to_datetime(df["listing_date"])
    df = df.sort_values("listing_date").drop_duplicates(["ticker", "exchange"], keep="first")

    # First date and first exchange per token
    first = df.sort_values("listing_date").drop_duplicates("ticker", keep="first")[["ticker", "listing_date", "exchange"]]
    first.columns = ["ticker", "first_date", "first_exchange"]

    df = df.merge(first, on="ticker")
    return df, first


def fetch_kline(ticker, exchange, start_date):
    """Fetch daily kline for a token from the given exchange.
    Returns (price_map, high_map): date_str -> close, date_str -> high."""
    end_date = datetime.now()
    fetcher = FETCHERS.get(exchange)
    if not fetcher:
        return {}, {}

    candles = fetcher(ticker, start_date, end_date)
    price_map = {}
    high_map = {}
    for dt, o, h, l, c in candles:
        price_map[dt] = c
        high_map[dt] = h
    return price_map, high_map


def find_closest_price(price_map, target_date, max_days=3):
    """Find price on target_date or nearest available within max_days."""
    target = target_date.strftime("%Y-%m-%d")
    if target in price_map:
        return price_map[target]
    for offset in range(1, max_days + 1):
        for delta in [timedelta(days=offset), timedelta(days=-offset)]:
            alt = (target_date + delta).strftime("%Y-%m-%d")
            if alt in price_map:
                return price_map[alt]
    return None


def pct(p0, p1):
    if p0 and p1 and p0 > 0:
        return round((p1 - p0) / p0 * 100, 2)
    return None


def init_kline_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS kline_returns")
    cur.execute("""
        CREATE TABLE kline_returns (
            ticker              TEXT NOT NULL,
            exchange             TEXT NOT NULL,
            listing_date         TEXT NOT NULL,
            is_first             INTEGER,
            days_later           INTEGER,
            source_exchange      TEXT,
            p0                   REAL,
            price_position_pct   REAL,
            return_1d_pct        REAL,
            return_7d_pct        REAL,
            return_14d_pct       REAL,
            return_30d_pct       REAL,
            peak_14d_pct         REAL,
            PRIMARY KEY (ticker, exchange)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def run():
    global KRW_USD
    KRW_USD = get_krw_usd_rate()
    print(f"KRW/USD rate: {KRW_USD:.6f} (1 USD = {1/KRW_USD:.0f} KRW)\n")

    init_kline_table()
    df, first_df = build_tasks()
    today = datetime.now().strftime("%Y-%m-%d")

    # Group by token
    tokens = df.groupby("ticker")
    total_tokens = len(tokens)
    conn = get_conn()
    cur = conn.cursor()
    ph = "%s" if _use_pg() else "?"

    ok, errors, skipped = 0, 0, 0

    for idx, (ticker, group) in enumerate(tokens):
        group = group.sort_values("listing_date")
        first_row = group.iloc[0]
        first_exchange = first_row["first_exchange"]
        first_date = first_row["first_date"]

        # Pick best K-line source: prefer non-Perps, non-Korean spot exchange
        exclude = ["Binance Perps", "Upbit", "Bithumb"]
        preferred = group[~group["exchange"].isin(exclude)]
        if not preferred.empty:
            source_exchange = preferred.iloc[0]["exchange"]
        else:
            korean = group[group["exchange"].isin(["Upbit", "Bithumb"])]
            if not korean.empty:
                source_exchange = korean.iloc[0]["exchange"]
            else:
                source_exchange = first_exchange

        start = first_date.to_pydatetime().replace(tzinfo=None)
        print(f"[{idx+1:>2}/{total_tokens}] {ticker:12} src={source_exchange:20}", end="", flush=True)

        try:
            price_map, high_map = fetch_kline(ticker, source_exchange, start)
        except Exception as e:
            print(f"  FETCH ERROR: {e}")
            errors += 1
            continue

        if not price_map:
            print(f"  NO DATA")
            skipped += 1
            continue

        print(f"  {len(price_map)} candles", end="", flush=True)

        # First price
        first_price = find_closest_price(price_map, start, max_days=3)

        # For each listing event of this token
        event_count = 0
        for _, row in group.iterrows():
            ex = row["exchange"]
            l_date = row["listing_date"].to_pydatetime().replace(tzinfo=None)
            is_first = 1 if row["listing_date"] == first_date else 0
            days_later = (row["listing_date"] - first_date).days

            p0 = find_closest_price(price_map, l_date, max_days=3)
            if p0 is None:
                continue

            price_position = pct(first_price, p0) if first_price else None

            # Post-listing returns
            p1 = find_closest_price(price_map, l_date + timedelta(days=1), max_days=1)
            p7 = find_closest_price(price_map, l_date + timedelta(days=7), max_days=2)
            p14 = find_closest_price(price_map, l_date + timedelta(days=14), max_days=2)
            p30 = find_closest_price(price_map, l_date + timedelta(days=30), max_days=2)

            # Don't compute return if target date is in the future
            r1 = pct(p0, p1) if (l_date + timedelta(days=1)).strftime("%Y-%m-%d") <= today else None
            r7 = pct(p0, p7) if (l_date + timedelta(days=7)).strftime("%Y-%m-%d") <= today else None
            r14 = pct(p0, p14) if (l_date + timedelta(days=14)).strftime("%Y-%m-%d") <= today else None
            r30 = pct(p0, p30) if (l_date + timedelta(days=30)).strftime("%Y-%m-%d") <= today else None

            # Peak: highest high in 14 days after listing
            peak_14d = None
            if (l_date + timedelta(days=1)).strftime("%Y-%m-%d") <= today:
                highs = []
                for d in range(0, 15):
                    dt_key = (l_date + timedelta(days=d)).strftime("%Y-%m-%d")
                    if dt_key in high_map:
                        highs.append(high_map[dt_key])
                if highs and p0 and p0 > 0:
                    peak_14d = round((max(highs) - p0) / p0 * 100, 2)

            if _use_pg():
                cur.execute(f"""
                    INSERT INTO kline_returns
                    (ticker, exchange, listing_date, is_first, days_later, source_exchange,
                     p0, price_position_pct, return_1d_pct, return_7d_pct, return_14d_pct, return_30d_pct,
                     peak_14d_pct)
                    VALUES ({','.join(['%s']*13)})
                    ON CONFLICT (ticker, exchange) DO UPDATE SET
                     listing_date=EXCLUDED.listing_date, is_first=EXCLUDED.is_first,
                     days_later=EXCLUDED.days_later, source_exchange=EXCLUDED.source_exchange,
                     p0=EXCLUDED.p0, price_position_pct=EXCLUDED.price_position_pct,
                     return_1d_pct=EXCLUDED.return_1d_pct, return_7d_pct=EXCLUDED.return_7d_pct,
                     return_14d_pct=EXCLUDED.return_14d_pct, return_30d_pct=EXCLUDED.return_30d_pct,
                     peak_14d_pct=EXCLUDED.peak_14d_pct
                """, (ticker, ex, l_date.strftime("%Y-%m-%d"), is_first, days_later,
                      source_exchange, p0, price_position, r1, r7, r14, r30, peak_14d))
            else:
                cur.execute("""
                    INSERT OR REPLACE INTO kline_returns
                    (ticker, exchange, listing_date, is_first, days_later, source_exchange,
                     p0, price_position_pct, return_1d_pct, return_7d_pct, return_14d_pct, return_30d_pct,
                     peak_14d_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (ticker, ex, l_date.strftime("%Y-%m-%d"), is_first, days_later,
                      source_exchange, p0, price_position, r1, r7, r14, r30, peak_14d))
            event_count += 1

        conn.commit()
        ok += 1
        print(f"  -> {event_count} events saved")
        time.sleep(0.3)

    cur.close()
    conn.close()
    print(f"\nDone. Tokens: {ok} ok, {skipped} skipped, {errors} errors")
    print(f"Total records in kline_returns: check DB")


if __name__ == "__main__":
    run()
