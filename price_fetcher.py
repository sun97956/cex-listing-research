import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from database import get_all, init_prices_table, insert_price, update_price_1d_ohlc

API_KEY = "CG-BQqEungaTSnqUbQkUEzohnNT"
BASE_URL = "https://pro-api.coingecko.com/api/v3"
HEADERS = {"x-cg-pro-api-key": API_KEY}
PROXIES = {"http": None, "https": None}


def cg_get(path, params=None):
    resp = requests.get(
        f"{BASE_URL}{path}", headers=HEADERS, params=params,
        proxies=PROXIES, timeout=15
    )
    resp.raise_for_status()
    return resp.json()


def get_all_coins():
    """Returns dict: symbol (lower) → list of coingecko ids."""
    coins = cg_get("/coins/list")
    mapping = {}
    for c in coins:
        sym = c["symbol"].lower()
        mapping.setdefault(sym, []).append(c["id"])
    return mapping


def resolve_coin_id(ticker, candidates):
    """If multiple candidates, pick the one with highest market cap rank."""
    if len(candidates) == 1:
        return candidates[0]
    try:
        data = cg_get("/coins/markets", params={
            "vs_currency": "usd",
            "ids": ",".join(candidates),
            "order": "market_cap_desc",
            "per_page": 10,
        })
        if data:
            return data[0]["id"]
    except Exception:
        pass
    return candidates[0]


def get_price_on_date(coin_id, date_str):
    """Fetch price and FDV for a coin on a specific date (YYYY-MM-DD)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    cg_date = dt.strftime("%d-%m-%Y")
    try:
        data = cg_get(f"/coins/{coin_id}/history", params={"date": cg_date, "localization": "false"})
        market = data.get("market_data", {})
        price = market.get("current_price", {}).get("usd")
        fdv = market.get("fully_diluted_valuation", {}).get("usd")
        return price, fdv
    except Exception:
        return None, None


def get_category(coin_id):
    """Fetch primary category for a coin."""
    try:
        data = cg_get(f"/coins/{coin_id}", params={
            "localization": "false", "tickers": "false",
            "market_data": "false", "community_data": "false",
            "developer_data": "false",
        })
        cats = data.get("categories", [])
        return cats[0] if cats else None
    except Exception:
        return None


def get_ohlc_on_date(coin_id, date_str):
    """Fetch open and high price on listing date using OHLC endpoint.
    days=180 returns daily candles covering all 2026 listings (≤135 days old).
    """
    from datetime import timezone
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    target_ts_ms = dt.timestamp() * 1000
    try:
        candles = cg_get(f"/coins/{coin_id}/ohlc", params={
            "vs_currency": "usd",
            "days": 180,
        })
        if not candles:
            return None, None
        # Find candle whose timestamp is closest to midnight of listing date
        best, best_diff = None, float("inf")
        for c in candles:
            diff = abs(c[0] - target_ts_ms)
            if diff < best_diff:
                best_diff = diff
                best = c
        # Accept only if within 24 h (86 400 000 ms)
        if best and best_diff < 86_400_000:
            return best[1], best[2]   # open, high
        return None, None
    except Exception:
        return None, None


def pct_change(p1, p2):
    if p1 and p2 and p1 > 0:
        return round((p2 - p1) / p1 * 100, 2)
    return None


def run():
    init_prices_table()

    df = get_all()
    # One row per (ticker, exchange) — use the earliest listing date per combo
    df["listing_date"] = pd.to_datetime(df["listing_date"])
    tasks = (
        df.sort_values("listing_date")
        .drop_duplicates(subset=["ticker", "exchange"])
        [["ticker", "exchange", "listing_date"]]
    )
    tasks["listing_date"] = tasks["listing_date"].dt.strftime("%Y-%m-%d")

    print("Fetching CoinGecko coin list...")
    coin_map = get_all_coins()
    print(f"Loaded {sum(len(v) for v in coin_map.values())} coins.\n")

    ok, skipped, errors = 0, 0, 0

    for _, row in tasks.iterrows():
        ticker = row["ticker"]
        exchange = row["exchange"]
        listing_date = row["listing_date"]

        candidates = coin_map.get(ticker.lower(), [])
        if not candidates:
            print(f"  [skip] {ticker} — not found on CoinGecko")
            skipped += 1
            continue

        coin_id = resolve_coin_id(ticker, candidates)

        # Dates
        d0 = listing_date
        today = datetime.now().strftime("%Y-%m-%d")
        d7  = min((datetime.strptime(d0, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d"),  today)
        d14 = min((datetime.strptime(d0, "%Y-%m-%d") + timedelta(days=14)).strftime("%Y-%m-%d"), today)
        d30 = min((datetime.strptime(d0, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d"), today)

        price0, fdv0 = get_price_on_date(coin_id, d0)
        time.sleep(0.3)
        price7, _  = get_price_on_date(coin_id, d7)
        time.sleep(0.3)
        price14, _ = get_price_on_date(coin_id, d14)
        time.sleep(0.3)
        price30, _ = get_price_on_date(coin_id, d30)
        time.sleep(0.3)

        category = get_category(coin_id)
        time.sleep(0.3)

        insert_price(
            ticker=ticker,
            exchange=exchange,
            listing_date=listing_date,
            coingecko_id=coin_id,
            category=category,
            price_listing=price0,
            price_7d=price7,
            price_14d=price14,
            fdv_listing=fdv0,
            change_7d_pct=pct_change(price0, price7),
            change_14d_pct=pct_change(price0, price14),
            price_30d=price30,
            change_30d_pct=pct_change(price0, price30),
        )

        status = f"p0={price0:.4f}" if price0 else "no price"
        chg7  = f"{pct_change(price0,price7):+.1f}%"  if price0 and price7  else "N/A"
        chg14 = f"{pct_change(price0,price14):+.1f}%" if price0 and price14 else "N/A"
        chg30 = f"{pct_change(price0,price30):+.1f}%" if price0 and price30 else "N/A"
        print(f"  [{ok+1:>3}] {ticker:12} {exchange:20} {listing_date}  {status}  7d:{chg7}  14d:{chg14}  30d:{chg30}")
        ok += 1

    print(f"\nDone. Success: {ok}, skipped (not on CG): {skipped}, errors: {errors}")


def run_1d_ohlc():
    """Update-only pass: fetch 1d price and listing-day OHLC for records missing those fields."""
    import sqlite3
    init_prices_table()

    conn = sqlite3.connect("listings.db")
    tasks = pd.read_sql_query(
        """SELECT ticker, exchange, listing_date, coingecko_id
           FROM prices
           WHERE price_1d IS NULL AND coingecko_id IS NOT NULL
           ORDER BY listing_date""",
        conn,
    )
    conn.close()

    print(f"Records needing 1d/OHLC update: {len(tasks)}\n")
    if tasks.empty:
        print("Nothing to do.")
        return

    ok, errors = 0, 0
    today = datetime.now().strftime("%Y-%m-%d")

    for _, row in tasks.iterrows():
        ticker      = row["ticker"]
        exchange    = row["exchange"]
        listing_date = row["listing_date"]
        coin_id     = row["coingecko_id"]

        d1 = min(
            (datetime.strptime(listing_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
            today,
        )

        try:
            price1, _ = get_price_on_date(coin_id, d1)
            time.sleep(0.3)
            day_open, day_high = get_ohlc_on_date(coin_id, listing_date)
            time.sleep(0.4)

            # Fetch listing price from DB to calculate pct changes
            import sqlite3 as _sq
            c2 = _sq.connect("listings.db")
            p0_row = c2.execute(
                "SELECT price_listing FROM prices WHERE ticker=? AND exchange=?",
                (ticker, exchange),
            ).fetchone()
            c2.close()
            price0 = p0_row[0] if p0_row else None

            pump = None
            if day_open and day_high and day_open > 0:
                pump = round((day_high - day_open) / day_open * 100, 2)

            update_price_1d_ohlc(
                ticker=ticker,
                exchange=exchange,
                price_1d=price1,
                change_1d_pct=pct_change(price0, price1),
                listing_day_open=day_open,
                listing_day_high=day_high,
                listing_day_pump=pump,
            )

            chg1  = f"{pct_change(price0,price1):+.1f}%" if price0 and price1 else "N/A"
            pump_s = f"{pump:+.1f}%"                     if pump is not None  else "N/A"
            print(f"  [{ok+1:>3}] {ticker:12} {exchange:20} {listing_date}  1d:{chg1}  pump:{pump_s}")
            ok += 1

        except Exception as e:
            print(f"  [err] {ticker} {exchange}: {e}")
            errors += 1

    print(f"\nDone. Updated: {ok}, errors: {errors}")


if __name__ == "__main__":
    import sys
    if "--1d" in sys.argv:
        run_1d_ohlc()
    else:
        run()
