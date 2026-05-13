import sqlite3
import pandas as pd

DB_PATH = "listings.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker       TEXT NOT NULL,
                exchange     TEXT NOT NULL,
                trading_pair TEXT,
                listing_type TEXT,
                listing_date TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique
            ON listings (ticker, exchange, trading_pair, listing_date)
        """)
        conn.commit()


def insert_listing(ticker, exchange, trading_pair, listing_type, listing_date):
    """Returns True if inserted, False if duplicate."""
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO listings (ticker, exchange, trading_pair, listing_type, listing_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (ticker, exchange, trading_pair, listing_type, listing_date),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_all(exchanges=None, date_from=None, date_to=None, listing_type=None):
    """Query listings with optional filters, returns DataFrame."""
    query = "SELECT ticker, exchange, trading_pair, listing_type, listing_date FROM listings WHERE 1=1"
    params = []

    if exchanges:
        placeholders = ",".join("?" * len(exchanges))
        query += f" AND exchange IN ({placeholders})"
        params.extend(exchanges)
    if date_from:
        query += " AND listing_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND listing_date <= ?"
        params.append(date_to)
    if listing_type:
        query += " AND listing_type = ?"
        params.append(listing_type)

    query += " ORDER BY listing_date DESC"

    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_stats():
    """Returns total count and per-exchange breakdown."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        by_exchange = conn.execute(
            "SELECT exchange, COUNT(*) as count FROM listings GROUP BY exchange ORDER BY count DESC"
        ).fetchall()
    return {"total": total, "by_exchange": dict(by_exchange)}


def init_prices_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                ticker          TEXT NOT NULL,
                exchange        TEXT NOT NULL,
                listing_date    TEXT NOT NULL,
                coingecko_id    TEXT,
                category        TEXT,
                price_listing   REAL,
                price_7d        REAL,
                price_14d       REAL,
                fdv_listing     REAL,
                change_7d_pct   REAL,
                change_14d_pct  REAL,
                PRIMARY KEY (ticker, exchange)
            )
        """)
        conn.commit()


def insert_price(ticker, exchange, listing_date, coingecko_id, category,
                 price_listing, price_7d, price_14d, fdv_listing,
                 change_7d_pct, change_14d_pct):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO prices
            (ticker, exchange, listing_date, coingecko_id, category,
             price_listing, price_7d, price_14d, fdv_listing,
             change_7d_pct, change_14d_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, exchange, listing_date, coingecko_id, category,
              price_listing, price_7d, price_14d, fdv_listing,
              change_7d_pct, change_14d_pct))
        conn.commit()


def get_prices():
    with get_conn() as conn:
        return pd.read_sql_query(
            """SELECT p.*, l.listing_type
               FROM prices p
               JOIN listings l ON p.ticker = l.ticker AND p.exchange = l.exchange
               ORDER BY p.listing_date DESC""",
            conn
        )
