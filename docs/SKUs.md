# SKU Output Data Dictionary

Quick-reference table for every column in `output/reorder_recommendations.csv`
and the "Reorder Recommendations" sheet of `output/inventory_report.xlsx`
(one row per product/SKU). For formulas and worked examples, see
[`COLUMN_DEFINITIONS.md`](COLUMN_DEFINITIONS.md). Example values below are
one real row (**Regency Cakestand Tier**) from a run against `data/Data.xlsx`,
filtered to `Config`'s default single-country scope.

| Column | Type | Example | What it is |
|---|---|---|---|
| `Description` | text | `Regency Cakestand Tier` | Product name (the SKU identifier used throughout this pipeline) |
| `average` | number | `28.5` | Average units sold per day, over the analysis window |
| `sd` | number | `38.89` | Standard deviation of daily units sold — demand volatility |
| `total_sales` | number | `3477` | Total units sold across the whole analysis window |
| `total_revenue` | number | `27,449.55` | Total revenue across the whole analysis window |
| `avg_unit_price` | number | `7.90` | `total_revenue / total_sales` — effective average selling price |
| `product_mix` | text (9 values) | `A_A` | ABC class: `<volume class>_<revenue class>`, each `A`/`B`/`C` |
| `service_level` | number, 0–1 | `0.95` | Target probability of not stocking out, set by `product_mix` |
| `lead_time_days` | number | `24.0` | Average per-SKU supplier lead time — real data from the source file when it has a `lead_time_days` column, else a flat `Config` fallback |
| `lead_time_sd_days` | number | `6.5` | Standard deviation of that SKU's lead time — same real-data-or-fallback rule |
| `ordering_cost_per_order` | number, currency | `62.08` | Cost to place one order for that SKU — same rule |
| `holding_rate` | number, fraction | `0.268` | Annual cost of holding one unit, as a fraction of its cost — same rule |
| `unit_cost` | number, currency | `7.89` | What this SKU costs to acquire — a real per-SKU `Cost` column when the source has one, else `avg_unit_price` as a fallback |
| `unit_cost_is_real` | boolean | `True` | Whether `unit_cost` came from a real `Cost` column (`True`) or the `avg_unit_price` fallback (`False`) |
| `demand_lead_time` | number | `684.0` | Expected demand while waiting for a new order to arrive |
| `safety_stock_fixed_leadtime` | number | `313.39` | Buffer stock needed if only demand varies (lead time assumed fixed) |
| `reorder_point_fixed_leadtime` | number | `997.39` | Stock level that should trigger a reorder, fixed-lead-time model |
| `safety_stock_variable_leadtime` | number | `437.10` | Buffer stock needed once lead-time uncertainty is included too |
| `reorder_point_variable_leadtime` | number | `1121.10` | Stock level that should trigger a reorder, variable-lead-time model (recommended) |
| `safety_stock_uplift_pct` | number, % | `39.48` | How much more safety stock the variable-lead-time model requires vs. the fixed one. `NaN` for products with `sd = 0` |
| `safety_stock_investment` | number, currency | `3449.48` | `safety_stock_variable_leadtime × unit_cost` — money tied up in buffer stock. Output is ranked by this column |
| `annual_demand` | number | `10,402.5` | `average × 365` — demand annualized from the analysis window |
| `eoq_units` | number | `781.5` | Economic order quantity — the order size that minimizes ordering + holding cost |
| `eoq_practical_units` | number | `400.1` | `eoq_units` rounded to the nearest practical order cycle (power-of-two weeks) |
| `eoq_order_cycle_weeks` | number | `3.9` | How often you'd order, in weeks, if ordering `eoq_units` each time |
| `annual_ordering_cost` | number, currency | `826.4` | Yearly cost of placing orders, at `eoq_units` |
| `annual_holding_cost` | number, currency | `826.4` | Yearly cost of holding inventory, at `eoq_units` (equal to ordering cost at the true EOQ, by construction) |
| `annual_logistics_cost` | number, currency | `83,746.0` | `annual_ordering_cost + annual_holding_cost + unit_cost × annual_demand` — full annual cost of this product at EOQ, purchase cost included |

## Notes

- One row = one product `Description` after cleaning (duplicates, cancelled
  orders, non-product line items like postage, and non-positive
  quantity/price rows are removed before this table is built — see
  `clean_transactions()` in `src/inventory_planning.py`).
- All monetary columns are in whatever currency `Price`/`Cost` were
  recorded in in the source file.
- Use `reorder_point_variable_leadtime` for actual reorder decisions — it's
  the more realistic model. `reorder_point_fixed_leadtime` is kept mainly
  for comparison (see `safety_stock_uplift_pct`).
- `lead_time_days`, `lead_time_sd_days`, `ordering_cost_per_order`,
  `holding_rate`, and `unit_cost` are **real per-SKU data whenever the
  source file has the matching column** (`extract_supply_parameters()` in
  `src/inventory_planning.py`), each falling back independently to a flat
  `Config` placeholder only for a SKU/source missing that one column. If
  you're running against a source missing some of these, replace the
  relevant `Config` placeholders with real figures before trusting
  `eoq_units` or `annual_logistics_cost` for actual purchasing decisions.
