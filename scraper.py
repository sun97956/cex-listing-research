import random
import time
import requests
from bs4 import BeautifulSoup
from database import init_db, insert_listing

BASE_URL = "https://listedon.org/en/search"

TARGET_EXCHANGES = {
    "Binance", "OKX", "ByBit", "Coinbase Exchange",
    "Bithumb", "Upbit"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://listedon.org/",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_page(page_num):
    params = {"page": page_num, "exchange": "", "text": "", "sort": "date", "order": "1"}
    retries = [5, 10, 20]
    for attempt, wait in enumerate(retries, 1):
        try:
            resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
            if resp.status_code in (429, 403):
                print(f"  [!] HTTP {resp.status_code} — stopping.")
                return None
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"  [retry {attempt}] {e} — waiting {wait}s")
            time.sleep(wait)
    print(f"  [!] Page {page_num} failed after {len(retries)} retries.")
    return None


def parse_page(html):
    """Parse one page, return list of dicts. Only 'Listed on' type kept."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    rows = soup.select("tr")
    if not rows:
        rows = soup.select("div.listing-entry, div.listing-row")

    for row in rows:
        # --- listing type: keep only "Listed on", skip "trading pair" ---
        type_el = (
            row.select_one("td.type") or
            row.select_one(".type") or
            row.select_one("span.type")
        )
        if not type_el:
            continue
        listing_type = type_el.get_text(separator=" ", strip=True)
        if "trading pair" in listing_type.lower():
            continue
        if "listed" not in listing_type.lower():
            continue

        # --- date: use separator=" " to avoid "May 9, 202605:41" concat ---
        date_el = (
            row.select_one("td.date") or
            row.select_one(".date") or
            row.select_one("time")
        )
        if not date_el:
            continue
        raw_date = date_el.get_text(separator=" ", strip=True)

        # --- ticker ---
        ticker_el = (
            row.select_one("td.ticker a") or
            row.select_one(".ticker a") or
            row.select_one("a[href*='/en/ticker/']")
        )
        if not ticker_el:
            continue
        ticker = ticker_el.get_text(strip=True).lstrip("$")

        # --- exchange ---
        exchange_el = (
            row.select_one("td.exchange a") or
            row.select_one(".exchange a") or
            row.select_one("a[href*='/en/exchange/']")
        )
        if not exchange_el:
            continue
        exchange = exchange_el.get_text(strip=True)

        # --- trading pair ---
        pair_el = (
            row.select_one("td.pairs a") or
            row.select_one(".pairs a")
        )
        trading_pair = pair_el.get_text(strip=True) if pair_el else ""

        results.append({
            "raw_date": raw_date,
            "ticker": ticker,
            "exchange": exchange,
            "trading_pair": trading_pair,
        })

    return results


def normalize_date(raw_date):
    """Convert 'May 12, 2026 02:52' or 'May 9 , 2026 05:41' → '2026-05-12'"""
    import re
    from datetime import datetime
    # Collapse multiple spaces, remove space-before-comma artifacts
    cleaned = re.sub(r"\s+", " ", raw_date.strip())
    cleaned = re.sub(r"\s*,\s*", ", ", cleaned)  # normalise comma spacing
    # Take only month/day/year, drop time
    parts = cleaned.split()
    date_only = " ".join(parts[:3]).strip(", ")
    for fmt in ("%B %d, %Y", "%B %d %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_only, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw_date.strip()


def scrape_all(test_mode=False):
    init_db()
    page = 1
    total_new = 0
    total_skip = 0
    consecutive_dupes = 0
    DUPE_STOP = 10

    print(f"{'[TEST MODE] ' if test_mode else ''}Starting scrape...\n")

    while True:
        if test_mode and page > 3:
            print("\n[TEST] Reached 3-page limit — stopping.")
            break

        print(f"Page {page}...", end=" ", flush=True)
        html = fetch_page(page)
        if html is None:
            break

        records = parse_page(html)

        if not records:
            print("no records parsed.")
            # Print snippet to help debug
            print("  HTML snippet:", html[500:1000])
            break

        page_new = 0
        page_skip = 0
        stop = False

        for rec in records:
            date_str = normalize_date(rec["raw_date"])

            # Stop condition 1: hit pre-2026 data
            if date_str[:4] < "2026":
                print(f"\n  [stop] Hit pre-2026 date: {date_str} (raw: {rec['raw_date']})")
                stop = True
                break

            # Filter to target exchanges only
            if rec["exchange"] not in TARGET_EXCHANGES:
                continue

            inserted = insert_listing(
                ticker=rec["ticker"],
                exchange=rec["exchange"],
                trading_pair=rec["trading_pair"],
                listing_type="New listing",
                listing_date=date_str,
            )

            if inserted:
                page_new += 1
                consecutive_dupes = 0
            else:
                page_skip += 1
                consecutive_dupes += 1

            # Stop condition 2: too many consecutive dupes (incremental update)
            if consecutive_dupes >= DUPE_STOP:
                print(f"\n  [stop] {DUPE_STOP} consecutive duplicates — already up to date.")
                stop = True
                break

        total_new += page_new
        total_skip += page_skip
        print(f"new={page_new}, skip={page_skip} | total new={total_new}")

        if stop:
            break

        page += 1
        time.sleep(random.uniform(1, 3))

    print(f"\nDone. Total inserted: {total_new}, skipped: {total_skip}")


if __name__ == "__main__":
    import sys
    test = "--test" in sys.argv
    scrape_all(test_mode=test)
