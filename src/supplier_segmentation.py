#!/usr/bin/env python3
"""Cross-country product mix, and supplier risk/value segmentation
(Kraljic matrix): which SKUs are worth the most procurement attention.

Adapted from ABC_SUPPLIER.py (uploaded separately), which read
online_retail2.csv and a separate supplier_data.csv this repo doesn't
have. Rebuilt on the same cleaned transaction data inventory_planning.py
loads -- Data.xlsx already carries the risk-factor columns
(availability, no_suppliers, standard, price_fluctuation) and Cost the
original script needed a second file for.

The single-country ABC/multi-criteria-ABC analysis at the top of the
original script (`inv.ABC`, `inv.productmix`) duplicates what
`inventory_planning.classify_products()` already does -- not
reimplemented here. This module covers the two genuinely new pieces:

1. Cross-country product mix (`inv.productmix_storelevel`) -- the same
   volume x revenue ABC classification, computed independently per
   country instead of just the one `Config.country` the main pipeline
   analyzes.
2. Supplier risk/value segmentation -- a Kraljic-matrix-style
   classification (Strategic / Leverage / Critical / Routine) per SKU,
   from its total procurement spend and a composite risk score.

Several real, verified issues from the original are fixed rather than
carried over:

1. **`retail.dropna()` drops far more than intended.** It removes any
   row with a null in *any* column, including ones with no bearing on
   whether a row is a usable transaction (e.g. a missing Customer ID for
   a guest checkout). `clean_transactions()` (already used by the rest
   of this repo) only requires the columns that actually matter --
   Invoice, Description, Quantity, InvoiceDate, Price -- to be present.
2. **No cancellation filtering.** The original never excludes invoices
   starting with "C" (returns/cancellations) -- `clean_transactions()`
   does.
3. **Row-by-row category assignment.** `for i in range(supplier.shape[0]):
   supplier.loc[i,'category'] = category(...)` is O(n) individual
   writes, and it only works because `supplier` still has an untouched
   0..n-1 RangeIndex -- it would silently write to the wrong rows (or
   raise `KeyError`) the moment any filtering happened upstream of it.
   Replaced with a vectorized `np.select`.
4. **Hardcoded value/risk thresholds sized to a file this repo doesn't
   have.** The original's `category()` splits on `value >= 3,000,000`
   and `risk_index >= 1`. Checked directly against Data.xlsx: per-SKU
   procurement spend ranges $22-$7,500 (median $333) -- nothing ever
   reaches 3,000,000, so every SKU would fall into Critical or Routine
   and the matrix would never produce a Strategic or Leverage result.
   Replaced with the standard Kraljic-matrix approach: split at the
   *median* of each axis, computed from this data.
5. **`value = price * Quantity`, ambiguous about which price.** The
   original's generic "price" column could have meant either the
   supplier's cost or the customer-facing selling price -- Data.xlsx has
   both. A supplier segmentation matrix should reflect procurement spend
   (how much you pay suppliers), so this uses `Cost x Quantity`, not
   `Price x Quantity` (Revenue, already used elsewhere in this repo for
   selling-side value).
"""

from __future__ import annotations

import logging
from pathlib import Path

import inventorize3 as inv
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from inventory_planning import Config, clean_transactions, load_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("supplier_segmentation")

RISK_FACTOR_COLUMNS = ["availability", "no_suppliers", "standard", "price_fluctuation"]


def build_country_product_mix(clean: pd.DataFrame) -> pd.DataFrame:
    """ABC (volume x revenue) product mix, computed independently per
    country rather than pooling across them -- a SKU that's a top
    seller in one country can be a long-tail item in another.
    """
    by_country = (
        clean.groupby(["Country", "Description"])
        .agg(total_sales=("Quantity", "sum"), total_revenue=("Revenue", "sum"))
        .reset_index()
    )
    mix = inv.productmix_storelevel(
        by_country["Description"], by_country["total_sales"], by_country["total_revenue"], by_country["Country"]
    )
    mix = mix.rename(columns={"storeofsku": "Country", "sku": "Description"})
    logger.info(
        "Cross-country product mix: %d countries, %d country/SKU combinations",
        mix["Country"].nunique(), len(mix),
    )
    return mix


def build_supplier_risk_value(clean: pd.DataFrame) -> pd.DataFrame:
    """Per-SKU procurement spend and a composite supply-risk score, then
    a Kraljic-matrix quadrant from each relative to its own median (not
    a fixed number -- see module docstring point 4).
    """
    clean = clean.copy()
    clean["spend"] = clean["Cost"] * clean["Quantity"]

    per_sku = clean.groupby("Description").agg(
        **{col: (col, "mean") for col in RISK_FACTOR_COLUMNS},
        total_qty=("Quantity", "sum"),
        total_spend=("spend", "sum"),
        primary_supplier=("supplier", lambda s: s.mode().iat[0]),
    ).reset_index()

    per_sku["risk_index"] = per_sku[RISK_FACTOR_COLUMNS].sum(axis=1)

    value_threshold = per_sku["total_spend"].median()
    risk_threshold = per_sku["risk_index"].median()
    logger.info(
        "Kraljic matrix thresholds (median split): spend >= $%.2f, risk_index >= %.3f",
        value_threshold, risk_threshold,
    )

    high_value = per_sku["total_spend"] >= value_threshold
    high_risk = per_sku["risk_index"] >= risk_threshold
    per_sku["category"] = np.select(
        [high_value & high_risk, high_value & ~high_risk, ~high_value & high_risk],
        ["Strategic", "Leverage", "Critical"],
        default="Routine",
    )

    logger.info("Supplier segmentation:\n%s", per_sku["category"].value_counts().to_string())
    return per_sku.sort_values("total_spend", ascending=False)


def save_plots(mix: pd.DataFrame, segmentation: pd.DataFrame, output_dir: Path, config: Config) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    focus_countries = [c for c in [config.country, "United Kingdom"] if c in set(mix["Country"])]
    if not focus_countries:
        focus_countries = mix["Country"].value_counts().head(2).index.tolist()
    focus_mix = mix[mix["Country"].isin(focus_countries)]

    fig, ax = plt.subplots(figsize=(9, 6))
    counts = focus_mix.groupby(["Country", "product_mix"]).size().unstack(fill_value=0)
    counts.T.plot(kind="bar", ax=ax)
    ax.set_title("Product Mix by Country")
    ax.set_xlabel("Class (volume x revenue)")
    ax.set_ylabel("Number of SKUs")
    ax.legend(title="Country")
    fig.tight_layout()
    fig.savefig(output_dir / "supplier_country_product_mix.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "supplier_country_product_mix.png")

    fig, ax = plt.subplots(figsize=(9, 6))
    for category, group in segmentation.groupby("category"):
        ax.scatter(group["total_spend"], group["risk_index"], label=category, alpha=0.6, s=20)
    ax.set_xscale("log")
    ax.set_xlabel("Total procurement spend per SKU (Cost x Quantity, log scale)")
    ax.set_ylabel("Risk index (availability + no_suppliers + standard + price_fluctuation)")
    ax.set_title("Supplier Risk/Value Segmentation (Kraljic Matrix)")
    ax.legend(title="Category")
    fig.tight_layout()
    fig.savefig(output_dir / "supplier_risk_value_matrix.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "supplier_risk_value_matrix.png")


def run(config: Config) -> None:
    # Both analyses here are inherently cross-scope (across countries, or
    # across the whole supplier base) rather than a single-country demand
    # question, so this loads every country regardless of Config.country.
    raw = load_transactions(config.data_path, country=None)
    clean = clean_transactions(raw)

    mix = build_country_product_mix(clean)
    segmentation = build_supplier_risk_value(clean)

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    mix.to_csv(output_dir / "supplier_country_product_mix.csv", index=False)
    segmentation.to_csv(output_dir / "supplier_risk_value_segmentation.csv", index=False)
    logger.info(
        "Saved supplier_country_product_mix.csv and supplier_risk_value_segmentation.csv to %s", output_dir,
    )

    save_plots(mix, segmentation, output_dir, config)

    logger.info(
        "Top 10 SKUs by procurement spend:\n%s",
        segmentation[["Description", "total_spend", "risk_index", "category", "primary_supplier"]]
        .head(10)
        .to_string(index=False),
    )


def main() -> None:
    run(Config())


if __name__ == "__main__":
    main()
