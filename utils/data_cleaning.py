"""Loading, validation and feature engineering for the retail sales dataset.

The workbook contains several pivot-table sheets plus the raw transactions in
the sheet called `data`. Only the raw sheet is analysed; the pivot sheets are
used afterwards to reconcile totals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DATA_SHEET = "data"

RENAME = {
    "Transaction ID": "TransactionID", "Product Name": "Product", "Unit Price (PKR)": "UnitPrice",
    "Gross Sales (PKR)": "GrossSales", "Discount %": "DiscountPct",
    "Discount Amount (PKR)": "DiscountAmount", "Net Sales (PKR)": "NetSales",
}
MONTH_ORDER = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DISCOUNT_BANDS = ["No discount", "0-5%", "5-10%", "10-20%", "20-30%"]
PRICE_BANDS = ["< 1K", "1K-5K", "5K-20K", "20K+"]
BASKET_BANDS = ["1 unit", "2-3 units", "4-6 units", "7+ units"]


def load_and_clean(path) -> tuple[pd.DataFrame, list[dict]]:
    log: list[dict] = []
    raw = pd.read_excel(path, sheet_name=DATA_SHEET)
    df = raw.copy()
    n0 = len(df)

    # 1. Headers / text hygiene
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=RENAME)
    for c in ["TransactionID", "Month", "Branch", "City", "Category", "Subcategory", "Product"]:
        df[c] = df[c].map(lambda v: " ".join(v.split()) if isinstance(v, str) else v)
    log.append(dict(Step="Load", Check="Source sheet", Result=f"'{DATA_SHEET}' sheet: {n0} rows x {raw.shape[1]} columns",
                    Action="Other sheets are pivot summaries; used only for reconciliation", Rows=0))

    # 2. Types
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    bad_dates = int(df["Date"].isna().sum())
    df = df.dropna(subset=["Date"])
    log.append(dict(Step="Types", Check="Date parsing", Result=f"{bad_dates} unparseable dates",
                    Action="Rows dropped" if bad_dates else "None needed", Rows=bad_dates))

    # 3. Duplicates and nulls
    dup_id = int(df["TransactionID"].duplicated().sum())
    df = df.drop_duplicates(subset="TransactionID")
    log.append(dict(Step="Duplicates", Check="Repeated TransactionID", Result=f"{dup_id} found",
                    Action="Removed" if dup_id else "None needed", Rows=dup_id))
    nulls = int(df.isna().sum().sum())
    log.append(dict(Step="Missing values", Check="Null cells (all columns)", Result=f"{nulls} found",
                    Action="None needed" if nulls == 0 else "Review", Rows=nulls))

    # 4. Arithmetic / consistency validation (reported; values are recalculated if wrong)
    gross_bad = int((df["GrossSales"] != df["Quantity"] * df["UnitPrice"]).sum())
    disc_bad = int((abs(df["DiscountAmount"] - df["GrossSales"] * df["DiscountPct"]) > 1).sum())
    net_bad = int((abs(df["NetSales"] - (df["GrossSales"] - df["DiscountAmount"])) > 0.01).sum())
    year_bad = int((df["Date"].dt.year != df["Year"]).sum())
    month_bad = int((df["Date"].dt.month_name() != df["Month"]).sum())
    city_bad = int((df["Branch"].str.split(" - ").str[0] != df["City"]).sum())
    for chk, bad in [("Gross = Quantity x Unit price", gross_bad), ("Discount amt = Gross x Discount %", disc_bad),
                     ("Net = Gross - Discount", net_bad), ("Year column matches Date", year_bad),
                     ("Month column matches Date", month_bad), ("City matches Branch", city_bad)]:
        log.append(dict(Step="Validation", Check=chk, Result=f"{bad} mismatches",
                        Action="Passed" if bad == 0 else "Flagged", Rows=bad))
    if net_bad:
        df["NetSales"] = df["GrossSales"] - df["DiscountAmount"]
    cat_multi = int((df.groupby("Product")["Category"].nunique() > 1).sum())
    log.append(dict(Step="Validation", Check="Each product belongs to one category", Result=f"{cat_multi} violations",
                    Action="Passed" if cat_multi == 0 else "Flagged", Rows=cat_multi))
    price_var = int((df.groupby("Product")["UnitPrice"].nunique() > 1).sum())
    log.append(dict(Step="Observation", Check="Products sold at more than one unit price",
                    Result=f"{price_var} of {df['Product'].nunique()} products",
                    Action="Kept as-is (price history/variants unknown); treat product-level price comparisons with care",
                    Rows=price_var))

    # 5. Feature engineering
    df["DiscountPct"] = (df["DiscountPct"] * 100).round(2)          # fraction -> percentage points
    df["Discounted"] = np.where(df["DiscountAmount"] > 0, "Discounted", "Full price")
    df["DiscountBand"] = pd.cut(df["DiscountPct"], [-0.01, 0, 5, 10, 20, 100],
                                labels=DISCOUNT_BANDS).astype(str)
    df["PriceBand"] = pd.cut(df["UnitPrice"], [0, 1000, 5000, 20000, 1e9], labels=PRICE_BANDS).astype(str)
    df["BasketBand"] = pd.cut(df["Quantity"], [0, 1, 3, 6, 1000], labels=BASKET_BANDS).astype(str)
    df["Quarter"] = "Q" + df["Date"].dt.quarter.astype(str)
    df["MonthNum"] = df["Date"].dt.month
    df["YearMonth"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["Weekday"] = df["Date"].dt.day_name()

    q1, q3 = df["NetSales"].quantile([.25, .75])
    fence = q3 + 1.5 * (q3 - q1)
    df["HighValueSale"] = df["NetSales"] > fence
    n_hv = int(df["HighValueSale"].sum())
    hv_cat = df.loc[df["HighValueSale"], "Category"].value_counts()
    top_hv = f"{hv_cat.index[0]} ({hv_cat.iloc[0] / n_hv:.0%})" if n_hv else "-"
    log.append(dict(Step="Outliers", Check=f"Net sales above IQR fence (PKR {fence:,.0f})",
                    Result=f"{n_hv} transactions, mostly {top_hv}",
                    Action="Kept (genuine big-ticket sales); flagged in HighValueSale", Rows=n_hv))
    log.append(dict(Step="Features", Check="Engineered columns",
                    Result="Quarter, YearMonth, Weekday, Discounted, DiscountBand, PriceBand, BasketBand, HighValueSale",
                    Action="Added; DiscountPct converted to percentage points", Rows=0))

    df = df.sort_values("Date").reset_index(drop=True)
    return df, log


def reconcile_with_pivots(path, df: pd.DataFrame) -> pd.DataFrame:
    """Compare the 'year wise sales' pivot sheet against totals recomputed from raw data."""
    try:
        p = pd.read_excel(path, sheet_name="year wise sales", header=None)
        rows = []
        for a, b in zip(p.iloc[:, 0], p.iloc[:, 1]):
            if isinstance(a, (int, float)) and not pd.isna(a) and 2000 < a < 2100 and not pd.isna(b):
                rows.append((int(a), float(b)))
        out = pd.DataFrame(rows, columns=["Year", "Pivot sheet (PKR)"])
        out["Recomputed (PKR)"] = out["Year"].map(df.groupby("Year")["NetSales"].sum())
        out["Difference"] = (out["Recomputed (PKR)"] - out["Pivot sheet (PKR)"]).round(2)
        out["Status"] = np.where(out["Difference"].abs() < 1, "Match", "Differs")
        return out
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def raw_profile(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=DATA_SHEET)
    return pd.DataFrame({"Column": raw.columns, "Type": raw.dtypes.astype(str).values,
                         "Missing": raw.isna().sum().values, "Unique": raw.nunique().values})
