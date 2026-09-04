# SKU Output Data Dictionary

Quick-reference table for every column in `output/reorder_recommendations.csv`
and the "Reorder Recommendations" sheet of `output/inventory_report.xlsx`
(one row per product/SKU). For formulas and worked examples, see
[`COLUMN_DEFINITIONS.md`](COLUMN_DEFINITIONS.md).

| Column | Type | Example | What it is |
|---|---|---|---|
| `Description` | text | `STOOL HOME SWEET HOME` | Product name (the SKU identifier used throughout this pipeline) |
| `average` | number | `30.5` | Average units sold per day, over the analysis window |
| `sd` | number | `41.72` | Standard deviation of daily units sold — demand volatility |
| `total_sales` | number | `2745` | Total units sold across the whole analysis window |
| `total_revenue` | number | `4108.75` | Total revenue across the whole analysis window |
| `avg_unit_price` | number | `1.50` | `total_revenue / total_sales` — effective average selling price |
| `product_mix` | text (9 values) | `A_A` | ABC class: `<volume class>_<revenue class>`, each `A`/`B`/`C` |
| `service_level` | number, 0–1 | `0.95` | Target probability of not stocking out, set by `product_mix` |
| `demand_lead_time` | number | `366.0` | Expected demand while waiting for a new order to arrive |
| `safety_stock_fixed_leadtime` | number | `237.7` | Buffer stock needed if only demand varies (lead time assumed fixed) |
| `reorder_point_fixed_leadtime` | number | `603.7` | Stock level that should trigger a reorder, fixed-lead-time model |
| `safety_stock_variable_leadtime` | number | `258.0` | Buffer stock needed once lead-time uncertainty is included too |
| `reorder_point_variable_leadtime` | number | `624.0` | Stock level that should trigger a reorder, variable-lead-time model (recommended) |
| `safety_stock_uplift_pct` | number, % | `8.5` | How much more safety stock the variable-lead-time model requires vs. the fixed one. `NaN` for products with `sd = 0` |
| `safety_stock_investment` | number, currency | `2692.31` | `safety_stock_variable_leadtime × avg_unit_price` — money tied up in buffer stock. Output is ranked by this column |
| `annual_demand` | number | `11132.5` | `average × 365` — demand annualized from the analysis window |
| `eoq_units` | number | `730.4` | Economic order quantity — the order size that minimizes ordering + holding cost |
| `eoq_practical_units` | number | `428.2` | `eoq_units` rounded to the nearest practical order cycle (power-of-two weeks) |
| `eoq_order_cycle_weeks` | number | `3.4` | How often you'd order, in weeks, if ordering `eoq_units` each time |
| `annual_ordering_cost` | number, currency | `762.1` | Yearly cost of placing orders, at `eoq_units` |
| `annual_holding_cost` | number, currency | `762.1` | Yearly cost of holding inventory, at `eoq_units` (equal to ordering cost at the true EOQ, by construction) |
| `annual_logistics_cost` | number, currency | `117,685.5` | `annual_ordering_cost + annual_holding_cost + avg_unit_price × annual_demand` — full annual cost of this product at EOQ, purchase cost included |

## Notes

- One row = one product `Description` after cleaning (duplicates, cancelled
  orders, non-product line items like postage, and non-positive
  quantity/price rows are removed before this table is built — see
  `clean_transactions()` in `src/inventory_planning.py`).
- All monetary columns are in whatever currency `Price` was recorded in in
  the source file (GBP for the UCI Online Retail dataset this pipeline was
  built against).
- Use `reorder_point_variable_leadtime` for actual reorder decisions — it's
  the more realistic model. `reorder_point_fixed_leadtime` is kept mainly
  for comparison (see `safety_stock_uplift_pct`).
- The `eoq_*` and `annual_*` columns use `ordering_cost_per_order` and
  `holding_rate` from `Config` — **these are placeholder values**, not
  derived from the transaction data (the data has no record of what it
  costs you to place an order or carry inventory). Replace them with real
  figures in `src/inventory_planning.py` before using `eoq_units` or
  `annual_logistics_cost` for actual purchasing decisions.
