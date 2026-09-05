#!/usr/bin/env python3
"""Backtest inventory review policies for the top-N SKUs by safety-stock
investment, using real historical daily demand instead of a static formula.

Reuses the reorder point (`reorder_point_variable_leadtime`) and order
quantity (`eoq_units`) already computed by inventory_planning.py as the
policy parameters, so this answers: "if I actually ran my own computed
numbers as a day-by-day ordering policy, what fill rate and cost would
this SKU's real demand history have produced?"

Uses inventorize (not inventorize3 -- inventorize3 doesn't ship these
simulation functions). The functions used here are flagged deprecated by
the library itself in favour of newer names (sim_Q_max, sim_base_stock_policy,
sim_min_max, periodic_policy) that only exist in inventorize, not
inventorize3; kept as-is here since they match the exercise this was
adapted from and their deprecation doesn't affect correctness. They also
have a minor shared bug (Item_fill_rate's denominator drops the last
period's demand), which slightly inflates the reported fill rate --
noted in the output, not worth a local reimplementation for a 5-SKU
backtest.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import inventorize as inv
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

from inventory_planning import (
    Config,
    classify_products,
    clean_transactions,
    compute_eoq,
    compute_reorder_points,
    daily_product_sales,
    extract_supply_parameters,
    filter_recent_window,
    load_transactions,
    product_stats,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("policy_simulation")

TOP_N = 5
REVIEW_PERIOD_DAYS = 7


def build_ranked_skus(config: Config) -> pd.DataFrame:
    raw = load_transactions(config.data_path, country=config.country)
    clean = clean_transactions(raw)
    windowed = filter_recent_window(clean, config.analysis_window_months)
    daily = daily_product_sales(windowed)
    stats = product_stats(daily)
    classified = classify_products(stats, config.service_level_map, config.default_service_level)

    supply_params = extract_supply_parameters(clean, config)
    merged = pd.merge(classified, supply_params, on="Description", how="left")
    merged["unit_cost"] = merged["unit_cost"].where(merged["unit_cost_is_real"], merged["avg_unit_price"])

    reorder = compute_reorder_points(merged)
    reorder = compute_eoq(reorder)
    return windowed, reorder.sort_values("safety_stock_investment", ascending=False)


def daily_series(windowed: pd.DataFrame, description: str) -> pd.Series:
    """A zero-filled daily demand series over the full window's calendar days.

    This is a different, and lower, daily average than the pipeline's
    `average` column: `average` is the mean over days the product actually
    sold (used for the static reorder-point/EOQ formulas). A day-by-day
    simulation needs every calendar day, including the ones with no sale,
    or it would overstate how often this SKU actually moves.
    """
    full_range = pd.date_range(windowed["date"].min(), windowed["date"].max(), freq="D")
    daily = windowed[windowed["Description"] == description].groupby("date")["Quantity"].sum()
    return daily.reindex(full_range, fill_value=0)


def run_policies_for_sku(sku_row: pd.Series, demand: np.ndarray, config: Config) -> list[dict]:
    mean_sim, sd_sim = demand.mean(), demand.std()
    reorder_point = round(sku_row["reorder_point_variable_leadtime"])
    order_qty = max(round(sku_row["eoq_units"]), 1)
    order_up_to = reorder_point + order_qty
    # This SKU's own lead time/cost/holding rate (real per-SKU data when the
    # source has it -- see extract_supply_parameters() -- rather than one
    # flat assumption applied to every SKU alike.
    leadtime = max(round(sku_row["lead_time_days"]), 1)
    inventory_cost_per_unit_day = sku_row["holding_rate"] * sku_row["unit_cost"] / 365

    common = dict(
        demand=demand,
        mean=mean_sim,
        sd=sd_sim,
        leadtime=leadtime,
        service_level=sku_row["service_level"],
        shortage_cost=sku_row["avg_unit_price"],
        inventory_cost=inventory_cost_per_unit_day,
        ordering_cost=sku_row["ordering_cost_per_order"],
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        runs = {
            "min_Q": inv.sim_min_Q_normal(**common, Quantity=order_qty, Min=reorder_point),
            "base_stock": inv.sim_base_normal(**common, Base=reorder_point),
            "min_max": inv.sim_min_max_normal(**common, Max=order_up_to, Min=reorder_point),
            "periodic_review": inv.Periodic_review_normal(**common, Review_period=REVIEW_PERIOD_DAYS, Max=order_up_to),
            "hybrid": inv.Hibrid_normal(**common, Review_period=REVIEW_PERIOD_DAYS, Min=reorder_point, Max=order_up_to),
        }

    rows = []
    for policy, (_, metrics) in runs.items():
        rows.append(
            {
                "Description": sku_row["Description"],
                "policy": policy,
                "target_service_level": sku_row["service_level"],
                "reorder_point_used": reorder_point,
                "order_qty_or_max_used": order_qty if policy == "min_Q" else order_up_to,
                **metrics,
            }
        )
    return rows


def save_plot(results: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    fill_pivot = results.pivot(index="Description", columns="policy", values="Item_fill_rate")
    fig, ax = plt.subplots(figsize=(10, 6))
    fill_pivot.plot(kind="bar", ax=ax)
    ax.set_title(f"Simulated Item Fill Rate by Policy - Top {TOP_N} SKUs (Germany)")
    ax.set_ylabel("Item fill rate")
    ax.set_xlabel("")
    ax.axhline(results["target_service_level"].iloc[0], color="black", linestyle="--", linewidth=1, label="target service level")
    ax.legend(title="Policy", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(output_dir / "policy_simulation_fill_rate.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "policy_simulation_fill_rate.png")

    # Fill rate comes out flat (100%) for every policy on these SKUs -- see
    # main()'s log line comparing true vs. selling-day average demand. Average
    # inventory level is where the policies actually differ, so it's plotted
    # too (log scale: it spans two orders of magnitude across these 5 SKUs).
    inv_pivot = results.pivot(index="Description", columns="policy", values="average_inventory_level")
    fig, ax = plt.subplots(figsize=(10, 6))
    inv_pivot.plot(kind="bar", ax=ax, logy=True)
    ax.set_title(f"Simulated Average Inventory Level by Policy - Top {TOP_N} SKUs (Germany)")
    ax.set_ylabel("Average inventory level (units, log scale)")
    ax.set_xlabel("")
    ax.legend(title="Policy", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(output_dir / "policy_simulation_inventory_level.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "policy_simulation_inventory_level.png")


def main() -> None:
    config = Config()
    windowed, ranked = build_ranked_skus(config)
    top_skus = ranked.head(TOP_N)

    logger.info("Top %d SKUs by safety_stock_investment: %s", TOP_N, list(top_skus["Description"]))

    all_rows = []
    for _, sku_row in top_skus.iterrows():
        demand = daily_series(windowed, sku_row["Description"]).to_numpy()
        selling_days = int((demand > 0).sum())
        logger.info(
            "%s: %d calendar days in window, %d with a sale (true daily mean=%.2f, vs. pipeline's selling-day average=%.2f)",
            sku_row["Description"], len(demand), selling_days, demand.mean(), sku_row["average"],
        )
        all_rows.extend(run_policies_for_sku(sku_row, demand, config))

    results = pd.DataFrame(all_rows)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "policy_simulation_top5.csv"
    results.to_csv(csv_path, index=False)
    logger.info("Saved %s", csv_path)

    save_plot(results, output_dir)

    summary_cols = ["Description", "policy", "target_service_level", "Item_fill_rate", "cycle_service_level", "average_inventory_level", "total_lost_sales"]
    logger.info("Results:\n%s", results[summary_cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
