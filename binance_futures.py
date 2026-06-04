import requests
from datetime import datetime, timezone
from database import init_db, insert_listing

API_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
START_2026 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
END_2026_NOW = int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def fetch_futures():
    resp = requests.get(API_URL, timeout=15, proxies={"http": None, "https": None})
    resp.raise_for_status()
    return resp.json()["symbols"]


def run():
    init_db()
    symbols = fetch_futures()

    new_count = 0
    skip_count = 0

    for s in symbols:
        if s["contractType"] != "PERPETUAL":
            continue
        if s["status"] != "TRADING":
            continue

        onboard_ms = s["onboardDate"]
        if onboard_ms < START_2026 or onboard_ms > END_2026_NOW:
            continue

        ticker = s["baseAsset"]
        trading_pair = s["symbol"]
        listing_date = datetime.fromtimestamp(onboard_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

        inserted = insert_listing(
            ticker=ticker,
            exchange="Binance Futures",
            trading_pair=trading_pair,
            listing_type="Futures",
            listing_date=listing_date,
        )
        if inserted:
            new_count += 1
            print(f"  + {ticker:12} {trading_pair:20} {listing_date}")
        else:
            skip_count += 1

    print(f"\nDone. Inserted: {new_count}, skipped (duplicate): {skip_count}")


if __name__ == "__main__":
    run()
