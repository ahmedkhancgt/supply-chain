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

Written to `output/` (tracked in git so the latest run's results are
browsable in the repo):

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

## Policy backtest (top-N SKUs)

`src/policy_simulation.py` runs the main pipeline, takes the top `TOP_N`
SKUs by `safety_stock_investment`, and replays each one's real daily
demand history through 5 inventory review policies (`inventorize`'s
`sim_min_Q_normal`, `sim_base_normal`, `sim_min_max_normal`,
`Periodic_review_normal`, `Hibrid_normal`) using the reorder point and EOQ
already computed for that SKU as the policy parameters. Unlike the static
formulas, this measures what would have *actually* happened (fill rate,
lost sales, average inventory carried) day by day.

```bash
python3 src/policy_simulation.py
```

Writes `policy_simulation_top5.csv`, `policy_simulation_fill_rate.png`,
and `policy_simulation_inventory_level.png` to `output/`.

These functions are flagged deprecated by `inventorize` in favour of newer
names (`sim_Q_max`, `sim_base_stock_policy`, `sim_min_max`,
`periodic_policy`) — kept as-is here since they're correct for this
purpose, just superseded. They also share a minor bug: `Item_fill_rate`'s
denominator drops the last simulated period's demand, slightly inflating
the reported fill rate — not significant enough to justify reimplementing
the simulation loop for a 5-SKU backtest, but worth knowing if you lean on
that number.

**A note on what "daily demand" means here**: the main pipeline's
`average` column is the mean demand on days a product *actually sold* —
correct for its formulas, but not the same thing as a true daily average.
Several of the top SKUs by safety-stock investment turned out to have sold
on only 1-2 days across the whole analysis window, so `daily_series()` in
this script computes its own zero-filled calendar-day mean/sd for the
simulation rather than reusing the pipeline's `average`/`sd`.

## Advanced analytics: demand pattern, pricing, single-period ordering

`src/advanced_analytics.py` combines three more techniques into one
pipeline, reusing `inventory_planning.py`'s cleaning and ABC classification
rather than duplicating it. Unlike the other two scripts, it uses the
**full** cleaned transaction history (not the 4-month window) since these
techniques benefit from more history, not a recent snapshot.

```bash
python3 src/advanced_analytics.py
```

1. **Demand-pattern classification** (`demand_pattern_classification.csv`/`.png`)
   — the standard ADI/CV² method (Syntetos-Boylan-Croston): buckets every
   product into smooth, intermittent, erratic, or lumpy demand.
2. **Price elasticity** (`price_elasticity.csv`) — `inventorize.linear_elasticity`
   per SKU, for SKUs with at least `MIN_WEEKS_FOR_ELASTICITY` weeks of
   price variation (most don't — see below).
3. **Price optimization** (`price_optimization_top5.csv`,
   `price_optimization_example.png`) — `inventorize.single_product_optimization`
   (fits linear/logit/poly demand curves) for the top 5 eligible SKUs by
   volume, comparing revenue-maximizing vs. profit-maximizing price.
4. **Single-period ("newsvendor") ordering** (`single_period_ordering.csv`)
   — `inventorize.MPN_singleperiod` per SKU, using yearly demand totals.

This was adapted from four uploaded scripts (`product_segmentation.py`,
`Behaviour_Pricing.py`, `Seasonal_Inventory.py`, and a small notebook),
fixing several bugs found by actually running them rather than carrying
them over:

- **`.dt.week`** (`Behaviour_Pricing.py`) was removed in pandas ≥2.0 and
  crashes immediately — replaced with an ISO week key via
  `.dt.strftime('%G-W%V')`.
- **ADI's day-gap calculation** (`product_segmentation.py`) converted a
  `Timedelta` to a day count by string-replacing
  `"days 00:00:00.000000000"` out of its text representation — this no
  longer matches pandas' current `Timedelta` formatting and silently
  produced all-`NaN` results. Replaced with `.dt.days`.
- **`single_product_optimization`'s `cost` parameter** (`Behaviour_Pricing.py`)
  was passed positionally, where it actually landed in the `degree`
  parameter instead (`cost` is the function's 6th argument). Verified this
  crashes for a float cost and silently zeroes out cost for an int one.
  Always called here with `cost=` as an explicit keyword.
- **A non-converging fit, not a clean error**: one candidate SKU had an
  almost perfectly constant price (`1.6499999999999997`–`1.65`, floating-point
  noise only) — fitting a logit curve to it sent `scipy`'s optimizer into a
  multi-minute non-converging loop instead of failing fast. Candidates are
  now pre-filtered by `MIN_RELATIVE_PRICE_SPREAD`, with a
  `PER_SKU_OPTIMIZATION_TIMEOUT_S` timeout as a second line of defense.
- **`MPN_singleperiod` returns `NaN`** for a SKU with exactly zero demand
  variance (both years sold identically) the same way it does for missing
  variance — this produced 113 all-`NaN` output rows before being folded
  into the same 10%-of-demand placeholder already used for the
  one-year-of-history case.
- `single_product_optimization`'s `current_price`/`optimum_linear`/`optimum_logit`
  fields are pre-formatted sentences (e.g. `"optimum logit revenue price is
  [18.19]for Mango"`), not plain numbers — parsed back out with a small
  regex helper instead of writing the sentence into a CSV column.

`COST_MARGIN`, `SALVAGE_RATE`, and `PENALTY_RATE` are placeholders in the
same category as `inventory_planning.Config`'s `ordering_cost_per_order`/
`holding_rate` — not in the transaction data, defaulted to match what the
original scripts assumed (see the comments at the top of the file).

**Why so few SKUs get a price elasticity or optimization result**: most
Germany SKUs barely change price at all over the two-year history — of
2,402 SKUs, only 50 had enough weeks of real price variation for
`compute_price_elasticity`, and only 5 (the top sellers among those 50)
get the full `single_product_optimization` treatment. This mirrors the
demand-sparsity finding from the policy backtest above — the data
supports fewer of these advanced techniques than the source scripts
assumed.
