#!/usr/bin/env python3
"""Demand-pattern classification, price elasticity/optimization, and
single-period (newsvendor) ordering for the Germany transaction data.

Adapted from product_segmentation.py, Behaviour_Pricing.py, and
Seasonal_Inventory.py (uploaded separately) into one pipeline, reusing
inventory_planning.py's data cleaning and ABC classification instead of
duplicating it. Three confirmed bugs found in the originals are fixed here
rather than carried over:

1. `.dt.week` (Behaviour_Pricing.py) is removed in pandas >=2.0 and crashes
   immediately -- replaced with an ISO week key via `.dt.strftime('%G-W%V')`.
2. ADI's day-gap calculation (product_segmentation.py) converted a Timedelta
   to a number of days by string-replacing `"days 00:00:00.000000000"`,
   which no longer matches pandas' current Timedelta string format and
   silently produced all-NaN results -- replaced with `.dt.days`.
3. `single_product_optimization`'s `cost` parameter (Behaviour_Pricing.py)
   was passed positionally where it landed in the `degree` parameter
   instead, defaulting real cost to 0 or crashing for float costs -- always
   called here with `cost=` as a keyword.

Uses the full cleaned transaction history (not the 4-month window
inventory_planning.py uses for reorder planning) since price elasticity and
demand-pattern classification benefit from more history, not a recent
snapshot.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from pathlib import Path

import inventorize as inv
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from inventory_planning import (
    Config,
    classify_products,
    clean_transactions,
    daily_product_sales,
    load_transactions,
    product_stats,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("advanced_analytics")

# Syntetos-Boylan-Croston thresholds (standard values, not tuned to this data).
ADI_THRESHOLD = 1.34
CV2_THRESHOLD = 0.49

# A SKU needs price variation across enough distinct weeks before a
# price-response curve means anything; below this it's skipped rather than
# fit on noise.
MIN_WEEKS_FOR_ELASTICITY = 8
PRICE_OPTIMIZATION_TOP_N = 5
MIN_RELATIVE_PRICE_SPREAD = 0.01  # (max-min)/mean price; below this the fit has nothing to learn from
PER_SKU_OPTIMIZATION_TIMEOUT_S = 15

# Not present in the transaction data -- same category of placeholder as
# Config.ordering_cost_per_order / holding_rate. COST_MARGIN matches the
# assumption both original scripts used (cost = 40% of price). Salvage/
# penalty default to 0 to match Seasonal_Inventory.py's own per-SKU loop
# (its manual single-item example used 0.7/0.4, but the actual per-SKU
# production loop used 0, 0) -- replace with real figures if available.
COST_MARGIN = 0.4
SALVAGE_RATE = 0.0
PENALTY_RATE = 0.0


def classify_demand_pattern(clean: pd.DataFrame) -> pd.DataFrame:
    """ADI (average demand interval) / CV^2 classification per product:
    smooth, intermittent, erratic, or lumpy demand (Syntetos-Boylan-Croston).
    """
    daily = daily_product_sales(clean)

    cv = (
        daily.groupby("Description")
        .agg(average=("total_daily", "mean"), sd=("total_daily", "std"))
        .reset_index()
    )
    cv["sd"] = cv["sd"].fillna(0.0)
    cv["cv_squared"] = (cv["sd"] / cv["average"]) ** 2

    daily_sorted = daily.sort_values(["Description", "date"])
    gap_days = daily_sorted.groupby("Description")["date"].diff().dt.days
    adi = daily_sorted.assign(gap_days=gap_days).groupby("Description").agg(ADI=("gap_days", "mean")).reset_index()

    result = pd.merge(adi, cv, on="Description", how="inner").dropna(subset=["ADI"])
    result["demand_pattern"] = np.select(
        [
            (result["ADI"] <= ADI_THRESHOLD) & (result["cv_squared"] <= CV2_THRESHOLD),
            (result["ADI"] > ADI_THRESHOLD) & (result["cv_squared"] <= CV2_THRESHOLD),
            (result["ADI"] <= ADI_THRESHOLD) & (result["cv_squared"] > CV2_THRESHOLD),
        ],
        ["smooth", "intermittent", "erratic"],
        default="lumpy",
    )
    logger.info("Demand pattern distribution:\n%s", result["demand_pattern"].value_counts().to_string())
    return result


def weekly_price_sales(clean: pd.DataFrame) -> pd.DataFrame:
    df = clean.copy()
    df["weekyear"] = df["InvoiceDate"].dt.strftime("%G-W%V")
    return (
        df.groupby(["Description", "weekyear"])
        .agg(total_sales=("Quantity", "sum"), price=("Price", "mean"))
        .reset_index()
    )


def compute_price_elasticity(weekly: pd.DataFrame, min_weeks: int, cost_margin: float) -> pd.DataFrame:
    rows = []
    skipped_sparse = skipped_error = 0
    for description, group in weekly.groupby("Description"):
        if group["weekyear"].nunique() < min_weeks or group["price"].nunique() < 2:
            skipped_sparse += 1
            continue
        cost = cost_margin * group["price"].max()
        current_price = group["price"].mean()
        try:
            elasticity = inv.linear_elasticity(group["price"], group["total_sales"], current_price, cost)
        except Exception as exc:
            logger.warning("linear_elasticity failed for %r: %s", description, exc)
            skipped_error += 1
            continue
        elasticity = {k: (v[0] if hasattr(v, "__len__") else v) for k, v in elasticity.items()}
        elasticity["Description"] = description
        rows.append(elasticity)

    logger.info(
        "Price elasticity: %d SKUs analyzed, %d skipped (fewer than %d weeks of price variation), %d failed",
        len(rows), skipped_sparse, min_weeks, skipped_error,
    )
    return pd.DataFrame(rows)


def _fit_single_product_optimization(description: str, group: pd.DataFrame, cost_margin: float):
    cost = cost_margin * group["price"].max()
    current_price = group["price"].mean()
    return inv.single_product_optimization(
        group["price"], group["total_sales"], description,
        current_price=current_price, cost=cost,
    )


def optimize_prices_for_top_skus(weekly: pd.DataFrame, top_n: int, min_weeks: int, cost_margin: float) -> dict:
    weeks_per_sku = weekly.groupby("Description")["weekyear"].nunique()
    eligible = weeks_per_sku[weeks_per_sku >= min_weeks].index

    price_spread = weekly[weekly["Description"].isin(eligible)].groupby("Description")["price"].agg(
        lambda p: (p.max() - p.min()) / p.mean()
    )
    # A near-constant price (e.g. float noise around one value) gives the
    # logit curve fit nothing to learn from -- observed on real data as a
    # multi-minute non-converging fit (repeated "overflow in exp") rather
    # than a clean error, so it's filtered out here rather than relied on
    # to fail fast. The timeout below is a second line of defense in case
    # some other SKU hits the same failure mode despite having a plausible
    # price spread.
    eligible = price_spread[price_spread >= MIN_RELATIVE_PRICE_SPREAD].index
    skipped_flat = len(price_spread) - len(eligible)

    totals = weekly[weekly["Description"].isin(eligible)].groupby("Description")["total_sales"].sum()
    candidates = totals.sort_values(ascending=False).head(top_n).index

    results = {}
    for description in candidates:
        group = weekly[weekly["Description"] == description]
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fit_single_product_optimization, description, group, cost_margin)
            try:
                results[description] = future.result(timeout=PER_SKU_OPTIMIZATION_TIMEOUT_S)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "single_product_optimization timed out for %r after %ds; skipped",
                    description, PER_SKU_OPTIMIZATION_TIMEOUT_S,
                )
            except Exception as exc:
                logger.warning("single_product_optimization failed for %r: %s", description, exc)

    logger.info(
        "Price optimization: %d/%d top SKUs succeeded (%d skipped for near-constant price)",
        len(results), len(candidates), skipped_flat,
    )
    return results


def single_period_ordering(clean: pd.DataFrame, cost_margin: float, salvage_rate: float, penalty_rate: float) -> pd.DataFrame:
    """Newsvendor-style order quantity per product, using yearly demand
    totals as the underlying "how much do I need for one period" estimate.
    """
    df = clean.copy()
    df["year"] = df["InvoiceDate"].dt.year
    yearly = df.groupby(["year", "Description"]).agg(total_sales=("Quantity", "sum"), price=("Price", "mean")).reset_index()

    stats = (
        yearly.groupby("Description")
        .agg(expected_demand=("total_sales", "mean"), sd=("total_sales", "std"), price=("price", "mean"))
        .reset_index()
    )
    # NaN: only one year of history, so std() has nothing to compute from.
    # Exactly 0: both years sold identically, which MPN_singleperiod (via
    # scipy.stats.norm with scale=0) treats as a degenerate distribution and
    # returns NaN for -- observed on real data as 113 all-NaN output rows.
    # Both cases get the same 10%-of-demand placeholder, matching this
    # script's own fallback for the NaN case.
    no_sd_signal = (stats["sd"].isna() | (stats["sd"] == 0)).sum()
    if no_sd_signal:
        logger.warning(
            "%d products have no usable demand-variance signal (one year of "
            "history, or identical sales both years); using 10%% of demand as a placeholder sd.",
            no_sd_signal,
        )
    stats["sd"] = stats["sd"].where(stats["sd"] > 0, stats["expected_demand"] * 0.1)
    stats["cost"] = stats["price"] * cost_margin
    stats["salvage"] = stats["price"] * salvage_rate
    stats["penalty"] = stats["price"] * penalty_rate

    rows = []
    for _, row in stats.iterrows():
        result = inv.MPN_singleperiod(
            row["expected_demand"], row["sd"], row["price"], row["cost"], row["salvage"], row["penalty"],
        )
        result["Description"] = row["Description"]
        rows.append(result)

    logger.info("Single-period ordering computed for %d SKUs", len(rows))
    return pd.DataFrame(rows)


def save_demand_pattern_plot(demand_pattern: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(data=demand_pattern, x="cv_squared", y="ADI", hue="demand_pattern", ax=ax)
    ax.axvline(CV2_THRESHOLD, color="grey", linestyle="--", linewidth=1)
    ax.axhline(ADI_THRESHOLD, color="grey", linestyle="--", linewidth=1)
    ax.set_title("Demand Pattern Classification (Germany)")
    ax.set_xlabel("CV² (demand variability)")
    ax.set_ylabel("ADI (average days between sales)")
    fig.tight_layout()
    fig.savefig(output_dir / "demand_pattern_classification.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "demand_pattern_classification.png")


def save_price_optimization_plot(optimizations: dict, output_dir: Path) -> None:
    if not optimizations:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    description, result = next(iter(optimizations.items()))
    predictions = result["predictions"].sort_values("x")

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(predictions.x, predictions.y, label="observed weekly sales")
    ax.plot(predictions.x, predictions.lm_p, label="linear model")
    ax.plot(predictions.x, predictions.logit_p, label="logit model")
    ax.set_title(f"Price Response Curve - {description}")
    ax.set_xlabel("Price")
    ax.set_ylabel("Predicted demand")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "price_optimization_example.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s (example SKU: %r)", output_dir / "price_optimization_example.png", description)


def _extract_number(text: str) -> float:
    """single_product_optimization returns several fields (current_price,
    optimum_linear, optimum_logit, best_model, ...) as pre-formatted
    sentences (e.g. "optimum logit revenue price is [18.19]for Mango")
    rather than plain numbers -- pull the number back out.
    """
    match = re.search(r"[-+]?\d*\.?\d+", text)
    return float(match.group()) if match else float("nan")


def _extract_model_name(text: str) -> str:
    match = re.search(r"is (\w+) model", text)
    return match.group(1) if match else text


def summarize_optimizations(optimizations: dict) -> pd.DataFrame:
    rows = []
    for description, result in optimizations.items():
        rows.append(
            {
                "Description": description,
                "current_price": _extract_number(result["current_price"]),
                "best_model": _extract_model_name(result["best_model"]),
                "optimum_revenue_price_linear": _extract_number(result["optimum_linear"]),
                "optimum_revenue_price_logit": _extract_number(result["optimum_logit"]),
                "point_of_maximum_profit_linear": result["point_of_maximum_profits"]["linear"][0],
                "point_of_maximum_profit_logit": result["point_of_maximum_profits"]["logit"][0],
            }
        )
    return pd.DataFrame(rows)


def run(config: Config) -> None:
    raw = load_transactions(config.data_path, country=config.country)
    clean = clean_transactions(raw)
    clean["revenue"] = clean["Quantity"] * clean["Price"]

    demand_pattern = classify_demand_pattern(clean)
    abc = classify_products(product_stats(daily_product_sales(clean)), config.service_level_map, config.default_service_level)
    demand_pattern = pd.merge(demand_pattern, abc[["Description", "product_mix"]], on="Description", how="left")

    weekly = weekly_price_sales(clean)
    elasticity = compute_price_elasticity(weekly, MIN_WEEKS_FOR_ELASTICITY, COST_MARGIN)
    optimizations = optimize_prices_for_top_skus(weekly, PRICE_OPTIMIZATION_TOP_N, MIN_WEEKS_FOR_ELASTICITY, COST_MARGIN)

    single_period = single_period_ordering(clean, COST_MARGIN, SALVAGE_RATE, PENALTY_RATE)

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    demand_pattern.to_csv(output_dir / "demand_pattern_classification.csv", index=False)
    elasticity.to_csv(output_dir / "price_elasticity.csv", index=False)
    single_period.to_csv(output_dir / "single_period_ordering.csv", index=False)
    if optimizations:
        summarize_optimizations(optimizations).to_csv(output_dir / "price_optimization_top5.csv", index=False)

    save_demand_pattern_plot(demand_pattern, output_dir)
    save_price_optimization_plot(optimizations, output_dir)

    logger.info("Wrote demand_pattern_classification.csv, price_elasticity.csv, "
                "single_period_ordering.csv, price_optimization_top5.csv to %s", output_dir)


def main() -> None:
    run(Config())


if __name__ == "__main__":
    main()
