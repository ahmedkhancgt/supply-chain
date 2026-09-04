# supply-chain

Supply Chain repository

## Inventory planning pipeline

`src/inventory_planning.py` computes reorder points, safety stock, and
economic order quantity (EOQ) for each product from order history, using
an ABC (volume x revenue) product classification to set a service-level
target per product.

### Setup

```bash
pip install -r requirements.txt
```

### Run

```bash
python3 src/inventory_planning.py
```

By default it reads `data/Germany.xlsx`. To point it at a different file or
country, edit the `Config` defaults at the top of `src/inventory_planning.py`
(`data_path`, `country`, `lead_time_days`, `lead_time_sd_days`, `analysis_window_months`).

`ordering_cost_per_order` and `holding_rate` are **placeholder values**
(not derivable from the transaction data) — replace them with your real
operating costs before trusting the `eoq_*` columns for purchasing
decisions.

### Output

Written to `output/` (not committed to git):

- `reorder_recommendations.csv` / `inventory_report.xlsx` — per-product
  reorder point and safety stock under a fixed lead time and under an
  uncertain lead time, plus economic order quantity (EOQ), ranked by
  safety-stock investment (units x avg selling price).
- `safety_stock_vs_variability.png` — safety stock vs. demand variability,
  colored by service level.
- `product_mix_distribution.png` — count of SKUs per ABC class.

For a quick-reference table of every output column, see
[`docs/SKUs.md`](docs/SKUs.md). For the full explanation of the formulas
behind them (with worked examples), see
[`docs/COLUMN_DEFINITIONS.md`](docs/COLUMN_DEFINITIONS.md).

### What the pipeline does

1. Loads transactions and removes duplicates, cancelled orders (invoices
   starting with `C`), non-product line items (postage, manual charges),
   and rows with non-positive quantity or price.
2. Restricts to the most recent `analysis_window_months` of order history.
3. Aggregates daily units sold and revenue per product, then computes each
   product's average daily demand and its standard deviation.
4. Classifies products into 9 classes (A/B/C by volume x A/B/C by revenue)
   via `inventorize3.productmix`, and maps each class to a target service
   level (higher for higher-priority classes).
5. Computes reorder point and safety stock two ways: assuming a fixed lead
   time, and accounting for uncertainty in the lead time itself. The
   lead-time-variability formula is implemented directly in this script
   rather than calling `inventorize3.reorderpoint_leadtime_variability`,
   which has a bug (it XORs the lead-time standard deviation instead of
   squaring it, understating safety stock).
6. Computes each product's economic order quantity (EOQ) — how much to
   order each time, complementing the reorder point's answer of when to
   order — plus a practical order quantity rounded to a convenient order
   cycle, and the resulting annual ordering/holding/logistics cost.
7. Writes the ranked recommendations, an executive summary, and two charts.

`evaluate_quantity_discount()` in `src/inventory_planning.py` is a
standalone helper (not run automatically) for comparing total cost at EOQ
vs. at a supplier's discounted order quantity for one product — call it
manually when you have a real discount offer.
