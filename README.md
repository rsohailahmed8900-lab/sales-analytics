# 🛒 Retail Sales Analytics Dashboard (Streamlit)

Interactive, cleaned sales report built from `data/imitiaz_sales.xlsx` (1,000 transactions, 2023-2025,
4 branches, 8 categories, PKR).

## Quick start
**Windows:** double-click `run.bat`  |  **macOS / Linux:** `bash run.sh`

Or manually (Python 3.9+):
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Opens at http://localhost:8501

## Structure
```
sales_analytics_dashboard/
├── app.py                   # Streamlit app: 7 tabs + sidebar filters
├── requirements.txt
├── .streamlit/config.toml   # Streamlit theme/server settings
├── utils/
│   ├── data_cleaning.py     # Load, validate, engineer features, reconcile
│   └── charts.py            # Plotly helpers, KPI cards, CSS, PKR formatter
├── data/imitiaz_sales.xlsx  # Source workbook
├── run.sh / run.bat         # One-click launchers
└── README.md
```

## Data preparation
The workbook has 9 sheets; 7 are pivot summaries or empty. Only the raw `data` sheet is analysed, and the
`year wise sales` pivot is used to reconcile totals (all 3 years match to the rupee).

| Check | Result |
|---|---|
| Duplicate transaction IDs / missing values / bad dates | None found |
| Gross = Qty x Price, Discount = Gross x %, Net = Gross - Discount | All rows pass |
| Year / Month / City agree with Date / Branch | All rows pass |
| Each product maps to a single category | Pass |
| Products sold at several unit prices | All 138 products, kept as-is and documented |
| High-value outliers (> PKR 13,651 net) | 119 flagged in `HighValueSale`, kept (86% Electronics) |

Engineered columns: `Quarter`, `YearMonth`, `Weekday`, `Discounted`, `DiscountBand`, `PriceBand`,
`BasketBand`, `HighValueSale`; `DiscountPct` is converted to percentage points.

## Tabs
1. **Overview** KPIs, monthly trend by year, category mix, auto-generated insights
2. **Time Trends** moving average, month x year heatmap, quarters, weekdays, category growth
3. **Category & Products** treemap, revenue vs transaction share, top-N products, Pareto, scorecard
4. **Branches** yearly comparison, branch x category heatmap, monthly lines, scorecard
5. **Discounts** discount rate by category/branch, bands, order size vs discount, scatter
6. **Data Explorer** custom chart builder, data table, CSV/Excel export
7. **Data Quality** cleaning log, pivot reconciliation, raw column profile

Sidebar filters (date range, branch, category, subcategory, sale type, outlier toggle) apply to every chart.
You can also upload another workbook that has a sheet named `data` with the same columns.

## Notes
- Streamlit is pinned `<1.50` because the app uses `use_container_width`, which newer releases deprecate.
"# sales-analytics" 
