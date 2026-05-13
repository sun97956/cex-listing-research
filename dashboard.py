import streamlit as st
import plotly.express as px
import pandas as pd
from database import get_all

st.set_page_config(page_title="CEX Listing Research", layout="wide")
st.title("CEX Listing Research Dashboard")
st.caption("Data source: listedon.org + Binance Futures API — 2026 New Listings (Binance, OKX, ByBit, Coinbase Exchange, Bithumb, Upbit, Binance Futures)")

# ── Load data ─────────────────────────────────────────────────────────────────
df_all = get_all()

if df_all.empty:
    st.warning("No data found. Run `python scraper.py` and `python binance_futures.py` first.")
    st.stop()

df_all["listing_date"] = pd.to_datetime(df_all["listing_date"])
df_all["month"] = df_all["listing_date"].dt.to_period("M").astype(str)

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")

exchanges = sorted(df_all["exchange"].unique().tolist())
selected_exchanges = st.sidebar.multiselect("Exchanges", exchanges, default=exchanges)

min_date = df_all["listing_date"].min().date()
max_date = df_all["listing_date"].max().date()
date_from, date_to = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

df = df_all[
    (df_all["exchange"].isin(selected_exchanges)) &
    (df_all["listing_date"].dt.date >= date_from) &
    (df_all["listing_date"].dt.date <= date_to)
].copy()

# ── 1. Overview metrics ───────────────────────────────────────────────────────
st.subheader("Overview")

this_month = pd.Timestamp.now().to_period("M").strftime("%Y-%m")
this_month_count = df[df["month"] == this_month].shape[0]
futures_count = df[df["exchange"] == "Binance Futures"].shape[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Listings", f"{len(df):,}")
col2.metric("Exchanges Covered", df["exchange"].nunique())
col3.metric("This Month", this_month_count)
col4.metric("Binance Futures", futures_count)

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
    monthly, x="month", y="count", color="exchange", markers=True,
    labels={"month": "Month", "count": "New Listings", "exchange": "Exchange"},
)
fig_trend.update_layout(xaxis_tickangle=-30, legend_title_text="Exchange", height=400)
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── 3. Exchange comparison bar chart ─────────────────────────────────────────
st.subheader("Total Listings by Exchange")

by_exchange = (
    df.groupby("exchange").size()
    .reset_index(name="count")
    .sort_values("count", ascending=True)
)

fig_bar = px.bar(
    by_exchange, x="count", y="exchange", orientation="h",
    labels={"count": "Total Listings", "exchange": "Exchange"},
    color="count", color_continuous_scale="Blues",
)
fig_bar.update_layout(coloraxis_showscale=False, height=350)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── 4. Binance Futures → Spot conversion ─────────────────────────────────────
st.subheader("Binance Futures → Spot Conversion")

futures_tickers = set(df_all[df_all["exchange"] == "Binance Futures"]["ticker"])
spot_df = df_all[df_all["exchange"] == "Binance"]

converted = []
for ticker in futures_tickers:
    fut_row = df_all[(df_all["exchange"] == "Binance Futures") & (df_all["ticker"] == ticker)].iloc[0]
    spot_rows = spot_df[spot_df["ticker"] == ticker]
    if not spot_rows.empty:
        spot_row = spot_rows.iloc[0]
        days = (spot_row["listing_date"] - fut_row["listing_date"]).days
        converted.append({
            "Ticker": ticker,
            "Futures Date": fut_row["listing_date"].strftime("%Y-%m-%d"),
            "Spot Date": spot_row["listing_date"].strftime("%Y-%m-%d"),
            "Days to Spot": days,
        })

total_futures = len(futures_tickers)
total_converted = len(converted)
conversion_rate = total_converted / total_futures * 100 if total_futures else 0
avg_days = round(sum(r["Days to Spot"] for r in converted) / total_converted, 1) if converted else 0

m1, m2, m3 = st.columns(3)
m1.metric("Futures Listings (2026)", total_futures)
m2.metric("Converted to Spot", f"{total_converted} ({conversion_rate:.0f}%)")
m3.metric("Avg Days Futures → Spot", avg_days)

if converted:
    conv_df = pd.DataFrame(converted).sort_values("Days to Spot")
    st.dataframe(conv_df, use_container_width=True, hide_index=True)

st.divider()

# ── 5. Multi-exchange token table ─────────────────────────────────────────────
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

# ── 6. Raw data table ─────────────────────────────────────────────────────────
st.subheader("Raw Data")

display_df = df[["listing_date", "ticker", "exchange", "trading_pair"]].copy()
display_df["listing_date"] = display_df["listing_date"].dt.strftime("%Y-%m-%d")
display_df = display_df.sort_values("listing_date", ascending=False).reset_index(drop=True)
display_df.columns = ["Date", "Ticker", "Exchange", "Trading Pair"]

st.dataframe(display_df, use_container_width=True, hide_index=True)

csv = display_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "listings.csv", "text/csv")
