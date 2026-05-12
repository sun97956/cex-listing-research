import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database import get_all, get_stats

st.set_page_config(page_title="CEX Listing Research", layout="wide")
st.title("CEX Listing Research Dashboard")
st.caption("Data source: listedon.org — 2026 New Listings only (Binance, OKX, Bybit, Coinbase, Gate.io, Bitget, KuCoin, MEXC, Kraken, Upbit)")

# ── Load data ────────────────────────────────────────────────────────────────
df_all = get_all()

if df_all.empty:
    st.warning("No data found. Run `python scraper.py` first.")
    st.stop()

df_all["listing_date"] = pd.to_datetime(df_all["listing_date"])
df_all["month"] = df_all["listing_date"].dt.to_period("M").astype(str)

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")

exchanges = sorted(df_all["exchange"].unique().tolist())
selected_exchanges = st.sidebar.multiselect(
    "Exchanges", exchanges, default=exchanges
)

min_date = df_all["listing_date"].min().date()
max_date = df_all["listing_date"].max().date()
date_from, date_to = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Apply filters
df = df_all[
    (df_all["exchange"].isin(selected_exchanges)) &
    (df_all["listing_date"].dt.date >= date_from) &
    (df_all["listing_date"].dt.date <= date_to)
].copy()

# ── 1. Overview metrics ───────────────────────────────────────────────────────
st.subheader("Overview")

this_month = pd.Timestamp.now().to_period("M").strftime("%Y-%m")
this_month_count = df[df["month"] == this_month].shape[0]

col1, col2, col3 = st.columns(3)
col1.metric("Total Listings", f"{len(df):,}")
col2.metric("Exchanges Covered", df["exchange"].nunique())
col3.metric("This Month", this_month_count)

st.divider()

# ── 2. Monthly trend line chart ───────────────────────────────────────────────
st.subheader("Monthly Listings by Exchange")

monthly = (
    df.groupby(["month", "exchange"])
    .size()
    .reset_index(name="count")
    .sort_values("month")
)

fig_trend = px.line(
    monthly,
    x="month",
    y="count",
    color="exchange",
    markers=True,
    labels={"month": "Month", "count": "New Listings", "exchange": "Exchange"},
)
fig_trend.update_layout(xaxis_tickangle=-30, legend_title_text="Exchange", height=400)
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── 3. Exchange comparison bar chart ─────────────────────────────────────────
st.subheader("Total Listings by Exchange")

by_exchange = (
    df.groupby("exchange")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=True)
)

fig_bar = px.bar(
    by_exchange,
    x="count",
    y="exchange",
    orientation="h",
    labels={"count": "Total Listings", "exchange": "Exchange"},
    color="count",
    color_continuous_scale="Blues",
)
fig_bar.update_layout(coloraxis_showscale=False, height=350)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── 4. Multi-exchange token table ─────────────────────────────────────────────
st.subheader("Tokens Listed on Multiple Exchanges")

overlap = (
    df.groupby("ticker")
    .agg(
        exchange_count=("exchange", "nunique"),
        exchanges=("exchange", lambda x: ", ".join(sorted(x.unique()))),
        first_listing=("listing_date", "min"),
    )
    .reset_index()
    .query("exchange_count >= 2")
    .sort_values(["exchange_count", "first_listing"], ascending=[False, True])
    .head(50)
)
overlap["first_listing"] = overlap["first_listing"].dt.strftime("%Y-%m-%d")

st.dataframe(
    overlap.rename(columns={
        "ticker": "Ticker",
        "exchange_count": "# Exchanges",
        "exchanges": "Listed On",
        "first_listing": "First Listing",
    }),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── 5. Raw data table ─────────────────────────────────────────────────────────
st.subheader("Raw Data")

display_df = df[["listing_date", "ticker", "exchange", "trading_pair"]].copy()
display_df["listing_date"] = display_df["listing_date"].dt.strftime("%Y-%m-%d")
display_df = display_df.sort_values("listing_date", ascending=False).reset_index(drop=True)
display_df.columns = ["Date", "Ticker", "Exchange", "Trading Pair"]

st.dataframe(display_df, use_container_width=True, hide_index=True)

csv = display_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "listings.csv", "text/csv")
