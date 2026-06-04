"""
Sync local SQLite data to Neon PostgreSQL.
Usage: python sync_to_neon.py
"""
import sqlite3
import psycopg2

NEON_URL = "postgresql://neondb_owner:npg_fClm2bQSBV6t@ep-late-band-apsuisd7-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require"
LOCAL_DB = "listings.db"


def sync():
    local = sqlite3.connect(LOCAL_DB)
    remote = psycopg2.connect(NEON_URL)
    cur = remote.cursor()

    # ── 1. Sync listings ────────────────────────────────────────────────────
    print("Syncing listings...")
    cur.execute("DELETE FROM listings")
    rows = local.execute("SELECT ticker, exchange, listing_date, trading_pair FROM listings").fetchall()
    for r in rows:
        cur.execute(
            "INSERT INTO listings (ticker, exchange, listing_date, trading_pair) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            r
        )
    print(f"  {len(rows)} rows")

    # ── 2. Sync kline_returns ───────────────────────────────────────────────
    print("Syncing kline_returns...")
    cur.execute("DELETE FROM kline_returns")
    rows = local.execute("SELECT ticker, exchange, listing_date, is_first, days_later, source_exchange, p0, price_position_pct, return_1d_pct, return_7d_pct, return_14d_pct, return_30d_pct, peak_14d_pct FROM kline_returns").fetchall()
    for r in rows:
        cur.execute(
            "INSERT INTO kline_returns (ticker, exchange, listing_date, is_first, days_later, source_exchange, p0, price_position_pct, return_1d_pct, return_7d_pct, return_14d_pct, return_30d_pct, peak_14d_pct) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            r
        )
    print(f"  {len(rows)} rows")

    # ── 3. Sync bf_returns ──────────────────────────────────────────────────
    print("Syncing bf_returns...")
    cur.execute("DELETE FROM bf_returns")
    rows = local.execute("SELECT ticker, bf_date, converted, gap_days, p0, r1d, r7d, r14d, r30d, peak_14d_pct, pre_spot_pct, fdv_at_listing FROM bf_returns").fetchall()
    for r in rows:
        cur.execute(
            "INSERT INTO bf_returns (ticker, bf_date, converted, gap_days, p0, r1d, r7d, r14d, r30d, peak_14d_pct, pre_spot_pct, fdv_at_listing) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            r
        )
    print(f"  {len(rows)} rows")

    remote.commit()
    cur.close()
    remote.close()
    local.close()
    print("\nDone! Neon is now in sync with local DB.")


if __name__ == "__main__":
    sync()
