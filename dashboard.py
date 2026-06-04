import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database import get_all, get_prices, get_kline_returns

st.set_page_config(page_title="CEX Listing Research", layout="wide")
st.title("CEX Listing Research Dashboard")
st.caption("Data source: listedon.org + Binance Perps API + CoinGecko — 2026 New Listings")

# ── Load data ─────────────────────────────────────────────────────────────────
df_all = get_all()
df_prices = get_prices()
df_kline = get_kline_returns()

if df_all.empty:
    st.warning("No data found. Run `python scraper.py` and `python binance_futures.py` first.")
    st.stop()

df_all["listing_date"] = pd.to_datetime(df_all["listing_date"])
df_all = df_all.drop_duplicates(subset=["ticker", "exchange", "listing_date"])
# Exclude XAUT (commodity token) from Binance Perps analysis
df_all = df_all[~((df_all["exchange"] == "Binance Perps") & (df_all["ticker"] == "XAUT"))]
df_all["month"] = df_all["listing_date"].dt.to_period("M").astype(str)

EXCHANGE_COLORS = {
    "Binance": "#F0B90B",
    "Binance Perps": "#F7D36B",
    "OKX": "#000000",
    "ByBit": "#FF6600",
    "Coinbase Exchange": "#5B9BD5",
    "Upbit": "#1A3A6B",
    "Bithumb": "#E74C3C",
}

CHART_LAYOUT = dict(
    font=dict(size=15, color="black"),
    xaxis=dict(tickfont=dict(size=14, color="black"), title_font=dict(size=15, color="black")),
    yaxis=dict(tickfont=dict(size=14, color="black"), title_font=dict(size=15, color="black")),
    legend=dict(font=dict(size=13, color="black")),
    width=900,
)

# ── Sidebar: Data Update ──────────────────────────────────────────────────────
st.sidebar.header("Data Update")
if st.sidebar.button("Refresh Dashboard"):
    st.cache_data.clear()
    st.rerun()

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

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: LISTING LANDSCAPE
# ══════════════════════════════════════════════════════════════════════════════
st.header("1 · Listing Landscape")

# ── Metrics ──────────────────────────────────────────────────────────────────
this_month = pd.Timestamp.now().to_period("M").strftime("%Y-%m")
this_month_count = df[df["month"] == this_month].shape[0]
perps_count = df[df["exchange"] == "Binance Perps"].shape[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Listings", f"{len(df):,}")
col2.metric("Exchanges Covered", df["exchange"].nunique())
col3.metric("This Month", this_month_count)
col4.metric("Binance Perps", perps_count)

# ── Monthly Listings ─────────────────────────────────────────────────────────
st.subheader("Monthly Listings by Exchange")
monthly = (
    df.groupby(["month", "exchange"]).size()
    .reset_index(name="count").sort_values("month")
)
fig_trend = px.bar(
    monthly, x="month", y="count", color="exchange",
    labels={"month": "Month", "count": "New Listings", "exchange": "Exchange"},
    color_discrete_map=EXCHANGE_COLORS,
)
fig_trend.update_layout(**CHART_LAYOUT, barmode="stack", xaxis_tickangle=-30, legend_title_text="Exchange", height=420)
st.plotly_chart(fig_trend, use_container_width=True)

# ── Total Listings ───────────────────────────────────────────────────────────
st.subheader("Total Listings by Exchange")
by_exchange = (
    df.groupby("exchange").size()
    .reset_index(name="count").sort_values("count", ascending=True)
)
fig_bar = px.bar(
    by_exchange, x="count", y="exchange", orientation="h",
    labels={"count": "Total Listings", "exchange": "Exchange"},
    color="exchange", color_discrete_map=EXCHANGE_COLORS,
)
fig_bar.update_layout(**CHART_LAYOUT, showlegend=False, height=400)
st.plotly_chart(fig_bar, use_container_width=True)

# ── Category Distribution ────────────────────────────────────────────────────
if not df_p.empty and "category" in df_p.columns:
    st.subheader("Category Distribution by Exchange")
    df_cat = df_p.dropna(subset=["category"]).copy()
    top_cats = df_cat["category"].value_counts().head(7).index.tolist()
    df_cat["cat_group"] = df_cat["category"].apply(lambda x: x if x in top_cats else "Other")
    cat_pivot = df_cat.groupby(["exchange", "cat_group"]).size().reset_index(name="count")
    fig_cat = px.bar(
        cat_pivot, x="exchange", y="count", color="cat_group",
        labels={"count": "# Listings", "exchange": "Exchange", "cat_group": "Category"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_cat.update_layout(**CHART_LAYOUT, height=420, legend_title_text="Category", xaxis_title="")
    st.plotly_chart(fig_cat, use_container_width=True)

# ── Tokens on Multiple Exchanges ────────────────────────────────────────────
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

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: PRICE IMPACT
# ══════════════════════════════════════════════════════════════════════════════
st.header("2 · Price Impact After Listing")

df_k = df_kline[df_kline["exchange"].isin(selected_exchanges)].copy() if not df_kline.empty else pd.DataFrame()

if not df_k.empty:
    perf = df_k.groupby("exchange").agg(
        n=("return_7d_pct", "count"),
        mean_7d=("return_7d_pct", "mean"),
        mean_14d=("return_14d_pct", "mean"),
        mean_30d=("return_30d_pct", "mean"),
    ).round(1).reset_index().sort_values("mean_30d", ascending=True)

    # ── Mean Return ────────────────────────────────────────────────────────
    st.markdown("**Mean Return by Exchange (7d / 14d / 30d)**")
    fig_perf = go.Figure()
    period_colors = {"7d": "#F58518", "14d": "#E45756", "30d": "#72B7B2"}
    fig_perf.add_trace(go.Bar(y=perf["exchange"], x=perf["mean_7d"],  name="7d",  orientation="h", marker_color=period_colors["7d"]))
    fig_perf.add_trace(go.Bar(y=perf["exchange"], x=perf["mean_14d"], name="14d", orientation="h", marker_color=period_colors["14d"]))
    fig_perf.add_trace(go.Bar(y=perf["exchange"], x=perf["mean_30d"], name="30d", orientation="h", marker_color=period_colors["30d"]))
    fig_perf.update_layout(
        **CHART_LAYOUT, barmode="group", height=420,
        xaxis_title="Mean Return (%)", yaxis_title="",
        legend_title_text="",
    )
    fig_perf.update_xaxes(zeroline=True, zerolinewidth=1, zerolinecolor="gray")
    st.plotly_chart(fig_perf, use_container_width=True)

    # ── Price Position ──────────────────────────────────────────────────────
    df_followers = df_k[df_k["is_first"] == 0]
    if not df_followers.empty:
        st.markdown("**Price Position at Listing** — price vs first lister")
        pos = df_followers.groupby("exchange").agg(
            n=("days_later", "count"),
            mean_position=("price_position_pct", "mean"),
            price_n=("price_position_pct", "count"),
            avg_days_later=("days_later", "mean"),
        ).round(1).reset_index().sort_values("mean_position", ascending=True)
        pos.columns = ["Exchange", "Sample", "Mean Position %", "Price N", "Avg Days Later"]
        st.dataframe(pos, use_container_width=True, hide_index=True)

    # ── Peak Return + Peak Data ──────────────────────────────────────────────
    if "peak_14d_pct" in df_k.columns and df_k["peak_14d_pct"].notna().any():
        peak_agg = df_k.groupby("exchange").agg(
            n=("peak_14d_pct", "count"),
            mean_peak=("peak_14d_pct", "mean"),
            median_peak=("peak_14d_pct", "median"),
        ).round(1).reset_index().sort_values("mean_peak", ascending=True)

        st.markdown("**Peak Return by Exchange (14d High)**")
        fig_peak = go.Figure()
        fig_peak.add_trace(go.Bar(
            y=peak_agg["exchange"], x=peak_agg["mean_peak"],
            name="Mean", orientation="h", marker_color="#E45756",
        ))
        fig_peak.add_trace(go.Bar(
            y=peak_agg["exchange"], x=peak_agg["median_peak"],
            name="Median", orientation="h", marker_color="#72B7B2",
        ))
        fig_peak.update_layout(
            **CHART_LAYOUT, barmode="group", height=420,
            xaxis_title="Peak Return (%)", yaxis_title="",
            legend_title_text="",
        )
        fig_peak.update_xaxes(zeroline=True, zerolinewidth=1, zerolinecolor="gray")
        st.plotly_chart(fig_peak, use_container_width=True)

        st.markdown("**Peak Return Data (14d High)**")
        peak_tbl = peak_agg.copy()
        peak_tbl.columns = ["Exchange", "N", "Mean Peak %", "Median Peak %"]
        peak_tbl = peak_tbl.sort_values("Mean Peak %", ascending=False)
        st.dataframe(peak_tbl, use_container_width=True, hide_index=True)

    # ── Token detail table ───────────────────────────────────────────────────
    with st.expander("View all token price performance"):
        show_cols = ["ticker", "exchange", "listing_date", "source_exchange", "p0",
                     "is_first", "days_later", "price_position_pct",
                     "return_1d_pct", "return_7d_pct", "return_14d_pct", "return_30d_pct",
                     "peak_14d_pct"]
        col_names = ["Ticker", "Exchange", "Listing Date", "Price Source", "Price (USD)",
                     "First?", "Days Later", "Price Position %",
                     "1d %", "7d %", "14d %", "30d %", "Peak 14d %"]
        avail_cols = [c for c in show_cols if c in df_k.columns]
        avail_names = [col_names[show_cols.index(c)] for c in avail_cols]
        show = df_k[avail_cols].copy()
        show.columns = avail_names
        show["First?"] = show["First?"].map({1: "Yes", 0: "No"})
        st.dataframe(show.sort_values("30d %", ascending=True), use_container_width=True, hide_index=True)
else:
    st.info("Run `python kline_fetcher.py` to load exchange K-line price data.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: BINANCE PERPS ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
st.header("3 · Binance Perps Analysis")

# ── BF data ──────────────────────────────────────────────────────────────────
df_bf_ret = pd.DataFrame()
try:
    from database import get_conn as _get_conn
    _conn = _get_conn()
    df_bf_ret = pd.read_sql_query("SELECT * FROM bf_returns WHERE ticker != 'XAUT' ORDER BY bf_date", _conn)
    _conn.close()
except Exception:
    pass

futures_tickers = set(df_all[(df_all["exchange"] == "Binance Perps") & (df_all["ticker"] != "XAUT")]["ticker"])
spot_df = df_all[df_all["exchange"] == "Binance"]

converted = []
for ticker in futures_tickers:
    fut_row = df_all[(df_all["exchange"] == "Binance Perps") & (df_all["ticker"] == ticker)].iloc[0]
    spot_rows = spot_df[spot_df["ticker"] == ticker]
    if not spot_rows.empty:
        spot_row = spot_rows.iloc[0]
        days = (spot_row["listing_date"] - fut_row["listing_date"]).days
        converted.append({
            "Ticker": ticker,
            "Perps Date": fut_row["listing_date"].strftime("%Y-%m-%d"),
            "Spot Date": spot_row["listing_date"].strftime("%Y-%m-%d"),
            "Days to Spot": days,
        })

total_futures = len(futures_tickers)
total_converted = len(converted)
conversion_rate = total_converted / total_futures * 100 if total_futures else 0
avg_days = round(sum(r["Days to Spot"] for r in converted) / total_converted, 1) if converted else 0

# ── Perps → Spot metrics ────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Perps Listings (2026)", total_futures)
m2.metric("Converted to Spot", f"{total_converted} ({conversion_rate:.0f}%)")
m3.metric("Avg Days Perps → Spot", avg_days)
if not df_bf_ret.empty:
    fdv_conv = df_bf_ret[df_bf_ret["converted"] == 1]["fdv_at_listing"].dropna()
    fdv_only = df_bf_ret[df_bf_ret["converted"] == 0]["fdv_at_listing"].dropna()
    m4.metric("Avg FDV (Converted)", f"${fdv_conv.mean() / 1e6:,.0f}M" if not fdv_conv.empty else "N/A")

# ── Post-Listing Return + Conversion Details ─────────────────────────────────
if not df_bf_ret.empty:
    df_bf_conv = df_bf_ret[df_bf_ret["converted"] == 1]
    df_bf_only = df_bf_ret[df_bf_ret["converted"] == 0]

    st.markdown("**Post-Listing Mean Return** (Perps K-line)")
    chart_data = []
    for label, sub in [("Perp to Spot", df_bf_conv), ("Perp Only", df_bf_only)]:
        for period, col in [("1d", "r1d"), ("7d", "r7d"), ("14d", "r14d")]:
            vals = sub[col].dropna()
            if not vals.empty:
                chart_data.append({"Group": label, "Period": period, "Mean Return %": round(vals.mean(), 1)})
    if chart_data:
        fig_bf = px.bar(
            pd.DataFrame(chart_data), x="Period", y="Mean Return %", color="Group",
            barmode="group", color_discrete_sequence=["#F58518", "#72B7B2"],
        )
        fig_bf.update_layout(**CHART_LAYOUT, height=400, xaxis_title="", legend_title_text="")
        fig_bf.update_yaxes(zeroline=True, zerolinewidth=1, zerolinecolor="gray")
        st.plotly_chart(fig_bf, use_container_width=True)

    if converted:
        st.markdown("**Conversion Details**")
        conv_df = pd.DataFrame(converted)
        conv_df["FDV ($M)"] = conv_df["Ticker"].map(
            df_bf_conv.set_index("ticker")["fdv_at_listing"].dropna().to_dict()
        ).apply(lambda x: round(x / 1e6) if pd.notna(x) else None)
        spot_exchanges = df[df["exchange"] != "Binance Perps"]
        conv_df["Spot Exchanges"] = conv_df["Ticker"].apply(
            lambda t: spot_exchanges[spot_exchanges["ticker"] == t]["exchange"].nunique()
        )
        conv_df = conv_df.sort_values("Days to Spot")
        st.dataframe(conv_df, use_container_width=True, hide_index=True)

# ── Pathway: Spot-First Tokens ───────────────────────────────────────────────
st.markdown("---")
st.subheader("Pathway to Binance Perps — Spot-First Tokens")

spot_all = df_all[df_all["exchange"] != "Binance Perps"]
bf_all = df_all[(df_all["exchange"] == "Binance Perps") & (df_all["ticker"] != "XAUT")]

pathway_rows = []
for _, row in bf_all.iterrows():
    t, bd = row["ticker"], row["listing_date"]
    before = spot_all[(spot_all["ticker"] == t) & (spot_all["listing_date"] <= bd)]
    if before.empty:
        continue
    days = (bd - before["listing_date"].min()).days
    exs = sorted(before["exchange"].unique())
    bn_after = spot_all[(spot_all["ticker"] == t) & (spot_all["exchange"] == "Binance") & (spot_all["listing_date"] >= bd)]
    fdv_row = df_bf_ret[df_bf_ret["ticker"] == t] if not df_bf_ret.empty else pd.DataFrame()
    fdv = fdv_row.iloc[0]["fdv_at_listing"] if not fdv_row.empty and pd.notna(fdv_row.iloc[0]["fdv_at_listing"]) else None
    pathway_rows.append({
        "Ticker": t, "First Spot": before["listing_date"].min().strftime("%Y-%m-%d"),
        "Perps Date": bd.strftime("%Y-%m-%d"), "Days to Perps": days,
        "Exchanges Before": ", ".join(exs), "N Before": len(exs),
        "FDV ($M)": round(fdv / 1e6) if fdv else None,
        "→ Binance Spot": bn_after.iloc[0]["listing_date"].strftime("%Y-%m-%d") if not bn_after.empty else "–",
    })

if pathway_rows:
    pw = pd.DataFrame(pathway_rows).sort_values("Days to Perps")
    n_pw = len(pw)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Spot-First Tokens", n_pw)
    col_b.metric("Mean Days to Perps", f'{pw["Days to Perps"].mean():.0f}')
    fdv_vals = pw["FDV ($M)"].dropna()
    col_c.metric("Mean FDV", f"${fdv_vals.mean():.0f}M" if not fdv_vals.empty else "N/A")

    pw_c1, pw_c2 = st.columns(2)

    with pw_c1:
        st.markdown("**Exchanges Listed Before Perps**")
        ex_count = {}
        for exs in pw["Exchanges Before"]:
            for e in exs.split(", "):
                ex_count[e] = ex_count.get(e, 0) + 1
        ex_df = pd.DataFrame([{"Exchange": k, "Count": v, "Pct": f"{v}/{n_pw}"} for k, v in ex_count.items()])
        ex_df = ex_df.sort_values("Count", ascending=True)
        fig_ex = px.bar(
            ex_df, x="Count", y="Exchange", orientation="h", text="Pct",
            color="Exchange", color_discrete_map=EXCHANGE_COLORS,
        )
        fig_ex.update_layout(**CHART_LAYOUT, showlegend=False, height=350, xaxis_title="# Tokens")
        fig_ex.update_traces(textposition="outside")
        st.plotly_chart(fig_ex, use_container_width=True)

    with pw_c2:
        st.markdown("**Days from First Spot to Perps**")
        bins = pd.cut(pw["Days to Perps"], bins=[-1, 2, 7, 30], labels=["0–2 days", "3–7 days", "8+ days"])
        bin_df = bins.value_counts().reset_index()
        bin_df.columns = ["Range", "Count"]
        bin_df = bin_df.sort_values("Range")
        fig_days = px.bar(
            bin_df, x="Range", y="Count", text="Count",
            color_discrete_sequence=["#F58518"],
        )
        fig_days.update_layout(**CHART_LAYOUT, height=350, xaxis_title="", yaxis_title="# Tokens")
        fig_days.update_traces(textposition="outside")
        st.plotly_chart(fig_days, use_container_width=True)

    # FDV scatter + detail table in expanders
    with st.expander("FDV at Listing vs Days to Perps"):
        if not fdv_vals.empty:
            fig_fdv = px.scatter(
                pw.dropna(subset=["FDV ($M)"]), x="Days to Perps", y="FDV ($M)",
                text="Ticker", size_max=12,
                color_discrete_sequence=["#8B6914"],
            )
            fig_fdv.update_traces(textposition="top center", marker=dict(size=10))
            fig_fdv.update_layout(**CHART_LAYOUT, height=400, xaxis_title="Days from First Spot to Perps", yaxis_title="FDV ($M)")
            st.plotly_chart(fig_fdv, use_container_width=True)

    with st.expander("View all Spot-First → Perps tokens"):
        st.dataframe(pw, use_container_width=True, hide_index=True)
else:
    st.info("No spot-first tokens found for Binance Perps.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: RAW DATA
# ══════════════════════════════════════════════════════════════════════════════
st.header("4 · Raw Data")

display_df = df[["listing_date", "ticker", "exchange", "trading_pair"]].copy()
display_df["listing_date"] = display_df["listing_date"].dt.strftime("%Y-%m-%d")
display_df = display_df.sort_values("listing_date", ascending=False).reset_index(drop=True)
display_df.columns = ["Date", "Ticker", "Exchange", "Trading Pair"]

st.dataframe(display_df, use_container_width=True, hide_index=True)
csv = display_df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", csv, "listings.csv", "text/csv")
