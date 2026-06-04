import os
import pandas as pd

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    try:
        import streamlit as st
        DATABASE_URL = st.secrets["DATABASE_URL"]
    except Exception:
        pass


def _use_pg():
    return DATABASE_URL.startswith("postgres")


def get_conn():
    if _use_pg():
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect("listings.db")


def _ph(n=1):
    """Return n placeholder(s): %s for PG, ? for SQLite."""
    p = "%s" if _use_pg() else "?"
    return ", ".join([p] * n)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    if _use_pg():
        cur.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                ticker       TEXT NOT NULL,
                exchange     TEXT NOT NULL,
                trading_pair TEXT,
                listing_type TEXT,
                listing_date TEXT NOT NULL,
                UNIQUE (ticker, exchange, trading_pair, listing_date)
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker       TEXT NOT NULL,
                exchange     TEXT NOT NULL,
                trading_pair TEXT,
                listing_type TEXT,
                listing_date TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique
            ON listings (ticker, exchange, trading_pair, listing_date)
        """)
    conn.commit()
    cur.close()
    conn.close()


def insert_listing(ticker, exchange, trading_pair, listing_type, listing_date):
    """Returns True if inserted, False if duplicate."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _use_pg():
            cur.execute(
                f"INSERT INTO listings (ticker, exchange, trading_pair, listing_type, listing_date) "
                f"VALUES ({_ph(5)}) ON CONFLICT DO NOTHING",
                (ticker, exchange, trading_pair, listing_type, listing_date),
            )
            inserted = cur.rowcount > 0
        else:
            cur.execute(
                f"INSERT INTO listings (ticker, exchange, trading_pair, listing_type, listing_date) "
                f"VALUES ({_ph(5)})",
                (ticker, exchange, trading_pair, listing_type, listing_date),
            )
            inserted = True
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def get_all(exchanges=None, date_from=None, date_to=None, listing_type=None):
    query = "SELECT ticker, exchange, trading_pair, listing_type, listing_date FROM listings WHERE 1=1"
    params = []
    ph = "%s" if _use_pg() else "?"

    if exchanges:
        placeholders = ",".join([ph] * len(exchanges))
        query += f" AND exchange IN ({placeholders})"
        params.extend(exchanges)
    if date_from:
        query += f" AND listing_date >= {ph}"
        params.append(date_from)
    if date_to:
        query += f" AND listing_date <= {ph}"
        params.append(date_to)
    if listing_type:
        query += f" AND listing_type = {ph}"
        params.append(listing_type)

    query += " ORDER BY listing_date DESC"

    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=tuple(params) if params else None)
    conn.close()
    return df


def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM listings")
    total = cur.fetchone()[0]
    cur.execute("SELECT exchange, COUNT(*) as count FROM listings GROUP BY exchange ORDER BY count DESC")
    by_exchange = dict(cur.fetchall())
    cur.close()
    conn.close()
    return {"total": total, "by_exchange": by_exchange}


def get_prices():
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            """SELECT p.*, l.listing_type
               FROM prices p
               JOIN (
                   SELECT ticker, exchange, MAX(listing_type) AS listing_type
                   FROM listings
                   GROUP BY ticker, exchange
               ) l ON p.ticker = l.ticker AND p.exchange = l.exchange
               ORDER BY p.listing_date DESC""",
            conn
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_kline_returns():
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM kline_returns ORDER BY listing_date DESC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df
