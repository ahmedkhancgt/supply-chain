#!/usr/bin/env python3
"""Market basket analysis: which products get bought together, and which
of those pairings could help move slow-selling stock.

Adapted from MarketBasketanalysis_1.ipynb (uploaded separately), which
assumed a pre-existing retail_clean.csv this repo doesn't have -- rebuilt
here on the same cleaned Germany transaction data inventory_planning.py
already loads.

Two real, verified bugs from the notebook are fixed rather than carried
over:

1. **"slow_moving" was actually the second-fastest-moving octile.**
   `pd.qcut(total_quantity_sold, 8, labels=False)` labels bins 0 (lowest
   quantity) through 7 (highest); the notebook filters `cut==6`. Checked
   directly against this data: bin 6 covers products that sold 98-188
   units total -- solidly mid-to-high volume, not "slow moving" by any
   reading. The genuinely slow-moving bin is 0. A rule table meant to
   surface cross-sell opportunities for overstocked slow movers was
   actually surfacing opportunities for already-popular products.
2. **Multi-item association rules were silently truncated to one item.**
   `rules["antecedents"].apply(lambda x: list(x)[0])` keeps only the
   first element of what mlxtend returns as a frozenset. Checked directly
   against this data: 224 of 930 rules (24%) have more than one
   antecedent item, so almost a quarter of the notebook's rule table
   would have displayed only part of the actual rule (e.g. "buy A -> buy
   C" when the real rule was "buy A and B -> buy C") with no visible sign
   anything was dropped. Fixed by joining every item in the set into one
   readable string instead of indexing into it.

Also: `min_support=0.009` (tuned for the ~37,000-invoice dataset the
notebook was written against) produces 36,658 rules on this repo's
~700-invoice Germany data -- mostly noise from single-digit invoice
counts. MIN_SUPPORT here is sized to this dataset instead (see below).
`association_rules` was also called without `min_threshold`, silently
taking mlxtend's generic default (0.8) rather than the analytically
meaningful cutoff for lift specifically (>1.0 is where an association
becomes positive) -- made explicit here.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules

from inventory_planning import Config, clean_transactions, load_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("market_basket_analysis")

# Re-checked directly against whichever source Config.data_path points at,
# since the right threshold depends on how many invoices/products there
# are, not a fixed number. The notebook's original 0.009 was tuned for a
# ~37,000-invoice dataset (mostly noise on anything smaller); 0.02 worked
# for the original ~700-invoice/2,400-product Germany.xlsx slice but
# produced zero rules against Data.xlsx's Germany slice (634 invoices
# spread across 1,250 products -- a sparser catalog-to-basket ratio even
# at a similar invoice count) -- checked directly: 0.02 -> 0 rules,
# 0.006 -> 8, 0.004 -> 26. Re-verify this constant if the data source
# changes again.
MIN_SUPPORT = 0.006
LIFT_MIN_THRESHOLD = 1.0
SLOW_MOVER_QUANTILES = 8
SLOW_MOVER_BIN = 0  # lowest-quantity octile; see module docstring


def build_baskets(clean: pd.DataFrame) -> pd.DataFrame:
    """One row per invoice, one column per product, True where that
    product appears anywhere on that invoice (repeat line items for the
    same product on one invoice collapse to a single True, same as the
    original notebook's sum-then-binarize -- just without the redundant
    intermediate groupby-then-regroup on the same keys).
    """
    item_counts = clean.groupby(["Invoice", "Description"]).size().unstack(fill_value=0)
    return item_counts > 0


def mine_association_rules(baskets_encoded: pd.DataFrame) -> pd.DataFrame:
    frequent_itemsets = apriori(baskets_encoded, min_support=MIN_SUPPORT, use_colnames=True)
    logger.info("Frequent itemsets at min_support=%.3f: %d", MIN_SUPPORT, len(frequent_itemsets))

    rules = association_rules(frequent_itemsets, metric="lift", min_threshold=LIFT_MIN_THRESHOLD)
    logger.info("Association rules with lift >= %.1f: %d", LIFT_MIN_THRESHOLD, len(rules))

    multi_item = (rules["antecedents"].apply(len) > 1) | (rules["consequents"].apply(len) > 1)
    logger.info(
        "%d of %d rules (%.0f%%) involve more than one item on at least one side -- "
        "would have been silently truncated by the original's list(x)[0] pattern",
        multi_item.sum(), len(rules), 100 * multi_item.mean() if len(rules) else 0,
    )

    rules = rules.copy()
    rules["antecedents"] = rules["antecedents"].apply(lambda items: " + ".join(sorted(items)))
    rules["consequents"] = rules["consequents"].apply(lambda items: " + ".join(sorted(items)))
    return rules.sort_values("confidence", ascending=False)


def find_slow_movers(clean: pd.DataFrame) -> pd.Series:
    """Products in the lowest total-quantity-sold octile."""
    total_quantity = clean.groupby("Description")["Quantity"].sum()
    bin_id = pd.qcut(total_quantity, SLOW_MOVER_QUANTILES, labels=False)
    slow_movers = total_quantity[bin_id == SLOW_MOVER_BIN]
    logger.info(
        "%d slow-moving products identified (bottom of %d bins, quantity sold %d-%d)",
        len(slow_movers), SLOW_MOVER_QUANTILES, slow_movers.min(), slow_movers.max(),
    )
    return slow_movers


def save_plots(clean: pd.DataFrame, rules: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    order_size = clean.groupby("Invoice")["Description"].size()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.boxplot(order_size)
    ax.set_title("Items per Order (Germany)")
    ax.set_ylabel("Distinct products per invoice")
    ax.set_xticks([])
    fig.tight_layout()
    fig.savefig(output_dir / "basket_order_size.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "basket_order_size.png")

    top_sellers = clean.groupby("Description")["Quantity"].sum().sort_values(ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(9, 6))
    top_sellers.iloc[::-1].plot(kind="barh", ax=ax, color="#4C72B0")
    ax.set_title("Top 10 Products by Units Sold (Germany)")
    ax.set_xlabel("Units sold")
    fig.tight_layout()
    fig.savefig(output_dir / "basket_top_sellers.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "basket_top_sellers.png")

    if len(rules):
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(rules["support"], rules["confidence"], c=rules["lift"], cmap="viridis", alpha=0.7)
        cbar = fig.colorbar(ax.collections[0], ax=ax)
        cbar.set_label("Lift")
        ax.set_xlabel("Support")
        ax.set_ylabel("Confidence")
        ax.set_title("Association Rules (Germany)")
        fig.tight_layout()
        fig.savefig(output_dir / "basket_rules_scatter.png", dpi=150)
        plt.close(fig)
        logger.info("Saved %s", output_dir / "basket_rules_scatter.png")


def run(config: Config) -> None:
    raw = load_transactions(config.data_path, country=config.country)
    clean = clean_transactions(raw)
    logger.info(
        "%d invoices, %d distinct products", clean["Invoice"].nunique(), clean["Description"].nunique(),
    )

    baskets_encoded = build_baskets(clean)
    rules = mine_association_rules(baskets_encoded)
    slow_movers = find_slow_movers(clean)

    slow_mover_names = set(slow_movers.index)
    slow_mover_rules = rules[
        rules["consequents"].apply(lambda text: any(item in slow_mover_names for item in text.split(" + ")))
    ]
    logger.info(
        "%d rules recommend a slow-moving product as the consequent (a genuine cross-sell "
        "opportunity for overstocked items, unlike the notebook's inverted bin choice)",
        len(slow_mover_rules),
    )

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    rules.to_csv(output_dir / "basket_association_rules.csv", index=False)
    slow_mover_rules.to_csv(output_dir / "basket_slow_mover_cross_sell.csv", index=False)
    slow_movers.reset_index().rename(columns={"Quantity": "total_quantity_sold"}).to_csv(
        output_dir / "basket_slow_movers.csv", index=False
    )
    logger.info(
        "Saved basket_association_rules.csv, basket_slow_mover_cross_sell.csv, and "
        "basket_slow_movers.csv to %s", output_dir,
    )

    save_plots(clean, rules, output_dir)

    logger.info(
        "Top 5 rules by confidence:\n%s",
        rules[["antecedents", "consequents", "support", "confidence", "lift"]].head(5).to_string(index=False),
    )


def main() -> None:
    run(Config())


if __name__ == "__main__":
    main()
