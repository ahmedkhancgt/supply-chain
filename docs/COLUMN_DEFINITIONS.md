# Column & Formula Reference

This document explains every derived column produced by
`src/inventory_planning.py`, in the order they're calculated, with the
underlying formula and a worked numeric example. It's meant to be readable
without knowing pandas or the statistics behind it in advance.

All examples below use one real row from a run against `data/Germany.xlsx`:

**STOOL HOME SWEET HOME** — `average = 30.5`, `sd = 41.72`,
`product_mix = A_A`, `service_level = 0.95`

## Contents

1. [Row-level: `revenue`](#1-row-level-revenue)
2. [Daily aggregates: `total_daily`, `total_revenue` (day+product)](#2-daily-aggregates)
3. [Product aggregates: `average`, `sd`, `total_sales`, `total_revenue`, `avg_unit_price`](#3-product-aggregates)
4. [ABC classification: `product_mix`, `service_level`](#4-abc-classification)
5. [Reorder point formulas](#5-reorder-point-formulas)
6. [`safety_stock_uplift_pct`](#6-safety_stock_uplift_pct)
7. [`safety_stock_investment`](#7-safety_stock_investment)
8. [Known library bug this script works around](#8-known-library-bug-this-script-works-around)

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

**Example:** STOOL HOME SWEET HOME averages 30.5 units/day with a standard
deviation of 41.72 — a spiky, lumpy seller, not a steady one.

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

Calculated in `compute_reorder_points()`.

### Demand during lead time

```python
demand_lead_time = average * lead_time_days
```

Expected units sold during the time it takes a new order to arrive.

```
= 30.5 * 12 = 366 units
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
sigma_dl_fixed = 41.72 * sqrt(12) = 144.55
safety_stock_fixed_leadtime = 1.645 * 144.55 ≈ 237.7
reorder_point_fixed_leadtime = 366 + 237.7 ≈ 603.7
```

Plain English: *"Over 12 days, how much could demand realistically vary,
and how much extra buffer on top of expected demand do I need to hit my
service level?"*

### Model B — lead time itself is uncertain

Accounts for the supplier sometimes delivering early or late
(`lead_time_sd_days`, default 2 days), on top of demand variability. The
two sources of uncertainty are combined under one square root:

```python
sigma_dl_variable = sqrt(
    lead_time_days * sd**2 + average**2 * lead_time_sd_days**2
)
safety_stock_variable_leadtime = safety_factor * sigma_dl_variable
reorder_point_variable_leadtime = demand_lead_time + safety_stock_variable_leadtime
```

```
sigma_dl_variable = sqrt(12 * 41.72**2 + 30.5**2 * 2**2)
                   = sqrt(20,886 + 3,721) ≈ 156.9
safety_stock_variable_leadtime = 1.645 * 156.9 ≈ 258.0
reorder_point_variable_leadtime = 366 + 258.0 ≈ 624.0
```

This needs *more* safety stock than Model A (258.0 vs. 237.7 units) because
it's honest about a second source of risk: an unreliable delivery
schedule, not just unpredictable demand.

---

## 6. `safety_stock_uplift_pct`

```python
safety_stock_uplift_pct = (
    safety_stock_variable_leadtime / safety_stock_fixed_leadtime - 1
) * 100
```

```
= (258.0 / 237.7 - 1) * 100 ≈ 8.5%
```

How much more safety stock a product needs once lead-time uncertainty is
accounted for, not just demand uncertainty. Products with `sd = 0`
(single-day sellers) have `safety_stock_fixed_leadtime = 0`, so this is
left as `NaN` for them (division by zero has no meaningful percentage).

---

## 7. `safety_stock_investment`

```python
safety_stock_investment = safety_stock_variable_leadtime * avg_unit_price
```

Converts safety stock from "units" into money tied up in a buffer for that
product. This is the column the output files are ranked by — it answers
"which products' safety stock is costing the most?", which is more
actionable than ranking by unit count alone.

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
