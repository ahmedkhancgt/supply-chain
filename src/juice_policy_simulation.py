#!/usr/bin/env python3
"""Backtest inventory review policies for multiple SKUs with different
demand volumes, using real historical daily demand instead of a static
formula.

Adapted from section16.py (uploaded separately) into the same shape as
policy_simulation.py: policy parameters are derived from each SKU's own
demand statistics instead of hand-picked per call, every policy for a given
SKU shares the same lead time/service level/costs (a fair comparison by
construction), and results are written as one CSV plus two comparison
charts instead of ad hoc per-call CSVs and a single messy time-series plot.

Two real bugs in section16.py are fixed here rather than carried over:
1. `skus[['apple_juice']]` / `skus[['cantalop_juice']]` (double brackets)
   select a DataFrame instead of a Series, which crashes `inventorize`
   immediately (`ValueError: setting an array element with a sequence`).
2. Its final 5-policy comparison mixed `leadtime=7` (min_Q) with
   `leadtime=2` (the other four) in the same table -- not a fair
   comparison. Every policy here gets the same LEAD_TIME_DAYS.

section16.py picked a Normal model for apple_juice (high volume) and a
Poisson model for grape_juice/cantalop_juice (low, intermittent counts) --
a good modeling choice this script keeps, generalized into an automatic
per-SKU check (POISSON_MEAN_THRESHOLD) instead of a manual per-call
decision, so it applies correctly regardless of which column is high- or
low-volume.
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
from scipy.stats import norm, poisson

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("juice_policy_simulation")

DATA_PATH = Path("data/sku_distributions.csv")
OUTPUT_DIR = Path("output")

LEAD_TIME_DAYS = 7
SERVICE_LEVEL = 0.9
REVIEW_PERIOD_DAYS = 7

# Not present in the data -- same category of placeholder used throughout
# this project's other pipelines (ordering_cost_per_order / holding_rate in
# inventory_planning.py). section16.py's own calls ranged from 1 to 100;
# these match its final (most deliberate) comparison block.
ORDERING_COST = 100
INVENTORY_COST = 1

# SKUs averaging fewer than this many units/day get the Poisson model
# (appropriate for low, intermittent counts); at or above it, Normal.
# grape_juice (~2/day) and cantalop_juice (~10/day) fall under this;
# apple_juice (~101/day) doesn't -- matching section16.py's own choices,
# but decided automatically instead of picked by hand per column.
POISSON_MEAN_THRESHOLD = 20


def load_sku_demand(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    day_gap = df["day"].diff().gt(1).sum()
    if day_gap:
        logger.warning(
            "%d gap(s) in the 'day' column (e.g. day 12 -> 21); treating rows as a "
            "sequential demand series regardless, since that's what the simulation uses.",
            day_gap,
        )
    return df


def compute_policy_parameters(demand: np.ndarray, leadtime: int, service_level: float, is_poisson: bool) -> dict:
    """Reorder point (Min) and order-up-to level (Max), derived from the
    SKU's own demand statistics -- the same auto-calculation each
    inventorize function falls back to internally when Min=False, computed
    here explicitly so it can be reused consistently across all 5 policies
    (Quantity/Max need a value even where the function itself has no
    auto-calc, e.g. sim_min_Q's fixed Quantity).
    """
    mean = demand.mean()
    if is_poisson:
        reorder_point = poisson.ppf(service_level, mean) * leadtime
    else:
        sd = demand.std()
        reorder_point = mean * leadtime + sd * np.sqrt(leadtime) * norm.ppf(service_level)
    order_qty = max(round(mean * leadtime), 1)
    reorder_point = max(round(reorder_point), 1)
    return {
        "mean": mean,
        "sd": demand.std(),
        "reorder_point": reorder_point,
        "order_qty": order_qty,
        "order_up_to": reorder_point + order_qty,
    }


def run_policies_for_sku(sku_name: str, demand: np.ndarray, is_poisson: bool) -> list[dict]:
    params = compute_policy_parameters(demand, LEAD_TIME_DAYS, SERVICE_LEVEL, is_poisson)
    logger.info(
        "%s: mean=%.2f sd=%.2f model=%s reorder_point=%d order_qty=%d order_up_to=%d",
        sku_name, params["mean"], params["sd"], "Poisson" if is_poisson else "Normal",
        params["reorder_point"], params["order_qty"], params["order_up_to"],
    )

    common = dict(
        demand=demand,
        leadtime=LEAD_TIME_DAYS,
        service_level=SERVICE_LEVEL,
        shortage_cost=1,
        ordering_cost=ORDERING_COST,
        inventory_cost=INVENTORY_COST,
    )
    reorder_point, order_qty, order_up_to = params["reorder_point"], params["order_qty"], params["order_up_to"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        if is_poisson:
            runs = {
                "min_Q": inv.sim_min_Q_pois(**common, lambda1=params["mean"], Quantity=order_qty, Min=reorder_point),
                "base_stock": inv.sim_base_pois(**common, lambda1=params["mean"], Base=reorder_point),
                "min_max": inv.sim_min_max_pois(**common, lambda1=params["mean"], Max=order_up_to, Min=reorder_point),
                "periodic_review": inv.Periodic_review_pois(**common, lambda1=params["mean"], Review_period=REVIEW_PERIOD_DAYS, Max=order_up_to),
                "hybrid": inv.Hibrid_pois(**common, lambda1=params["mean"], Review_period=REVIEW_PERIOD_DAYS, Min=reorder_point, Max=order_up_to),
            }
        else:
            runs = {
                "min_Q": inv.sim_min_Q_normal(**common, mean=params["mean"], sd=params["sd"], Quantity=order_qty, Min=reorder_point),
                "base_stock": inv.sim_base_normal(**common, mean=params["mean"], sd=params["sd"], Base=reorder_point),
                "min_max": inv.sim_min_max_normal(**common, mean=params["mean"], sd=params["sd"], Max=order_up_to, Min=reorder_point),
                "periodic_review": inv.Periodic_review_normal(**common, mean=params["mean"], sd=params["sd"], Review_period=REVIEW_PERIOD_DAYS, Max=order_up_to),
                "hybrid": inv.Hibrid_normal(**common, mean=params["mean"], sd=params["sd"], Review_period=REVIEW_PERIOD_DAYS, Min=reorder_point, Max=order_up_to),
            }

    rows = []
    for policy, (_, metrics) in runs.items():
        rows.append(
            {
                "sku": sku_name,
                "demand_model": "Poisson" if is_poisson else "Normal",
                "policy": policy,
                "target_service_level": SERVICE_LEVEL,
                "reorder_point_used": reorder_point,
                "order_qty_or_max_used": order_qty if policy == "min_Q" else order_up_to,
                **metrics,
            }
        )
    return rows


def save_plots(results: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    fill_pivot = results.pivot(index="sku", columns="policy", values="Item_fill_rate")
    fig, ax = plt.subplots(figsize=(10, 6))
    fill_pivot.plot(kind="bar", ax=ax)
    ax.set_title("Simulated Item Fill Rate by Policy (Juice SKUs)")
    ax.set_ylabel("Item fill rate")
    ax.set_xlabel("")
    ax.axhline(SERVICE_LEVEL, color="black", linestyle="--", linewidth=1, label="target service level")
    ax.legend(title="Policy", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(output_dir / "juice_policy_fill_rate.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "juice_policy_fill_rate.png")

    inv_pivot = results.pivot(index="sku", columns="policy", values="average_inventory_level")
    fig, ax = plt.subplots(figsize=(10, 6))
    inv_pivot.plot(kind="bar", ax=ax, logy=True)
    ax.set_title("Simulated Average Inventory Level by Policy (Juice SKUs)")
    ax.set_ylabel("Average inventory level (units, log scale)")
    ax.set_xlabel("")
    ax.legend(title="Policy", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(output_dir / "juice_policy_inventory_level.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "juice_policy_inventory_level.png")


def main() -> None:
    skus = load_sku_demand(DATA_PATH)
    sku_columns = ["apple_juice", "grape_juice", "cantalop_juice"]

    all_rows = []
    for sku_name in sku_columns:
        demand = skus[sku_name].to_numpy()
        is_poisson = demand.mean() < POISSON_MEAN_THRESHOLD
        all_rows.extend(run_policies_for_sku(sku_name, demand, is_poisson))

    results = pd.DataFrame(all_rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "juice_policy_simulation.csv"
    results.to_csv(csv_path, index=False)
    logger.info("Saved %s", csv_path)

    save_plots(results, OUTPUT_DIR)

    summary_cols = ["sku", "demand_model", "policy", "target_service_level", "Item_fill_rate", "cycle_service_level", "average_inventory_level", "total_lost_sales"]
    logger.info("Results:\n%s", results[summary_cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
