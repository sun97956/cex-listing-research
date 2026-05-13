import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database import get_all, get_prices

st.set_page_config(page_title="CEX Listing Research", layout="wide")
st.title("CEX Listing Research Dashboard")
st.caption("Data source: listedon.org + Binance Futures API + CoinGecko — 2026 New Listings")

# ── Load data ─────────────────────────────────────────────────────────────────
df_all = get_all()
df_prices = get_prices()

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
    "Date range", value=(min_date, max_date),
    min_value=min_date, max_value=max_date,
)

df = df_all[
    (df_all["exchange"].isin(selected_exchanges)) &
    (df_all["listing_date"].dt.date >= date_from) &
    (df_all["listing_date"].dt.date <= date_to)
].copy()

df_p = df_prices[df_prices["exchange"].isin(selected_exchanges)].copy() if not df_prices.empty else pd.DataFrame()

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

# ── 2. Monthly trend ──────────────────────────────────────────────────────────
st.subheader("Monthly Listings by Exchange")

monthly = (
    df.groupby(["month", "exchange"]).size()
    .reset_index(name="count").sort_values("month")
)
fig_trend = px.line(
    monthly, x="month", y="count", color="exchange", markers=True,
    labels={"month": "Month", "count": "New Listings", "exchange": "Exchange"},
)
fig_trend.update_layout(xaxis_tickangle=-30, legend_title_text="Exchange", height=400)
st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── 3. Exchange comparison ────────────────────────────────────────────────────
st.subheader("Total Listings by Exchange")

by_exchange = (
    df.groupby("exchange").size()
    .reset_index(name="count").sort_values("count", ascending=True)
)
fig_bar = px.bar(
    by_exchange, x="count", y="exchange", orientation="h",
    labels={"count": "Total Listings", "exchange": "Exchange"},
    color="count", color_continuous_scale="Blues",
)
fig_bar.update_layout(coloraxis_showscale=False, height=350)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ── 4. Price performance ──────────────────────────────────────────────────────
st.subheader("Price Performance After Listing")

if not df_p.empty and "change_14d_pct" in df_p.columns:
    df_p_clean = df_p.dropna(subset=["change_14d_pct", "change_7d_pct"])

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Average 14-day Return by Exchange**")
        perf = (
            df_p_clean.groupby("exchange")
            .agg(
                mean_14d=("change_14d_pct", "mean"),
                median_14d=("change_14d_pct", "median"),
                count=("change_14d_pct", "count"),
            )
            .round(1).reset_index()
            .sort_values("median_14d", ascending=True)
        )
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Bar(
            y=perf["exchange"], x=perf["mean_14d"],
            name="Mean", orientation="h", marker_color="#4C78A8",
        ))
        fig_perf.add_trace(go.Bar(
            y=perf["exchange"], x=perf["median_14d"],
            name="Median", orientation="h", marker_color="#72B7B2",
        ))
        fig_perf.update_layout(
            barmode="group", height=320,
            xaxis_title="14d Return (%)", yaxis_title="",
            legend_title_text="", xaxis=dict(zeroline=True, zerolinewidth=1, zerolinecolor="gray"),
        )
        st.plotly_chart(fig_perf, use_container_width=True)

    with col_b:
        st.markdown("**7-day vs 14-day Return (Median)**")
        perf7 = (
            df_p_clean.groupby("exchange")
            .agg(median_7d=("change_7d_pct", "median"), median_14d=("change_14d_pct", "median"))
            .round(1).reset_index()
        )
        fig_7v14 = go.Figure()
        fig_7v14.add_trace(go.Bar(
            y=perf7["exchange"], x=perf7["median_7d"],
            name="7d", orientation="h", marker_color="#F58518",
        ))
        fig_7v14.add_trace(go.Bar(
            y=perf7["exchange"], x=perf7["median_14d"],
            name="14d", orientation="h", marker_color="#E45756",
        ))
        fig_7v14.update_layout(
            barmode="group", height=320,
            xaxis_title="Return (%)", yaxis_title="",
            legend_title_text="", xaxis=dict(zeroline=True, zerolinewidth=1, zerolinecolor="gray"),
        )
        st.plotly_chart(fig_7v14, use_container_width=True)

    # Token-level table
    with st.expander("View all token price performance"):
        show_cols = ["ticker", "exchange", "listing_date", "category",
                     "price_listing", "change_7d_pct", "change_14d_pct"]
        show = df_p_clean[show_cols].copy()
        show.columns = ["Ticker", "Exchange", "Listing Date", "Category",
                        "Price (USD)", "7d %", "14d %"]
        st.dataframe(show.sort_values("14d %", ascending=False), use_container_width=True, hide_index=True)
else:
    st.info("Run `python price_fetcher.py` to load price data.")

st.divider()

# ── 5. Category distribution ──────────────────────────────────────────────────
st.subheader("Category Distribution by Exchange")

if not df_p.empty and "category" in df_p.columns:
    df_cat = df_p.dropna(subset=["category"]).copy()
    # Group minor categories
    top_cats = df_cat["category"].value_counts().head(7).index.tolist()
    df_cat["cat_group"] = df_cat["category"].apply(lambda x: x if x in top_cats else "Other")

    cat_pivot = (
        df_cat.groupby(["exchange", "cat_group"]).size()
        .reset_index(name="count")
    )
    fig_cat = px.bar(
        cat_pivot, x="exchange", y="count", color="cat_group",
        labels={"count": "# Listings", "exchange": "Exchange", "cat_group": "Category"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_cat.update_layout(height=380, legend_title_text="Category", xaxis_title="")
    st.plotly_chart(fig_cat, use_container_width=True)

st.divider()

# ── 6. Binance Futures → Spot conversion ─────────────────────────────────────
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

# ── 7. Multi-exchange token table ─────────────────────────────────────────────
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
        "ticker": "Ticker", "exchange_count": "# Exchanges",
        "exchanges": "Listed On", "first_listing": "First Listing",
    }),
    use_container_width=True, hide_index=True,
)

st.divider()

# ── 8. Raw data ───────────────────────────────────────────────────────────────
st.subheader("Raw Data")

display_df = df[["listing_date", "ticker", "exchange", "trading_pair"]].copy()
display_df["listing_date"] = display_df["listing_date"].dt.strftime("%Y-%m-%d")
display_df = display_df.sort_values("listing_date", ascending=False).reset_index(drop=True)
display_df.columns = ["Date", "Ticker", "Exchange", "Trading Pair"]

st.dataframe(display_df, use_container_width=True, hide_index=True)
csv = display_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "listings.csv", "text/csv")
