# supply-chain

Supply Chain repository

## Data source: `data/Data.xlsx`

Every script in this repo reads from `Config.data_path`
(`src/inventory_planning.py`), which points at `data/Data.xlsx` —
140,000 transactions across 40 countries. `Config.country` defaults to
`"Germany"`, analyzing a 2,867-row slice by default; point `Config.country`
at any of the other 39 countries in the file (or set it to `None` for the
full unfiltered dataset) to analyze a different scope.

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
1:1 with `Country` (e.g. `TA015` = Germany, `TA039` = United Kingdom, 41
codes for 41 countries). It's a straight relabeling of `Country`, not
independent information, and no script in this repo consumes it yet.

`market_basket_analysis.py`'s `MIN_SUPPORT` (0.006) was tuned directly
against Data.xlsx's Germany slice (634 invoices, 1,250 products) —
checked directly (`0.02` → 0 rules, `0.006` → 8, `0.004` → 26) before
landing on `0.006`. Re-check this constant if the data source changes;
it isn't derivable from anything else in the file the way the cost/lead-time
columns are.

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

By default it reads `data/Data.xlsx`, filtered to `country="Germany"` (see
"Data source" above). To point it at a different file or country, edit the
`Config` defaults at the top of `src/inventory_planning.py` (`data_path`,
`country`, `analysis_window_months`).

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

Unit cost for all three techniques comes from `resolve_unit_costs()`: a
real per-SKU `Cost` column when the source has one (`Data.xlsx` does), or
`COST_MARGIN * price` otherwise (see "Data source" above). `SALVAGE_RATE`
and `PENALTY_RATE` remain flat placeholders in the same category as
`inventory_planning.Config`'s `ordering_cost_per_order`/`holding_rate` —
not in the transaction data, defaulted to match what the original scripts
assumed (see the comments at the top of the file).

**Why so few SKUs get a price elasticity or optimization result**: most
Germany SKUs barely change price at all over the history — of 1,250 SKUs
in Data.xlsx's Germany slice, only 6 had enough weeks of real price
variation for `compute_price_elasticity`, and only 5 (the top sellers
among those) get the full `single_product_optimization` treatment. This
mirrors the demand-sparsity finding from the policy backtest above — the
data supports fewer of these advanced techniques than the source scripts
assumed.

## Customer lifetime value segmentation

`src/customer_ltv_segmentation.py` computes RFM (recency, frequency,
monetary) scores per customer, clusters them into Low/Mid/High lifetime
value segments, and trains a classifier to predict segment from RFM
behavior. Adapted from `cltv.py`/`cltv_assignment.py` (uploaded
separately) — two near-identical scripts that both assumed an
already-computed RFM file this repo doesn't have, so `compute_rfm()`
reconstructs it directly from the same cleaned transaction data
`inventory_planning.py` already loads.

```bash
python3 src/customer_ltv_segmentation.py
```

Writes `customer_rfm_segments.csv`, `ltv_segment_confusion.csv`,
`ltv_outlier_removal.png`, `ltv_segment_means.png`, and
`ltv_feature_importance.png` to `output/`.

Three real, verified bugs from the originals are fixed here rather than
carried over:

- **A guaranteed crash**: `len(ltv)-len(outliers_removed)` is called one
  line *before* `outliers_removed` is defined — `NameError` on any
  top-to-bottom run.
- **An RFM scoring inversion applied to the wrong columns**: both
  originals map `{'1':'3','3':'1','2':'2'}` onto recency, frequency,
  *and* monetary alike. That flip only makes sense for recency (low
  recency = best, so its raw tertile order needs reversing) — frequency
  and monetary already increase with customer value, so applying the
  same flip inverts a scale that didn't need it. Fixed by qcut-ing
  recency with descending labels and frequency/monetary with ascending
  labels directly, instead of qcut-then-flip.
- **The consequential one — KMeans cluster IDs assumed sorted by value**:
  nothing guarantees `KMeans(...).fit_predict()`'s cluster `0` has the
  lowest mean LTV. Verified empirically (5 reseeds of a synthetic
  3-cluster LTV distribution): the cluster-id-to-mean order came out
  already sorted in only 1 of 5 runs. The originals' hardcoded
  `{'0':'Low_ltv','1':'Mid_ltv','2':'High_ltv'}` would silently mislabel
  customers — e.g. calling your highest-spending cluster "Low_ltv" — on
  an unlucky seed, with nothing in the code to catch it. Fixed by ranking
  clusters by their actual mean LTV before labeling.

Also fixed: no `random_state` anywhere (`KMeans`, the CV splitters, the
searches) — results didn't reproduce run to run; and the final
`groupby(['Actual','Prediction'])['Actual','Prediction']` — tuple-style
column selection on a `GroupBy`, which raises
`ValueError: Cannot subset columns with a tuple with more than one
element` on current pandas — fixed to list-style selection. A train/test
split was also added before the final evaluation; the originals predicted
on the same data they'd fit on, which overstates real accuracy.

**A caveat worth knowing, not a bug**: `monetary` (an RFM feature the
classifier trains on) is the same value as `ltv` (what `KMeans` actually
clustered on) — confirmed in the Germany run, where the winning model's
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

Adapted from `ABC_SUPPLIER.py` (uploaded separately), which read
`online_retail2.csv` and a separate `supplier_data.csv` this repo
doesn't have — rebuilt on the same cleaned transaction data
`inventory_planning.py` loads, since Data.xlsx already carries the
risk-factor columns and `Cost` the original needed a second file for.
The single-country ABC/multi-criteria-ABC analysis at the top of the
original script duplicates `classify_products()` and isn't reimplemented
here.

Several real issues from the original are fixed rather than carried over:

- **`retail.dropna()` drops far more than intended** — it removes any
  row with a null in *any* column, not just ones that matter (e.g. a
  missing Customer ID for a guest checkout). Uses `clean_transactions()`
  instead, which only requires the columns that make a row a usable
  transaction. Also fixes the original's missing cancellation filter
  (invoices starting with `"C"`), which `clean_transactions()` already
  handles.
- **Row-by-row category assignment**:
  `for i in range(supplier.shape[0]): supplier.loc[i,'category'] = category(...)`
  is O(n) individual writes, and only works because `supplier` still has
  an untouched `0..n-1` `RangeIndex` — it would silently write to the
  wrong rows (or raise `KeyError`) the moment any filtering happened
  upstream. Replaced with a vectorized `np.select`.
- **Hardcoded value/risk thresholds sized to a file this repo doesn't
  have**: the original's quadrant function splits on `value >= 3,000,000`
  and `risk_index >= 1`. Checked directly against Data.xlsx: per-SKU
  procurement spend ranges $22-$7,500 (median $333) — nothing ever
  reaches 3,000,000, so every SKU would land in Critical or Routine and
  the matrix would never produce a Strategic or Leverage result. Fixed
  with the standard Kraljic-matrix approach instead: split at the
  *median* of each axis, computed from this data (verified: an even
  ~950/950/570/570 split across the four quadrants).
- **Ambiguous `value = price * Quantity`**: the original's generic
  `price` column could mean either the supplier's cost or the
  customer-facing selling price — Data.xlsx has both. Since this is a
  procurement-risk matrix (how much you pay suppliers, not what you
  resell for), `value` here is `Cost x Quantity`, not `Price x Quantity`
  (Revenue, already used for selling-side value elsewhere in this repo).

## Market basket analysis

`src/market_basket_analysis.py` mines which products get bought together
(via `mlxtend`'s Apriori algorithm) and cross-references the resulting
rules against genuinely slow-moving products, to surface potential
cross-sell pairings for stock that isn't selling on its own. Adapted from
`MarketBasketanalysis_1.ipynb` (uploaded separately), which assumed a
pre-existing `retail_clean.csv` this repo doesn't have — rebuilt on the
same cleaned Germany transaction data `inventory_planning.py` loads.

```bash
python3 src/market_basket_analysis.py
```

Writes `basket_association_rules.csv`, `basket_slow_mover_cross_sell.csv`,
`basket_slow_movers.csv`, and three charts (`basket_order_size.png`,
`basket_top_sellers.png`, `basket_rules_scatter.png`) to `output/`.

Two real bugs from the notebook are fixed here rather than carried over:

- **"slow_moving" was actually the second-fastest-moving octile.**
  `pd.qcut(total_quantity_sold, 8, labels=False)` labels bins ascending —
  0 is the lowest-quantity octile, 7 the highest — and the notebook
  filtered `cut==6`. Checked directly against this data: bin 6 covers
  products that sold 98–188 units total, solidly mid-to-high volume. A
  step meant to find cross-sell opportunities for overstocked slow movers
  was actually targeting already-popular products. Fixed to bin `0`.
- **Multi-item association rules were silently truncated to one item.**
  `rules["antecedents"].apply(lambda x: list(x)[0])` keeps only the first
  element of what `mlxtend` returns as a set — a real correctness bug
  regardless of dataset, since any rule with more than one antecedent or
  consequent item would show only part of the real rule (e.g. "buy A →
  buy C" when the actual rule was "buy A and B → buy C") with no visible
  sign anything was dropped. Fixed by joining every item into one
  readable string instead of indexing into the set.

`association_rules` was also called without `min_threshold`, silently
taking `mlxtend`'s generic default (0.8) rather than the analytically
meaningful cutoff for lift specifically (only lift `> 1.0` is a positive
association) — made explicit here as `LIFT_MIN_THRESHOLD`.

**Real finding, not a bug**: at `MIN_SUPPORT`, zero rules involve a
slow-moving product on either side, in this dataset (Data.xlsx's Germany
slice: 283 slow movers, bottom octile, 1–6 units sold total, against 8
rules total). That's expected, not a mistake in the code — a product has
to appear in a minimum share of invoices to be included in any rule at
all, and slow movers are by definition too rare to clear that bar.
Finding real cross-sell pairings for them would need a support threshold
scoped specifically to those products, not the same threshold used for
the catalog-wide rule mining above — the two questions ("what do people
buy together in general" vs. "what could I bundle with this specific
slow-moving item") need different statistical treatment, which this
script doesn't attempt.

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

Adapted from `section2.py` (uploaded separately), which read a
`retail_clean.csv` this repo doesn't have and computed every metric for
the UK only. Rebuilt on the same cleaned transaction data
`inventory_planning.py` loads, computing every metric for **every**
country rather than one, plus an "All Countries" combined row per week
(the direct generalization of the original's single UK series).

Two issues fixed rather than carried over:

- **Joining on raw resampled calendar dates.** The original computes two
  independently-`resample('W')`-d weekly series and merges them on the
  resulting `date` column — fragile, since two series resampled from
  different starting dates can anchor "week" boundaries on different
  days and silently fail to join even when their data genuinely
  overlaps, with nothing to explain why the result came back all `NaN`.
  Fixed by keying both sides on `(iso_year, iso_week)` instead.
- **A convoluted invoice count**:
  `groupby(['date','Invoice']).agg(n_invoices=('Invoice','count')).reset_index().groupby('date').agg(n_invoices=('Invoice','count'))`
  counts rows per `(date, Invoice)` group only to throw that count away
  and count the number of groups instead — equivalent to, and replaced
  with, a single `nunique()`.

**A real data mismatch, handled explicitly rather than silently**:
`data/footfall.xlsx` covers 2016-01-03 to 2020-01-26, while the
transaction data covers 2009-12-01 to 2011-12-09 — these date ranges
don't overlap at all, so a real-calendar-date join produces **zero**
matched weeks. Since footfall is needed to compute `conversion_rate` at
all, `align_footfall_to_period()` shifts every footfall date back by a
whole number of weeks (318, landing on 2009-11-29 to 2013-12-22) so it
brackets the transaction period — a relabeling, not new data: the same
213 weekly footfall values in the same order, just moved onto different
calendar dates. This gives a full 104/104 matched weeks and a populated
`conversion_rate`, but it's **this business's real footfall pattern laid
over 2009-2011, not actual historical footfall for those years** — no
such data exists. Treat `conversion_rate` in the output as an
illustrative estimate, not a verified historical metric; the output's
`footfall_aligned` column (and a `WARNING`-level log line on every run)
flags this. Set `KPIConfig.align_footfall_to_data=False` in
`src/retail_kpi_metrics.py` to see the real, unmatched (`NaN`-everywhere)
join instead. `footfall.xlsx` also carries no per-country breakdown
(unlike the original's UK-specific `footfall_uk.xlsx`), so conversion
rate is only ever computed at the "All Countries" grain — one
undifferentiated footfall number can't be allocated across countries.

## Assortment planning

`src/assortment_planning.py` answers: how much catalog space should the
top-selling categories get to maximize gross profit? It selects the top
3 categories by historical revenue, uses each category's weekly share of
active SKUs (among those top categories) as a proxy for assortment
breadth — `Data.xlsx` has no physical shelf-space field — fits a
log-log cross-category elasticity model (`log10(units sold) ~
sum of log10(each top category's space share)`, so one category's space
can help or hurt another's sales, not just its own), and optimizes the
space split (each category bounded 10–70%, summing to 100%) to maximize
predicted weekly gross profit.

```bash
python3 src/assortment_planning.py
```

Writes `assortment_planning_results.xlsx` (Category Summary, Weekly
Space, Weekly Units, Regression, Optimization sheets) and
`assortment_planning_allocation.png` to `output/`.

Runs against **every country combined**, not one — unlike the
inventory-planning pipeline, assortment/shelf-space allocation is a
catalog-wide decision, and the original script (adapted from
`Assortment_Planning_Data.py`, uploaded separately, already written
against `Data.xlsx`'s schema) never filtered by country either.

One real issue fixed: the original read `Data.xlsx` directly with
`pd.read_excel()` and its own narrower cleaning (drop nulls in a few
columns, positive `Quantity`/`Price`, non-negative `Cost`) instead of
this repo's `clean_transactions()`. Checked directly: `clean_transactions()`
removes 47 rows with `StockCode == "C2"` ("Carriage" — a shipping charge,
not a product) that the original's cleaning let through under
`category == "General Merchandise"`. Those rows would have counted a
shipping fee as a "General Merchandise" sale in every downstream
aggregate feeding the model (revenue, units, gross profit, active-SKU
share). Rebuilt on `load_transactions()`/`clean_transactions()` instead.

**Verified against `Data.xlsx`**: top 3 categories by revenue are
General Merchandise, Storage & Organization, and Home Decor; all 104
weeks in the data qualify for the model (every week has positive sales
and active SKUs in all three). Regression R² came out modest (0.15,
0.03, and 0.31 respectively) — as the original script's own
business-interpretation notes say, assortment breadth alone explains
only a limited part of demand, and R² should be reviewed before trusting
the recommendation. With that caveat, the optimizer recommends shifting
space from Storage & Organization (28.5% → 22.0%) to Home Decor (28.8% →
35.6%), leaving General Merchandise roughly unchanged (42.8% → 42.3%),
for a modelled **+21.8% weekly gross profit** uplift. This is a modelled
scenario for evaluation, not an automatic buying decision — the original
script's own notes on what a production version would need (seasonality,
promotions, stock-outs, supplier risk, lead time, price elasticity,
minimum display requirements, category strategic importance) still apply.
