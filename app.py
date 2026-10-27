"""Retail Sales Analytics Dashboard  |  run with:  streamlit run app.py"""
from __future__ import annotations

import calendar
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.charts import PALETTE, YEAR_COLORS, CSS, bar_sum, donut, heatmap, insight, kpi, pkr, style
from utils.data_cleaning import (BASKET_BANDS, DISCOUNT_BANDS, MONTH_ORDER, WEEKDAY_ORDER,
                                 load_and_clean, raw_profile, reconcile_with_pivots)

DATA_PATH = Path(__file__).parent / "data" / "imitiaz_sales.xlsx"
MONTH_ABBR = list(calendar.month_abbr)[1:]

st.set_page_config(page_title="Sales Analytics Dashboard", page_icon="🛒", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading and cleaning data...")
def get_data(path: str, mtime: float):
    df, log = load_and_clean(path)
    return df, pd.DataFrame(log), reconcile_with_pivots(path, df), raw_profile(path)


uploaded = st.sidebar.file_uploader("Optional: upload another sales file (.xlsx with a 'data' sheet)",
                                    type=["xlsx"])
if uploaded is not None:
    tmp = Path(__file__).parent / "data" / "_uploaded.xlsx"
    tmp.write_bytes(uploaded.getbuffer())
    source = tmp
else:
    source = DATA_PATH

try:
    full, clean_log, recon, profile = get_data(str(source), source.stat().st_mtime)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load the dataset: {exc}")
    st.stop()

full = full.assign(YearStr=full["Year"].astype(str))

# --------------------------------------------------------------------------- filters
st.sidebar.markdown("## 🎛️ Filters")
d_min, d_max = full["Date"].min().date(), full["Date"].max().date()
rng = st.sidebar.date_input("Date range", (d_min, d_max), min_value=d_min, max_value=d_max)
start, end = (rng[0], rng[1]) if isinstance(rng, (tuple, list)) and len(rng) == 2 else (
    (rng[0], rng[0]) if isinstance(rng, (tuple, list)) else (rng, rng))

branches = sorted(full["Branch"].unique())
f_branch = st.sidebar.multiselect("Branch", branches, default=branches)
cats = sorted(full["Category"].unique())
f_cat = st.sidebar.multiselect("Category", cats, default=cats)
subs = sorted(full.loc[full["Category"].isin(f_cat), "Subcategory"].unique())
f_sub = st.sidebar.multiselect("Subcategory", subs, default=subs)
types = ["Discounted", "Full price"]
f_type = st.sidebar.multiselect("Sale type", types, default=types)
no_hv = st.sidebar.checkbox("Exclude high-value outliers", value=False,
                            help="Removes transactions above the IQR fence (mostly Electronics).")

df = full[
    full["Date"].between(pd.Timestamp(start), pd.Timestamp(end))
    & full["Branch"].isin(f_branch) & full["Category"].isin(f_cat) & full["Subcategory"].isin(f_sub)
    & full["Discounted"].isin(f_type)
]
if no_hv:
    df = df[~df["HighValueSale"]]

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(df):,}** of {len(full):,} transactions")

# --------------------------------------------------------------------------- header
st.markdown(
    '<div class="hero"><h1>🛒 Retail Sales Analytics</h1>'
    "<p>Revenue, categories, branches and discounting across 4 cities, built from the cleaned transaction data (PKR).</p></div>",
    unsafe_allow_html=True)

if df.empty:
    st.warning("No transactions match the current filters. Widen the filters in the sidebar.")
    st.stop()

net, gross, disc = df["NetSales"].sum(), df["GrossSales"].sum(), df["DiscountAmount"].sum()
n_tx, units = len(df), int(df["Quantity"].sum())
by_year = df.groupby("Year")["NetSales"].sum()
yoy_txt = ""
if len(by_year) >= 2:
    y1, y0 = by_year.index[-1], by_year.index[-2]
    yoy_txt = f"{y1} vs {y0}: {(by_year.iloc[-1] / by_year.iloc[-2] - 1) * 100:+.1f}%"

tabs = st.tabs(["📊 Overview", "📈 Time Trends", "🧺 Category & Products", "🏬 Branches",
                "🏷️ Discounts", "🔎 Data Explorer", "🧹 Data Quality"])

# =========================================================================== OVERVIEW
with tabs[0]:
    c = st.columns(6)
    c[0].markdown(kpi("Net sales", pkr(net), yoy_txt), unsafe_allow_html=True)
    c[1].markdown(kpi("Gross sales", pkr(gross), "before discounts", "#6366F1"), unsafe_allow_html=True)
    c[2].markdown(kpi("Transactions", f"{n_tx:,}", f"{units:,} units sold", "#F59E0B"), unsafe_allow_html=True)
    c[3].markdown(kpi("Avg order value", pkr(net / n_tx), f"median {pkr(df['NetSales'].median())}", "#06B6D4"),
                  unsafe_allow_html=True)
    c[4].markdown(kpi("Discount given", pkr(disc), f"{disc / gross * 100:.1f}% of gross", "#EF4444"),
                  unsafe_allow_html=True)
    c[5].markdown(kpi("Discounted orders", f"{(df['Discounted'] == 'Discounted').mean() * 100:.0f}%",
                      "of all transactions", "#8B5CF6"), unsafe_allow_html=True)
    st.write("")

    a, b = st.columns([3, 2])
    m = df.groupby(["YearStr", "MonthNum"])["NetSales"].sum().reset_index()
    m["Month"] = m["MonthNum"].map(lambda i: MONTH_ABBR[i - 1])
    fig = px.line(m, x="Month", y="NetSales", color="YearStr", markers=True, color_discrete_map=YEAR_COLORS,
                  category_orders={"Month": MONTH_ABBR})
    fig.update_layout(legend_title_text="Year")
    a.plotly_chart(style(fig, 380, "Monthly net sales by year"), use_container_width=True)
    b.plotly_chart(donut(df, "Category", title="Net sales share by category", height=380),
                   use_container_width=True)

    a, b = st.columns(2)
    a.plotly_chart(bar_sum(df, "Branch", title="Net sales by branch", horizontal=True, height=320),
                   use_container_width=True)
    yr = df.groupby("YearStr")[["GrossSales", "NetSales"]].sum().reset_index().melt(
        id_vars="YearStr", var_name="Measure", value_name="PKR")
    fig = px.bar(yr, x="YearStr", y="PKR", color="Measure", barmode="group",
                 color_discrete_sequence=["#A5B4FC", "#0F766E"])
    fig.update_xaxes(title="")
    b.plotly_chart(style(fig, 320, "Gross vs net sales by year"), use_container_width=True)

    st.markdown("### 💡 Key insights")
    ins = []
    cat_s = df.groupby("Category")["NetSales"].sum().sort_values(ascending=False)
    cat_n = df["Category"].value_counts()
    top = cat_s.index[0]
    ins.append(insight(f"<b>{top}</b> drives <b>{cat_s.iloc[0] / net * 100:.0f}%</b> of net sales from only "
                       f"<b>{cat_n[top] / n_tx * 100:.0f}%</b> of transactions (avg ticket "
                       f"{pkr(df.loc[df['Category'] == top, 'NetSales'].mean())}).", "amber"))
    br = df.groupby("Branch")["NetSales"].sum().sort_values(ascending=False)
    ins.append(insight(f"Top branch by revenue: <b>{br.index[0]}</b> ({pkr(br.iloc[0])}, {br.iloc[0] / net * 100:.0f}% "
                       f"of total); lowest: <b>{br.index[-1]}</b> ({pkr(br.iloc[-1])}).", ""))
    mm = df.groupby("MonthNum")["NetSales"].sum()
    ins.append(insight(f"Strongest month overall: <b>{MONTH_ORDER[mm.idxmax() - 1]}</b> ({pkr(mm.max())}); "
                       f"weakest: <b>{MONTH_ORDER[mm.idxmin() - 1]}</b> ({pkr(mm.min())}).", "good"))
    if yoy_txt:
        ins.append(insight(f"Net sales {yoy_txt}. Because electronics orders are so large, a handful of big tickets "
                           "can swing a year; try the sidebar toggle to exclude high-value outliers.", "warn"))
    ins.append(insight(f"Discounts cost <b>{pkr(disc)}</b> ({disc / gross * 100:.1f}% of gross sales); "
                       f"{(df['Discounted'] == 'Discounted').mean() * 100:.0f}% of orders carried a discount.", ""))
    st.markdown("".join(ins), unsafe_allow_html=True)

# =========================================================================== TRENDS
with tabs[1]:
    st.markdown("### Sales over time")
    ts = df.groupby("YearMonth")["NetSales"].sum().reset_index().sort_values("YearMonth")
    ts["3-month average"] = ts["NetSales"].rolling(3, min_periods=1).mean()
    fig = px.line(ts, x="YearMonth", y=["NetSales", "3-month average"],
                  color_discrete_sequence=["#94A3B8", "#0F766E"])
    fig.update_layout(legend_title_text="", yaxis_title="PKR", xaxis_title="")
    st.plotly_chart(style(fig, 380, "Monthly net sales with 3-month moving average"), use_container_width=True)

    a, b = st.columns(2)
    hm = df.pivot_table(index="Month", columns="Year", values="NetSales", aggfunc="sum").reindex(
        [mo for mo in MONTH_ORDER if mo in set(df["Month"])]).div(1000)
    a.plotly_chart(heatmap(hm, "Net sales heatmap, month x year (PKR K)", height=440), use_container_width=True)
    q = df.groupby(["Quarter", "YearStr"])["NetSales"].sum().reset_index()
    fig = px.bar(q, x="Quarter", y="NetSales", color="YearStr", barmode="group", color_discrete_map=YEAR_COLORS)
    fig.update_layout(legend_title_text="Year")
    b.plotly_chart(style(fig, 440, "Quarterly net sales"), use_container_width=True)

    a, b = st.columns(2)
    wd = df.groupby("Weekday").agg(NetSales=("NetSales", "sum"), Transactions=("NetSales", "size")).reindex(
        [w for w in WEEKDAY_ORDER if w in set(df["Weekday"])]).reset_index()
    fig = px.bar(wd, x="Weekday", y="Transactions", text="Transactions", color_discrete_sequence=["#6366F1"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    a.plotly_chart(style(fig, 360, "Transactions by weekday"), use_container_width=True)
    ym = df.groupby(["YearStr", "Category"])["NetSales"].sum().reset_index()
    ym = ym[ym["Category"] != "Electronics"]
    fig = px.bar(ym, x="Category", y="NetSales", color="YearStr", barmode="group", color_discrete_map=YEAR_COLORS)
    fig.update_layout(legend_title_text="Year")
    b.plotly_chart(style(fig, 360, "Year-by-year, categories excluding Electronics"), use_container_width=True)

    st.markdown("##### Growth by category (first vs last year in selection)")
    pv = df.pivot_table(index="Category", columns="Year", values="NetSales", aggfunc="sum")
    if pv.shape[1] >= 2:
        g = ((pv.iloc[:, -1] / pv.iloc[:, 0] - 1) * 100).round(1).sort_values().reset_index()
        g.columns = ["Category", "Growth"]
        g["Positive"] = np.where(g["Growth"] >= 0, "Growth", "Decline")
        fig = px.bar(g, x="Growth", y="Category", orientation="h", color="Positive", text="Growth",
                     color_discrete_map={"Growth": "#10B981", "Decline": "#EF4444"})
        fig.update_traces(texttemplate="%{text}%", textposition="outside", cliponaxis=False)
        fig.update_layout(showlegend=False, xaxis_title=f"% change {pv.columns[0]} to {pv.columns[-1]}")
        st.plotly_chart(style(fig, 360), use_container_width=True)
    else:
        st.info("Select a date range spanning at least two years to see growth.")

# =========================================================================== CATEGORY / PRODUCT
with tabs[2]:
    st.markdown("### Category & product performance")
    a, b = st.columns(2)
    fig = px.treemap(df, path=[px.Constant("All"), "Category", "Subcategory"], values="NetSales",
                     color_discrete_sequence=PALETTE)
    a.plotly_chart(style(fig, 440, "Where revenue comes from (category > subcategory)"), use_container_width=True)
    sh = pd.DataFrame({"Net sales": df.groupby("Category")["NetSales"].sum() / net * 100,
                       "Transactions": df["Category"].value_counts() / n_tx * 100}).round(1)
    sh = sh.sort_values("Net sales", ascending=False).reset_index().rename(columns={"index": "Category"})
    sh = sh.melt(id_vars=sh.columns[0], var_name="Share of", value_name="Percent")
    sh.columns = ["Category", "Share of", "Percent"]
    fig = px.bar(sh, x="Category", y="Percent", color="Share of", barmode="group",
                 color_discrete_sequence=["#0F766E", "#F59E0B"], text="Percent")
    fig.update_traces(texttemplate="%{text}%", textposition="outside", cliponaxis=False)
    b.plotly_chart(style(fig, 440, "Revenue share vs transaction share"), use_container_width=True)

    n_top = st.slider("Number of top products", 5, 25, 10)
    a, b = st.columns(2)
    a.plotly_chart(bar_sum(df, "Product", title=f"Top {n_top} products by net sales", horizontal=True,
                           top=n_top, height=max(340, 28 * n_top + 80)), use_container_width=True)
    cnt = (df.groupby("Product").agg(Units=("Quantity", "sum")).sort_values("Units", ascending=False)
           .head(n_top).reset_index().sort_values("Units"))
    fig = px.bar(cnt, x="Units", y="Product", orientation="h", text="Units", color_discrete_sequence=["#6366F1"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    b.plotly_chart(style(fig, max(340, 28 * n_top + 80), f"Top {n_top} products by units sold"),
                   use_container_width=True)

    prod = df.groupby("Product")["NetSales"].sum().sort_values(ascending=False)
    cum = (prod.cumsum() / prod.sum() * 100).reset_index(drop=True)
    n80 = int((cum < 80).sum() + 1)
    fig = go.Figure(go.Scatter(x=list(range(1, len(cum) + 1)), y=cum, fill="tozeroy", line=dict(color="#0F766E")))
    fig.add_hline(y=80, line_dash="dash", line_color="#EF4444", annotation_text="80% of sales")
    fig.update_layout(xaxis_title="Products ranked by net sales", yaxis_title="Cumulative % of net sales")
    st.plotly_chart(style(fig, 340, f"Pareto: {n80} of {len(prod)} products generate 80% of net sales"),
                    use_container_width=True)

    st.markdown("##### Category scorecard")
    sc = df.groupby("Category").agg(
        NetSales=("NetSales", "sum"), GrossSales=("GrossSales", "sum"), Transactions=("NetSales", "size"),
        Units=("Quantity", "sum"), AvgOrderValue=("NetSales", "mean"), Discount=("DiscountAmount", "sum"))
    sc["DiscountRate%"] = (sc["Discount"] / sc["GrossSales"] * 100).round(1)
    sc["Share%"] = (sc["NetSales"] / net * 100).round(1)
    st.dataframe(sc.sort_values("NetSales", ascending=False).round(0).reset_index(),
                 use_container_width=True, hide_index=True)

# =========================================================================== BRANCHES
with tabs[3]:
    st.markdown("### Branch performance")
    bs = df.groupby("Branch").agg(NetSales=("NetSales", "sum"), Transactions=("NetSales", "size"),
                                  Units=("Quantity", "sum"), AOV=("NetSales", "mean"),
                                  Discount=("DiscountAmount", "sum"), Gross=("GrossSales", "sum"))
    bs["DiscountRate%"] = (bs["Discount"] / bs["Gross"] * 100).round(1)
    bs["ElectronicsShare%"] = (df[df["Category"] == "Electronics"].groupby("Branch")["NetSales"].sum()
                               / bs["NetSales"] * 100).round(1)
    bs = bs.fillna(0)
    a, b = st.columns(2)
    yb = df.groupby(["Branch", "YearStr"])["NetSales"].sum().reset_index()
    fig = px.bar(yb, x="Branch", y="NetSales", color="YearStr", barmode="group", color_discrete_map=YEAR_COLORS)
    fig.update_layout(legend_title_text="Year")
    a.plotly_chart(style(fig, 400, "Net sales by branch and year"), use_container_width=True)
    hm = df.pivot_table(index="Branch", columns="Category", values="NetSales", aggfunc="sum").fillna(0).div(1000)
    b.plotly_chart(heatmap(hm, "Branch x category net sales (PKR K)", height=400), use_container_width=True)

    bm = df.groupby(["YearMonth", "Branch"])["NetSales"].sum().reset_index()
    fig = px.line(bm, x="YearMonth", y="NetSales", color="Branch", color_discrete_sequence=PALETTE)
    fig.update_layout(xaxis_title="", yaxis_title="PKR", legend_title_text="")
    st.plotly_chart(style(fig, 380, "Monthly net sales by branch"), use_container_width=True)

    a, b = st.columns(2)
    fig = px.bar(bs.reset_index(), x="Branch", y="Transactions", text="Transactions",
                 color_discrete_sequence=["#6366F1"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    a.plotly_chart(style(fig, 340, "Transactions by branch"), use_container_width=True)
    fig = px.bar(bs.reset_index(), x="Branch", y="AOV", text=bs["AOV"].map(lambda v: pkr(v, False)).values,
                 color_discrete_sequence=["#F59E0B"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    b.plotly_chart(style(fig, 340, "Average order value by branch (PKR)"), use_container_width=True)

    st.markdown("##### Branch scorecard")
    st.dataframe(bs.drop(columns=["Discount", "Gross"]).round(1).reset_index(), use_container_width=True,
                 hide_index=True)

# =========================================================================== DISCOUNTS
with tabs[4]:
    st.markdown("### Discount analysis")
    d = st.columns(4)
    d[0].markdown(kpi("Total discount", pkr(disc), f"{disc / gross * 100:.1f}% of gross", "#EF4444"),
                  unsafe_allow_html=True)
    dd = df[df["Discounted"] == "Discounted"]
    d[1].markdown(kpi("Discounted orders", f"{len(dd):,}", f"{len(dd) / n_tx * 100:.1f}% of orders", "#F59E0B"),
                  unsafe_allow_html=True)
    d[2].markdown(kpi("Avg discount (when given)", f"{dd['DiscountPct'].mean():.1f}%" if len(dd) else "-",
                      "per discounted order", "#6366F1"), unsafe_allow_html=True)
    d[3].markdown(kpi("Max discount", f"{df['DiscountPct'].max():.1f}%", "single transaction", "#8B5CF6"),
                  unsafe_allow_html=True)
    st.write("")

    a, b = st.columns(2)
    cd = df.groupby("Category").agg(D=("DiscountAmount", "sum"), G=("GrossSales", "sum")).reset_index()
    cd["Rate"] = (cd["D"] / cd["G"] * 100).round(2)
    cd = cd.sort_values("Rate")
    fig = px.bar(cd, x="Rate", y="Category", orientation="h", text="Rate", color="Rate",
                 color_continuous_scale=["#FDE68A", "#EF4444"])
    fig.update_traces(texttemplate="%{text}%", textposition="outside", cliponaxis=False)
    fig.update_coloraxes(showscale=False)
    fig.update_layout(xaxis_title="Discount as % of gross sales")
    a.plotly_chart(style(fig, 380, "Effective discount rate by category"), use_container_width=True)
    bd = df.groupby("DiscountBand").size().reindex(DISCOUNT_BANDS).dropna().reset_index()
    bd.columns = ["DiscountBand", "Transactions"]
    fig = px.bar(bd, x="DiscountBand", y="Transactions", text="Transactions", color_discrete_sequence=["#F59E0B"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    b.plotly_chart(style(fig, 380, "Transactions by discount band"), use_container_width=True)

    a, b = st.columns(2)
    bk = df.groupby("BasketBand")["DiscountPct"].mean().reindex(BASKET_BANDS).dropna().round(2).reset_index()
    fig = px.bar(bk, x="BasketBand", y="DiscountPct", text="DiscountPct", color_discrete_sequence=["#6366F1"])
    fig.update_traces(texttemplate="%{text}%", textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title="Order size", yaxis_title="Avg discount %")
    a.plotly_chart(style(fig, 360, "Do bigger orders get bigger discounts?"), use_container_width=True)
    by = df.groupby(["Branch", "YearStr"]).agg(D=("DiscountAmount", "sum"), G=("GrossSales", "sum")).reset_index()
    by["Rate"] = (by["D"] / by["G"] * 100).round(2)
    fig = px.bar(by, x="Branch", y="Rate", color="YearStr", barmode="group", color_discrete_map=YEAR_COLORS)
    fig.update_layout(yaxis_title="Discount % of gross", legend_title_text="Year")
    b.plotly_chart(style(fig, 360, "Discount rate by branch and year"), use_container_width=True)

    fig = px.scatter(df, x="GrossSales", y="DiscountPct", color="Category", log_x=True, opacity=.7,
                     color_discrete_sequence=PALETTE, hover_data=["Product", "Branch", "NetSales"])
    fig.update_layout(xaxis_title="Gross sales (PKR, log scale)", yaxis_title="Discount %")
    st.plotly_chart(style(fig, 420, "Discount % vs transaction size"), use_container_width=True)

# =========================================================================== EXPLORER
with tabs[5]:
    st.markdown("### Build your own chart")
    dims = ["Year", "Quarter", "Month", "Weekday", "Branch", "City", "Category", "Subcategory", "Product",
            "Discounted", "DiscountBand", "PriceBand", "BasketBand"]
    meas = ["NetSales", "GrossSales", "DiscountAmount", "Quantity", "UnitPrice", "DiscountPct"]
    c1, c2, c3, c4, c5 = st.columns(5)
    kind = c1.selectbox("Chart type", ["Bar", "Line (by month)", "Box", "Scatter", "Histogram"])
    x = c2.selectbox("Group / X", dims, index=dims.index("Category"))
    y = c3.selectbox("Measure", meas)
    agg = c4.selectbox("Aggregation", ["Sum", "Average", "Count"])
    color = c5.selectbox("Colour by", ["None"] + dims, index=0)
    cc = None if color == "None" else color
    func = {"Sum": "sum", "Average": "mean", "Count": "count"}[agg]
    dfx = df.assign(**{"Year": df["YearStr"]})
    if kind == "Bar":
        keys = [x] + ([cc] if cc and cc != x else [])
        g = dfx.groupby(keys)[y].agg(func).reset_index()
        fig = px.bar(g, x=x, y=y, color=cc if cc and cc != x else None, barmode="group",
                     color_discrete_sequence=PALETTE)
    elif kind == "Line (by month)":
        keys = ["YearMonth"] + ([cc] if cc else [])
        g = dfx.groupby(keys)[y].agg(func).reset_index()
        fig = px.line(g, x="YearMonth", y=y, color=cc, markers=True, color_discrete_sequence=PALETTE)
    elif kind == "Box":
        fig = px.box(dfx, x=x, y=y, color=cc, color_discrete_sequence=PALETTE)
    elif kind == "Scatter":
        fig = px.scatter(dfx, x="GrossSales" if y != "GrossSales" else "Quantity", y=y, color=cc, opacity=.7,
                         color_discrete_sequence=PALETTE, hover_data=["Product", "Branch"])
    else:
        fig = px.histogram(dfx, x=y, color=cc, barmode="overlay", opacity=.75, nbins=40,
                           color_discrete_sequence=PALETTE)
    st.plotly_chart(style(fig, 460), use_container_width=True)

    st.markdown("### Data table")
    show = st.multiselect("Columns", list(df.columns), default=[
        "TransactionID", "Date", "Branch", "Category", "Product", "Quantity", "UnitPrice", "DiscountPct", "NetSales"])
    st.dataframe(df[show] if show else df, use_container_width=True, height=360)
    e1, e2 = st.columns(2)
    e1.download_button("⬇️ Download filtered data (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "sales_filtered.csv", "text/csv")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        full.drop(columns=["YearStr"]).to_excel(xw, index=False, sheet_name="Cleaned_Data")
        clean_log.to_excel(xw, index=False, sheet_name="Cleaning_Log")
    e2.download_button("⬇️ Download full cleaned dataset (Excel)", buf.getvalue(), "Sales_cleaned.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =========================================================================== DATA QUALITY
with tabs[6]:
    st.markdown("### Data quality & validation report")
    passed = int(clean_log["Action"].eq("Passed").sum())
    total_checks = int(clean_log["Step"].eq("Validation").sum())
    c = st.columns(4)
    c[0].markdown(kpi("Transactions", f"{len(full):,}", "after cleaning"), unsafe_allow_html=True)
    c[1].markdown(kpi("Validation checks passed", f"{passed}/{total_checks}", "arithmetic & consistency",
                      "#10B981"), unsafe_allow_html=True)
    c[2].markdown(kpi("Missing cells", f"{int(full.drop(columns=['YearStr']).isna().sum().sum())}", "all columns",
                      "#F59E0B"), unsafe_allow_html=True)
    c[3].markdown(kpi("High-value flagged", f"{int(full['HighValueSale'].sum())}", "kept, not removed", "#8B5CF6"),
                  unsafe_allow_html=True)
    st.write("")
    st.dataframe(clean_log, use_container_width=True, hide_index=True)
    if not recon.empty:
        st.markdown("##### Reconciliation with the workbook's 'year wise sales' pivot sheet")
        st.dataframe(recon, use_container_width=True, hide_index=True)
    st.markdown("##### Raw column profile")
    st.dataframe(profile, use_container_width=True, hide_index=True, height=360)
    st.info("Filters change only what is displayed; the cleaned dataset itself is never altered.")
