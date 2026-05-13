import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from database import get_all, init_prices_table, insert_price

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
        d7 = (datetime.strptime(d0, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
        d14 = (datetime.strptime(d0, "%Y-%m-%d") + timedelta(days=14)).strftime("%Y-%m-%d")

        # Cap d7/d14 at today to avoid future-date errors
        today = datetime.now().strftime("%Y-%m-%d")
        d7 = min(d7, today)
        d14 = min(d14, today)

        price0, fdv0 = get_price_on_date(coin_id, d0)
        time.sleep(0.3)
        price7, _ = get_price_on_date(coin_id, d7)
        time.sleep(0.3)
        price14, _ = get_price_on_date(coin_id, d14)
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
        )

        status = f"p0={price0:.4f}" if price0 else "no price"
        chg7 = f"{pct_change(price0,price7):+.1f}%" if price0 and price7 else "N/A"
        chg14 = f"{pct_change(price0,price14):+.1f}%" if price0 and price14 else "N/A"
        print(f"  [{ok+1:>3}] {ticker:12} {exchange:20} {listing_date}  {status}  7d:{chg7}  14d:{chg14}")
        ok += 1

    print(f"\nDone. Success: {ok}, skipped (not on CG): {skipped}, errors: {errors}")


if __name__ == "__main__":
    run()
