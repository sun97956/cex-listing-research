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
