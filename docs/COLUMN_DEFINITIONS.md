# Column & Formula Reference

This document explains every derived column produced by
`src/inventory_planning.py`, in the order they're calculated, with the
underlying formula and a worked numeric example. It's meant to be readable
without knowing pandas or the statistics behind it in advance.

All examples below use one real row from a run against `data/Data.xlsx`,
filtered to `Config`'s default single-country scope:

**Regency Cakestand Tier** — `average = 28.5`, `sd = 38.89`,
`product_mix = A_A`, `service_level = 0.95`, `lead_time_days = 24.0`,
`lead_time_sd_days = 6.5`, `unit_cost = 7.89`, `ordering_cost_per_order
= 62.08`, `holding_rate = 0.268`

## Contents

1. [Row-level: `revenue`](#1-row-level-revenue)
2. [Daily aggregates: `total_daily`, `total_revenue` (day+product)](#2-daily-aggregates)
3. [Product aggregates: `average`, `sd`, `total_sales`, `total_revenue`, `avg_unit_price`](#3-product-aggregates)
4. [ABC classification: `product_mix`, `service_level`](#4-abc-classification)
5. [Reorder point formulas](#5-reorder-point-formulas)
6. [`safety_stock_uplift_pct`](#6-safety_stock_uplift_pct)
7. [`safety_stock_investment`](#7-safety_stock_investment)
8. [Known library bug this script works around](#8-known-library-bug-this-script-works-around)
9. [Economic order quantity (EOQ)](#9-economic-order-quantity-eoq)

---

## 1. Row-level: `revenue`

Calculated in `filter_recent_window()` on each individual transaction line:

```python
revenue = Quantity * Price
```

Units sold × unit price for that one line of that one invoice.

---

## 2. Daily aggregates

Calculated in `daily_product_sales()` by grouping transactions by
`date` + `Description` and summing:

| Column | Meaning |
|---|---|
| `total_daily` | Total units of that product sold **on that day** |
| `total_revenue` | Total revenue from that product **on that day** |

---

## 3. Product aggregates

Calculated in `product_stats()` by grouping the daily table by
`Description` only:

| Column | Formula | Meaning |
|---|---|---|
| `average` | `mean(total_daily)` across all days in the window | Typical daily demand for the product |
| `sd` | `std(total_daily)` across all days in the window | How much daily demand swings around the average (demand volatility). Products sold on only one day in the window get `sd = 0` (there's no variance signal from a single observation), not a missing value. |
| `total_sales` | `sum(total_daily)` | Total units sold across the whole window |
| `total_revenue` | `sum(total_revenue)` | Total revenue across the whole window |
| `avg_unit_price` | `total_revenue / total_sales` | Effective average selling price per unit |

**Example:** Regency Cakestand Tier averages 28.5 units/day with a
standard deviation of 38.89 — a spiky, lumpy seller, not a steady one.

---

## 4. ABC classification

Calculated in `classify_products()`, which calls
`inventorize3.productmix(skus, sales, revenue)`.

1. Rank every product by `total_sales`, take the cumulative % of total
   volume it represents.
2. Independently rank every product by `total_revenue`, take the
   cumulative % of total revenue it represents.
3. For each ranking, bucket by the classic Pareto thresholds:

   | Cumulative share | Category |
   |---|---|
   | up to 80% | `A` |
   | 80%–95% | `B` |
   | 95%–100% | `C` |

4. `product_mix = sales_category + "_" + revenue_category` — one of 9
   combinations (`A_A`, `A_B`, `A_C`, `B_A`, ..., `C_C`).
   `A_A` = high volume **and** high revenue: your most important products.
   `C_C` = low volume **and** low revenue: the long tail.

5. `service_level` is then looked up from `Config.service_level_map` using
   `product_mix`:

   ```python
   DEFAULT_SERVICE_LEVEL_MAP = {
       "A_A": 0.95, "A_B": 0.95, "A_C": 0.95,
       "B_A": 0.70, "B_B": 0.70, "B_C": 0.75,
       "C_A": 0.80, "C_B": 0.80, "C_C": 0.70,
   }
   ```

   Higher-priority classes get a higher target service level (probability
   of not stocking out), which drives more safety stock in step 5. Any
   class not present in the map falls back to `default_service_level`
   (0.75), with a warning logged.

**Example:** `A_A` → `service_level = 0.95` (target: 95% chance of not
running out before the next delivery arrives).

---

## 5. Reorder point formulas

Calculated in `compute_reorder_points()`. `lead_time_days` and
`lead_time_sd_days` are per-SKU values from `extract_supply_parameters()`
— real data averaged from the source file's own columns when it has them,
falling back to a flat `Config` placeholder only for a SKU/source
missing that column (see the main `README.md`).

### Demand during lead time

```python
demand_lead_time = average * lead_time_days
```

Expected units sold during the time it takes a new order to arrive.

```
= 28.5 * 24.0 = 684 units
```

### Safety factor

```python
safety_factor = scipy.stats.norm.ppf(service_level)
```

Converts a target service level (a probability) into a multiplier using
the inverse of the normal distribution's cumulative distribution function
— this is the standard "z-score" used in safety stock formulas. A 95%
service level gives a factor of about **1.645**; a 70% service level gives
only about 0.524. Higher target service level → bigger multiplier → more
safety stock.

### Model A — fixed lead time

Assumes the supplier's lead time itself never varies; only demand does.

```python
sigma_dl_fixed = sd * sqrt(lead_time_days)
safety_stock_fixed_leadtime = safety_factor * sigma_dl_fixed
reorder_point_fixed_leadtime = demand_lead_time + safety_stock_fixed_leadtime
```

```
sigma_dl_fixed = 38.89 * sqrt(24.0) ≈ 190.53
safety_stock_fixed_leadtime = 1.645 * 190.53 ≈ 313.39
reorder_point_fixed_leadtime = 684 + 313.39 ≈ 997.39
```

Plain English: *"Over 24 days, how much could demand realistically vary,
and how much extra buffer on top of expected demand do I need to hit my
service level?"*

### Model B — lead time itself is uncertain

Accounts for the supplier sometimes delivering early or late
(`lead_time_sd_days`), on top of demand variability. The two sources of
uncertainty are combined under one square root:

```python
sigma_dl_variable = sqrt(
    lead_time_days * sd**2 + average**2 * lead_time_sd_days**2
)
safety_stock_variable_leadtime = safety_factor * sigma_dl_variable
reorder_point_variable_leadtime = demand_lead_time + safety_stock_variable_leadtime
```

```
sigma_dl_variable = sqrt(24.0 * 38.89**2 + 28.5**2 * 6.5**2)
                   = sqrt(24.0 * 1512.5 + 812.25 * 42.25) ≈ 265.74
safety_stock_variable_leadtime = 1.645 * 265.74 ≈ 437.10
reorder_point_variable_leadtime = 684 + 437.10 ≈ 1121.10
```

This needs *more* safety stock than Model A (437.10 vs. 313.39 units)
because it's honest about a second source of risk: an unreliable delivery
schedule (this SKU's real `lead_time_sd_days` of 6.5 days is substantial
relative to its 24-day lead time), not just unpredictable demand.

---

## 6. `safety_stock_uplift_pct`

```python
safety_stock_uplift_pct = (
    safety_stock_variable_leadtime / safety_stock_fixed_leadtime - 1
) * 100
```

```
= (437.10 / 313.39 - 1) * 100 ≈ 39.48%
```

How much more safety stock a product needs once lead-time uncertainty is
accounted for, not just demand uncertainty. Products with `sd = 0`
(single-day sellers) have `safety_stock_fixed_leadtime = 0`, so this is
left as `NaN` for them (division by zero has no meaningful percentage).

---

## 7. `safety_stock_investment`

```python
safety_stock_investment = safety_stock_variable_leadtime * unit_cost
```

Converts safety stock from "units" into money tied up in a buffer for
that product — valued at what it costs to acquire (`unit_cost`: a real
per-SKU `Cost` when the source data has one, else `avg_unit_price` as a
fallback — see `extract_supply_parameters()`), not what it sells for.
This is the column the output files are ranked by — it answers "which
products' safety stock is costing the most?", which is more actionable
than ranking by unit count alone.

```
= 437.10 * 7.89 ≈ 3,449.48
```

---

## 8. Known library bug this script works around

`inventorize3.reorderpoint_leadtime_variability()` computes the combined
demand/lead-time variance as:

```python
sigmadl = sqrt(
    leadtimein_days * dailystandarddeviation**2
    + dailydemand**2 * sd_leadtime_days ^ 2   # bug: ^ is bitwise XOR, not **2
)
```

`^` in Python is the bitwise XOR operator, not exponentiation (`**` is).
This only avoids crashing when every input happens to be an integer
(`float ^ int` raises `TypeError`), and even then it silently computes the
wrong number — XOR instead of squaring `sd_leadtime_days`, which
**understates safety stock**. In a test run this understated safety stock
by roughly 30–40% depending on the inputs.

`compute_reorder_points()` in this repo implements the correct formula
directly (`sd_leadtime_days ** 2`, shown in Model B above) instead of
calling that library function, so `safety_stock_variable_leadtime` and
`reorder_point_variable_leadtime` in the output are correct.

(The same bug also exists, byte-for-byte identical, in the original
`inventorize` package — `inventorize3` copied it rather than introducing
it. Confirmed by installing `inventorize` separately and reading its
source for this function.)

---

## 9. Economic order quantity (EOQ)

Reorder point answers *"when do I place an order?"*. EOQ answers a
different question: *"how much should I order each time?"*. Calculated in
`compute_eoq()`.

**Important:** EOQ needs two inputs — `ordering_cost_per_order` (what it
costs to place one order) and `holding_rate` (annual cost of carrying one
unit in stock, as a fraction of its price). `extract_supply_parameters()`
uses real per-SKU values from the source data when available; `Config`
supplies a flat placeholder (`ordering_cost_per_order=50.0`,
`holding_rate=0.20`) only for a SKU/source missing that column. If you're
running against a source without either column, replace the placeholders
with real figures before trusting `eoq_units` or `annual_logistics_cost`
for actual purchasing decisions.

### `annual_demand`

```python
annual_demand = average * 365
```

Annualizes the daily average demand computed in step 3.

### `eoq_units`, `eoq_order_cycle_weeks`

The classic EOQ formula balances two competing costs: ordering more often
costs more in ordering fees, ordering less often costs more in holding
cost (money tied up in stock sitting on a shelf). The quantity that
minimizes their sum is:

```python
holding_cost_per_unit = holding_rate * unit_cost
order_cycle_years = sqrt(2 * ordering_cost_per_order / (annual_demand * holding_cost_per_unit))
eoq_units = order_cycle_years * annual_demand
eoq_order_cycle_weeks = order_cycle_years * 52
```

**Example** (Regency Cakestand Tier, `unit_cost ≈ 7.89`,
`annual_demand ≈ 10,402.5`, real per-SKU `ordering_cost_per_order = 62.08`,
`holding_rate = 0.268`):

```
holding_cost_per_unit = 0.268 * 7.89 ≈ 2.11
order_cycle_years = sqrt(2 * 62.08 / (10,402.5 * 2.11)) ≈ 0.0751
eoq_units = 0.0751 * 10,402.5 ≈ 781.5
eoq_order_cycle_weeks = 0.0751 * 52 ≈ 3.91
```

So: order about 782 units roughly every 3.9 weeks.

### `eoq_practical_units`

EOQ's total-cost curve is flat near its minimum, so a real warehouse
rounds the order cycle to an operationally convenient number of weeks
rather than ordering on an odd 3.41-week cadence. The standard heuristic
rounds to the nearest **power of two weeks** (1, 2, 4, 8, ...):

```python
practical_cycle_weeks = 2 ** round(log(eoq_order_cycle_weeks / sqrt(2)) / log(2))
eoq_practical_units = practical_cycle_weeks / 52 * annual_demand
```

```
practical_cycle_weeks = 2**round(log(3.91 / sqrt(2)) / log(2)) = 2**round(1.47) = 2**1 = 2
eoq_practical_units = 2/52 * 10,402.5 ≈ 400.1
```

This mirrors `inventorize3.TQpractical()` — that function was checked for
the same kind of bug as `reorderpoint_leadtime_variability()` and found to
be correct, but it's reimplemented directly here for consistency with the
rest of this pipeline (and to vectorize it across all SKUs at once instead
of one row at a time).

### `annual_ordering_cost`, `annual_holding_cost`, `annual_logistics_cost`

```python
annual_ordering_cost = (annual_demand / eoq_units) * ordering_cost_per_order
annual_holding_cost = (eoq_units / 2) * holding_cost_per_unit
annual_logistics_cost = annual_ordering_cost + annual_holding_cost + unit_cost * annual_demand
```

At the true EOQ, `annual_ordering_cost` and `annual_holding_cost` are
always equal by construction — that's the point the formula solves for.
For Regency Cakestand Tier both come out to ≈ **826.4**.
`annual_logistics_cost` adds the cost of the goods themselves
(`unit_cost * annual_demand`), giving the full annual cost of carrying
this product: 826.4 + 826.4 + (7.89 × 10,402.5) ≈ **83,746.0**.

### What was deliberately left out

Two things from the original EOQ scripts this was adapted from were
**not** carried into the automatic per-SKU pipeline:

- **A separate EOQ-based reorder point.** The classic EOQ reorder point
  formula (`reorder_point = lead_time_demand`, no safety stock at all) is
  a cruder model than what `compute_reorder_points()` already provides.
  Adding it would just create a second, worse reorder-point column sitting
  next to a better one.
- **Quantity-discount evaluation.** Deciding whether to accept a
  supplier's "10% off if you order 700" offer needs a specific offer
  (a quantity and a discount %) that doesn't exist per SKU in the
  transaction data, so it can't run automatically over 1,000+ products.
  It's available as `evaluate_quantity_discount()` in
  `src/inventory_planning.py` — call it manually with a real offer when
  one comes in.
