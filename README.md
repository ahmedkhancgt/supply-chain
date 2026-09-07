# supply-chain

Supply Chain repository

## Data source: `data/Data.xlsx`

Every script in this repo reads from `Config.data_path`
(`src/inventory_planning.py`), which points at `data/Data.xlsx` —
140,000 transactions across 41 countries. Most scripts analyze one
country at a time, set via `Config.country`; point it at any country
present in the file, or set it to `None` to analyze the full unfiltered
dataset instead. The examples and figures throughout this README (row
counts, invoice counts, etc.) all come from a single-country run using
`Config`'s current default — re-run against whichever country you set
to see your own numbers.

Data.xlsx carries real per-transaction data for several assumptions that
would otherwise be flat placeholder constants: `lead_time_days`,
`lead_time_sd_days`, `ordering_cost_per_order`, `holding_rate`, and `Cost`
(a real per-unit cost, alongside the selling `Price`).
`inventory_planning.extract_supply_parameters()` averages each of these
per SKU and merges them into the reorder-point/EOQ pipeline;
`advanced_analytics.resolve_unit_costs()` does the same for `Cost`. Each
column falls back **independently** to a `Config` placeholder (or
`COST_MARGIN * price` for cost) if it's ever missing from a source — so
the pipeline degrades gracefully field-by-field rather than requiring
every column to be present at once. `SALVAGE_RATE` and `PENALTY_RATE` in
`advanced_analytics.py` remain flat placeholders regardless — Data.xlsx
has no equivalent columns for either.

`Data.xlsx` also carries a `Trade_Area_ID` column — a trade-area code
1:1 with `Country` (41 codes for 41 countries), used by
`trade_area_modelling.py`.

`market_basket_analysis.py`'s `MIN_SUPPORT` (0.006) was tuned directly
against this data's default single-country scope (634 invoices, 1,250
products) rather than reused from the source notebook's default —
re-check this constant if the data source or country scope changes,
since it isn't derivable from anything else in the file the way the
cost/lead-time columns are.

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

By default it reads `data/Data.xlsx`, filtered to `Config.country`'s
default value (see "Data source" above). To point it at a different file
or country, edit the `Config` defaults at the top of
`src/inventory_planning.py` (`data_path`, `country`,
`analysis_window_months`).

`lead_time_days`, `lead_time_sd_days`, `ordering_cost_per_order`, and
`holding_rate` on `Config` are **fallback values only** — real per-SKU
data from the source file is used instead whenever it has the matching
column (`extract_supply_parameters()`), which `Data.xlsx` does for all
four. Each falls back independently, one field at a time, for any
SKU/source missing its column.

### Output

Written to `output/` (tracked in git so the latest run's results are
browsable in the repo):

- `reorder_recommendations.csv` / `inventory_report.xlsx` — per-product
  reorder point and safety stock under a fixed lead time and under an
  uncertain lead time, plus economic order quantity (EOQ), ranked by
  safety-stock investment (units x unit cost).
- `safety_stock_vs_variability.png` — safety stock vs. demand variability,
  colored by service level.
- `product_mix_distribution.png` — count of SKUs per ABC class.

For a quick-reference table of every output column, see
[`docs/SKUs.md`](docs/SKUs.md). For the full explanation of the formulas
behind them (with worked examples), see
[`docs/COLUMN_DEFINITIONS.md`](docs/COLUMN_DEFINITIONS.md). For what
every metric across the whole repo means in business terms — and the
decision it's meant to drive — see
[`docs/BUSINESS_GUIDE.md`](docs/BUSINESS_GUIDE.md).

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
names, kept as-is here since they're correct for this purpose, just
superseded. They also share a minor library bug: `Item_fill_rate`'s
denominator drops the last simulated period's demand, slightly inflating
the reported fill rate — worth knowing if you lean on that number.

**A note on what "daily demand" means here**: the main pipeline's
`average` column is the mean demand on days a product *actually sold* —
correct for its formulas, but not the same thing as a true daily average.
Several of the top SKUs by safety-stock investment sold on only 1-2 days
across the whole analysis window, so `daily_series()` in this script
computes its own zero-filled calendar-day mean/sd for the simulation
instead of reusing the pipeline's `average`/`sd`.

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

Adapted from four uploaded scripts, fixing several bugs found by actually
running them:

- `.dt.week` was removed in pandas ≥2.0 and crashed immediately —
  replaced with an ISO week key.
- The ADI day-gap calculation parsed a `Timedelta`'s string
  representation, which no longer matches pandas' current format and
  silently produced all-`NaN` results — replaced with `.dt.days`.
- `single_product_optimization`'s `cost` argument was passed
  positionally and landed in the wrong parameter — now always passed as
  an explicit keyword.
- One near-constant-price SKU sent the price-optimization fit into a
  multi-minute non-converging loop instead of failing fast — candidates
  are now pre-filtered by minimum price spread, with a timeout as backup.
- `MPN_singleperiod` returned `NaN` for any SKU with exactly zero demand
  variance — folded into the same demand-based placeholder already used
  for the one-year-of-history case.
- `single_product_optimization`'s price fields come back as pre-formatted
  sentences, not numbers — parsed out with a small regex helper instead
  of writing the sentence into a CSV column.

Unit cost for all three techniques comes from `resolve_unit_costs()`: a
real per-SKU `Cost` column when the source has one, or `COST_MARGIN *
price` otherwise. `SALVAGE_RATE` and `PENALTY_RATE` remain flat
placeholders in the same category as `inventory_planning.Config`'s
`ordering_cost_per_order`/`holding_rate` — not in the transaction data,
defaulted to match what the original scripts assumed.

**Why so few SKUs get a price elasticity or optimization result**: most
SKUs in the default scope barely change price at all over the history —
of 1,250 SKUs, only 6 had enough weeks of real price variation for
`compute_price_elasticity`, and only 5 (the top sellers among those) get
the full `single_product_optimization` treatment. This mirrors the
demand-sparsity finding from the policy backtest above — the data
supports fewer of these advanced techniques than the source scripts
assumed.

## Customer lifetime value segmentation

`src/customer_ltv_segmentation.py` computes RFM (recency, frequency,
monetary) scores per customer, clusters them into Low/Mid/High lifetime
value segments, and trains a classifier to predict segment from RFM
behavior. Adapted from two uploaded scripts that both assumed an
already-computed RFM file this repo doesn't have, so `compute_rfm()`
reconstructs it directly from the same cleaned transaction data
`inventory_planning.py` already loads.

```bash
python3 src/customer_ltv_segmentation.py
```

Writes `customer_rfm_segments.csv`, `ltv_segment_confusion.csv`,
`ltv_outlier_removal.png`, `ltv_segment_means.png`, and
`ltv_feature_importance.png` to `output/`.

Real bugs fixed rather than carried over:

- A guaranteed crash — a variable was referenced one line before it was
  defined.
- An RFM scoring inversion applied to all three columns instead of just
  recency, which is the only one that needs its raw order reversed.
- The consequential one: KMeans cluster IDs aren't guaranteed to sort by
  value, but the originals hardcoded `0=Low`, `1=Mid`, `2=High` anyway —
  verified this mislabels customers on an unlucky seed. Fixed by ranking
  clusters by their actual mean LTV before labeling.
- No `random_state` anywhere, so results didn't reproduce run to run; a
  pandas `GroupBy` tuple-column-selection that raises on current pandas;
  and no train/test split before evaluation, which overstated accuracy.

**A caveat worth knowing, not a bug**: `monetary` (an RFM feature the
classifier trains on) is the same value as `ltv` (what `KMeans` actually
clustered on) — confirmed by running this, where the winning model's
feature importance came out `monetary: 1.0`, everything else `0.0`. The
classifier isn't learning a genuine behavioral pattern so much as
recovering its own label through a renamed copy of it. Kept as-is to
match the original scripts' feature set, but reported here rather than
silently presenting the resulting ~100% accuracy as a clean result.

## Cross-country product mix and supplier segmentation

`src/supplier_segmentation.py` covers two analyses that operate across
the whole business rather than one country's demand, so — unlike the
other scripts — it loads every country in `data/Data.xlsx` regardless of
`Config.country`:

1. **Cross-country product mix** (`supplier_country_product_mix.csv`,
   `supplier_country_product_mix.png`) — the same ABC (volume x revenue)
   classification `inventory_planning.classify_products()` computes for
   one country, run independently per country via
   `inventorize3.productmix_storelevel` — a SKU that's a top seller in
   one country can be a long-tail item in another.
2. **Supplier risk/value segmentation** (`supplier_risk_value_segmentation.csv`,
   `supplier_risk_value_matrix.png`) — a Kraljic-matrix-style
   classification (Strategic / Leverage / Critical / Routine) per SKU,
   from its total procurement spend (`Cost x Quantity`, summed) and a
   composite risk score (`availability + no_suppliers + standard +
   price_fluctuation`, columns Data.xlsx carries per transaction).

```bash
python3 src/supplier_segmentation.py
```

Adapted from an uploaded script that read two files this repo doesn't
have — rebuilt on the cleaned transaction data `inventory_planning.py`
loads, since Data.xlsx already carries the risk-factor and cost columns
the original needed a second file for. The single-country ABC analysis
at the top of the original duplicates `classify_products()` and isn't
reimplemented here.

Real issues fixed rather than carried over:

- The original's `dropna()` removed any row with a null in *any* column
  (e.g. a missing Customer ID for a guest checkout) and never filtered
  cancelled invoices — both handled correctly by `clean_transactions()`.
- A row-by-row category assignment loop that only worked by luck of an
  untouched index — replaced with a vectorized `np.select`.
- Hardcoded value/risk thresholds (`value >= 3,000,000`) sized to a file
  this repo doesn't have — against this data, procurement spend never
  gets close, so every SKU would land in the same two quadrants. Fixed
  with the standard Kraljic-matrix approach: split at the median of each
  axis, computed from the real data.
- An ambiguous `value = price * Quantity` — resolved to `Cost x Quantity`
  specifically, since this is a procurement-risk matrix (what you pay
  suppliers), not a selling-side one.

## Market basket analysis

`src/market_basket_analysis.py` mines which products get bought together
(via `mlxtend`'s Apriori algorithm) and cross-references the resulting
rules against genuinely slow-moving products, to surface potential
cross-sell pairings for stock that isn't selling on its own. Adapted from
an uploaded notebook that assumed a pre-existing cleaned CSV this repo
doesn't have — rebuilt on the same cleaned transaction data
`inventory_planning.py` loads.

```bash
python3 src/market_basket_analysis.py
```

Writes `basket_association_rules.csv`, `basket_slow_mover_cross_sell.csv`,
`basket_slow_movers.csv`, and three charts (`basket_order_size.png`,
`basket_top_sellers.png`, `basket_rules_scatter.png`) to `output/`.

Real bugs fixed rather than carried over:

- **"slow_moving" was actually the second-fastest-moving octile.**
  `pd.qcut` labels bins ascending (0 = lowest quantity), and the notebook
  filtered the wrong bin — actually mid-to-high-volume products. A step
  meant to find cross-sell opportunities for overstocked slow movers was
  targeting already-popular products instead. Fixed to the correct bin.
- **Multi-item association rules were silently truncated to one item.**
  Indexing into `mlxtend`'s result set kept only the first item of any
  multi-item rule, with no sign anything was dropped. Fixed by joining
  every item into one readable string.
- `association_rules` was also called without `min_threshold`, silently
  taking `mlxtend`'s generic default rather than the analytically
  meaningful cutoff for lift specifically (only `> 1.0` is a positive
  association) — made explicit here as `LIFT_MIN_THRESHOLD`.

**Real finding, not a bug**: at `MIN_SUPPORT`, zero rules involve a
slow-moving product on either side, in this dataset. That's expected —
a product has to appear in a minimum share of invoices to be included in
any rule at all, and slow movers are by definition too rare to clear
that bar. Finding real cross-sell pairings for them would need a support
threshold scoped specifically to those products, which this script
doesn't attempt.

## Weekly retail KPIs: conversion rate, ATV, UPT, ASP

`src/retail_kpi_metrics.py` computes four weekly (ISO year+week) metrics
for every country in `data/Data.xlsx`, plus a combined "All Countries"
total:

- **ATV** (average transaction value) — mean revenue per invoice.
- **UPT** (units per transaction) — mean units per invoice.
- **ASP** (average selling price) — `ATV / UPT`.
- **Conversion rate** — invoices ÷ website visitors, from `data/footfall.xlsx`.

```bash
python3 src/retail_kpi_metrics.py
```

Writes `retail_kpi_metrics.csv` to `output/`.

Adapted from an uploaded script that read a cleaned CSV this repo
doesn't have and computed every metric for the UK only. Rebuilt on the
same cleaned transaction data `inventory_planning.py` loads, computing
every metric for **every** country rather than one, plus an "All
Countries" combined row per week.

Issues fixed rather than carried over: the original joined two
independently-resampled weekly series on raw calendar dates, which is
fragile — two series resampled from different starting dates can anchor
"week" boundaries on different days and silently fail to join even when
their data genuinely overlaps. Fixed by keying both sides on
`(iso_year, iso_week)` instead. A convoluted invoice count was also
simplified to a single `nunique()`.

**A real data mismatch, handled explicitly rather than silently**:
`data/footfall.xlsx` covers 2016-2020, while the transaction data covers
2009-2011 — these date ranges don't overlap, so a real-calendar-date join
produces zero matched weeks. Since footfall is needed to compute
`conversion_rate` at all, `align_footfall_to_period()` shifts every
footfall date back by a whole number of weeks so it brackets the
transaction period — a relabeling, not new data: the same weekly values
in the same order, just moved onto different calendar dates. Treat
`conversion_rate` in the output as an illustrative estimate, not a
verified historical metric; the output's `footfall_aligned` column flags
this. Set `KPIConfig.align_footfall_to_data=False` to see the real,
unmatched (`NaN`-everywhere) join instead. `footfall.xlsx` also carries
no per-country breakdown, so conversion rate is only ever computed at
the "All Countries" grain.

## Assortment planning

`src/assortment_planning.py` answers: how much catalog space should the
top-selling categories get to maximize gross profit? It selects the top
3 categories by historical revenue, uses each category's weekly share of
active SKUs (among those top categories) as a proxy for assortment
breadth — `Data.xlsx` has no physical shelf-space field — fits a
log-log cross-category elasticity model (so one category's space can
help or hurt another's sales, not just its own), and optimizes the space
split (each category bounded 10–70%, summing to 100%) to maximize
predicted weekly gross profit.

```bash
python3 src/assortment_planning.py
```

Writes `assortment_planning_results.xlsx` (Category Summary, Weekly
Space, Weekly Units, Regression, Optimization sheets) and
`assortment_planning_allocation.png` to `output/`.

Runs against **every country combined**, not one — assortment/shelf-space
allocation is a catalog-wide decision, and the original script never
filtered by country either.

One real issue fixed: the original read `Data.xlsx` directly with its
own narrower cleaning instead of this repo's `clean_transactions()`,
which additionally excludes non-product line items (e.g. a "Carriage"
shipping-charge row that was being counted as a product sale in every
downstream aggregate).

**Verified against `Data.xlsx`**: top 3 categories by revenue are
General Merchandise, Storage & Organization, and Home Decor. Regression
R² came out modest (0.15, 0.03, and 0.31 respectively) — assortment
breadth alone explains only a limited part of demand, and R² should be
reviewed before trusting the recommendation. With that caveat, the
optimizer recommends shifting space from Storage & Organization (28.5% →
22.0%) to Home Decor (28.8% → 35.6%), for a modelled **+21.8% weekly
gross profit** uplift. This is a modelled scenario for evaluation, not
an automatic buying decision — a production version would still need
seasonality, promotions, stock-outs, supplier risk, and other real-world
factors this model doesn't capture.

## Trade-area modelling (Huff gravity model)

`src/trade_area_modelling.py` answers: given several competing stores
and a set of markets ("trade areas"), which store is each market's
demand likely to gravitate to, and how much should each store expect to
capture? It implements the classic Huff gravity model: each store's
"pull" on a trade area is its attractiveness divided by distance
squared, and each trade area's total (synthetic) market potential splits
across stores in proportion to each store's share of that pull.

```bash
python3 src/trade_area_modelling.py
```

Writes `trade_area_modelling_results.xlsx` (Executive_Summary,
Huff_Detail, plus the three synthetic input sheets) and
`trade_area_expected_capture.png` to `output/`.

Uses `data/Data.xlsx`'s `Trade_Area_ID` column joined against
`data/Trade_Area_Synthetic_Inputs.xlsx` (uploaded separately:
`Trade_Area_Census` — synthetic households/expenditure/market-potential
per trade area; `Store_Attributes` — 3 competing stores' physical/access
characteristics; `Distance_Matrix` — each trade area's distance to each
store).

Issues fixed rather than carried over: the original read `Data.xlsx` raw
with no cleaning, so "actual" revenue/invoices per trade area now come
from `clean_transactions()` instead — this changes the numbers for the 4
trade areas with a shipping-charge row, all by under 1.5% of that trade
area's revenue. The original also joined `Distance_Matrix` to
`Trade_Area_Census` positionally rather than on a key — it happened to
produce the right answer here because the two sheets are already in the
same order, but a reordered file would have silently misassigned every
trade area's distances. Fixed by merging explicitly on
`(Trade_Area_ID, Country)`.

**Verified against the uploaded reference output**: reproduces it almost
exactly (a sub-0.0001% gap traced to a rounding-precision difference,
not a modeling error). Total synthetic market potential across all 41
trade areas is ~132.0 billion; expected capture splits ~86.1B / 8.3B /
37.6B across the three stores. Store 3 has the highest attractiveness
score, but Store 1 wins by far the largest total capture because it's
dramatically closer to the single biggest market (the UK) — proximity
outweighs Store 3's attractiveness edge everywhere else.

## Hybrid 12-week SKU forecasting

`src/hybrid_forecasting.py` forecasts the next 12 weeks of demand per
SKU by pitting two different forecasting approaches against each
other — a classical statistical/intermittent-demand suite, and a
machine-learning panel model — and using whichever one actually
backtests better for that specific SKU, rather than picking one
approach for the whole catalog.

```bash
python3 src/hybrid_forecasting.py
```

Writes `hybrid_forecast_sku_comparison.csv` (one row per SKU: demand
classification, both sides' backtest metrics, the winning source/model,
and the resulting 12-week forecast), `hybrid_forecast_all_candidate_metrics.csv`
(every method tried, not just the winner), `hybrid_forecast_12w_detail.csv`
(per SKU per future week), and `hybrid_forecast_overview.png` to `output/`.

Adapted from an uploaded PyCaret-based script and reference output from
a prior run of it. Two substitutions, both already used by that
reference run itself (it noted PyCaret wasn't installable in its own
runtime either):

- **No PyCaret.** Fits `HistGradientBoostingRegressor`,
  `RandomForestRegressor`, and `Ridge` directly instead of pulling in
  `pycaret[full]`'s large dependency tree — backtested and picked by MAE
  the same way the original's PyCaret-wrapped shortlist was.
- **No separate "Version 1" statistical script.** The original expects
  pre-generated forecast files from a companion script this repo doesn't
  have. Rebuilt directly: Naive, moving averages, simple exponential
  smoothing, seasonal naive, and Croston's method (classic, SBA-corrected,
  and TSB) — implemented from their standard formulas.

One real issue fixed: the original measured every SKU's history against
the full 106-week panel regardless of when that SKU actually started
selling. Checked directly: 502 of 3,080 SKUs (16%) don't appear until
more than a year into the panel, so crediting them with a full-panel
history materially overstates how lumpy their demand looks. Fixed by
measuring each SKU's history from its own first sale week onward — this
is also why this run's demand-pattern mix differs from the uploaded
reference's (more SKUs classified Smooth/Erratic once new SKUs aren't
miscounted as long-dormant ones).

**Verified against `data/Data.xlsx`** (all countries, 3,080 SKUs, keyed
by `StockCode` — the finer-grained identifier here, unlike the rest of
this repo's `Description`): the statistical side won for 70% of SKUs and
the ML side for 30%, closely matching the uploaded reference's own split
and median error despite using different underlying ML algorithms.
Total hybrid 12-week forecast: ~324,000 units (~$659,000 revenue).
