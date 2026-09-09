#!/usr/bin/env python3
"""Assortment planning: how much catalog/shelf space the top categories
should get to maximize gross profit.

Adapted from Assortment_Planning_Data.py (uploaded separately), which
was already written against Data.xlsx's schema but read the file
directly with `pd.read_excel()` and its own narrower cleaning step
(dropna on a few columns, positive Quantity/Price, non-negative Cost)
rather than this repo's `clean_transactions()`. Rebuilt to reuse
`inventory_planning.load_transactions()`/`clean_transactions()` instead
-- a real, verified fix: `clean_transactions()` removes 47 rows with
`StockCode == "C2"` ("Carriage" -- a shipping charge, not a product),
which the original's cleaning let straight through under
`category == "General Merchandise"`. Those rows would have counted a
shipping fee as a "General Merchandise" sale in every downstream
aggregate feeding the assortment model (revenue, units, gross profit,
active-SKU share).

Unlike the reorder-point/EOQ pipeline, this runs against every country
combined, not one -- the original script never filtered by country
either, and assortment/shelf-space allocation is a catalog-wide decision
rather than a per-market one (see `supplier_segmentation.py`'s
cross-country product mix for the per-market view of category
importance).

### Model logic (unchanged from the original)
1. Select the top `top_n` categories by historical revenue.
2. Aggregate weekly (Monday-start weeks), using each category's share of
   active SKUs -- among the top categories only -- as an
   assortment-breadth proxy. Data.xlsx has no physical shelf-space field.
3. Fit one log-log regression per category:
   `log10(units_sold_i) = intercept_i + sum_j beta_ij * log10(space_share_j)`
   across *every* top category's space share -- a cross-category
   elasticity model, so one category's space can help or hurt another's
   sales (cannibalization/complementarity), not just its own.
4. Multiply predicted units by each category's historical average unit
   gross profit (`(Price - Cost)` per unit sold) to get predicted profit.
5. Optimize each category's space share (bounded 10-70%, summing to
   100%) to maximize total predicted weekly gross profit.

Verified against data/Data.xlsx: all 104 weeks in the data qualify for
the model (every week has positive sales and active SKUs in all 3 top
categories -- General Merchandise, Storage & Organization, Home Decor),
so the valid-weeks filter drops nothing here. R² for the three
regressions came out modest (0.03-0.31 -- Storage & Organization's own
sales are the least explained by assortment-breadth alone). The
optimizer converges to a real (non-boundary-clamped) recommendation with
a double-digit modelled profit uplift -- see README.md for the actual
numbers. As the original script's own business-interpretation notes say:
this is a modelled scenario, not an automatic buying decision, and R²
should be reviewed before trusting it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import optimize
from sklearn.linear_model import LinearRegression

from inventory_planning import Config, clean_transactions, load_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("assortment_planning")


@dataclass(frozen=True)
class AssortmentConfig:
    top_n: int = 3
    min_space_pct: float = 10.0
    max_space_pct: float = 70.0
    total_space_pct: float = 100.0
    output_dir: Path = Path("output")


def select_top_categories(clean: pd.DataFrame, top_n: int) -> tuple[list[str], pd.DataFrame]:
    """Requires `clean` to already have a `GrossProfit` column."""
    category_summary = (
        clean.groupby("category", as_index=False)
        .agg(
            Revenue=("Revenue", "sum"),
            Units=("Quantity", "sum"),
            GrossProfit=("GrossProfit", "sum"),
            UniqueSKUs=("StockCode", "nunique"),
            Transactions=("Invoice", "nunique"),
        )
        .sort_values("Revenue", ascending=False)
    )
    top_categories = category_summary.head(top_n)["category"].tolist()
    logger.info("Top %d categories by revenue: %s", top_n, top_categories)
    return top_categories, category_summary


def build_weekly_space_and_sales(clean: pd.DataFrame, top_categories: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Weekly (Monday-start) active-SKU share and units sold for the top
    categories. Returns `(space_pct, units_sold, model_df)` -- `model_df`
    is every cleaned transaction row for the top categories, kept for the
    average-unit-profit calculation below, which uses the full history
    rather than just the weeks that pass the valid-weeks filter here.
    """
    model_df = clean[clean["category"].isin(top_categories)].copy()
    model_df["Week"] = model_df["date"] - pd.to_timedelta(model_df["date"].dt.weekday, unit="D")

    weekly = (
        model_df.groupby(["Week", "category"])
        .agg(ActiveSKUs=("StockCode", "nunique"), UnitsSold=("Quantity", "sum"))
        .reset_index()
    )
    active_skus = weekly.pivot(index="Week", columns="category", values="ActiveSKUs").reindex(columns=top_categories)
    units_sold = weekly.pivot(index="Week", columns="category", values="UnitsSold").reindex(columns=top_categories)

    valid_weeks = (
        active_skus.notna().all(axis=1)
        & units_sold.notna().all(axis=1)
        & (active_skus > 0).all(axis=1)
        & (units_sold > 0).all(axis=1)
    )
    total_weeks = len(active_skus)
    active_skus = active_skus.loc[valid_weeks]
    units_sold = units_sold.loc[valid_weeks]
    logger.info(
        "Weeks used in model: %d of %d (every top category needs positive active SKUs and units that week)",
        len(active_skus), total_weeks,
    )

    space_pct = active_skus.div(active_skus.sum(axis=1), axis=0) * 100
    return space_pct, units_sold, model_df


def fit_category_regressions(
    space_pct: pd.DataFrame, units_sold: pd.DataFrame, top_categories: list[str]
) -> tuple[dict[str, LinearRegression], pd.DataFrame]:
    """One log-log regression per category:
    `log10(units_sold_i) = intercept_i + sum_j beta_ij * log10(space_pct_j)`
    -- a cross-category elasticity model, not just each category's own
    space vs. its own sales.
    """
    x = np.log10(space_pct.values)
    models: dict[str, LinearRegression] = {}
    rows = []
    for category in top_categories:
        y = np.log10(units_sold[category].values)
        model = LinearRegression().fit(x, y)
        models[category] = model
        row = {"Sales_Category": category, "Intercept": model.intercept_, "R2": model.score(x, y)}
        for j, space_category in enumerate(top_categories):
            row[f"Beta_{space_category}"] = model.coef_[j]
        rows.append(row)
    coefficients_df = pd.DataFrame(rows)
    logger.info("Regression R2 by category:\n%s", coefficients_df[["Sales_Category", "R2"]].to_string(index=False))
    return models, coefficients_df


def compute_avg_unit_profit(model_df: pd.DataFrame, top_categories: list[str]) -> dict[str, float]:
    profit_summary = (
        model_df.groupby("category")
        .agg(Units=("Quantity", "sum"), GrossProfit=("GrossProfit", "sum"))
        .reindex(top_categories)
    )
    profit_summary["AvgUnitProfit"] = profit_summary["GrossProfit"] / profit_summary["Units"]
    logger.info("Average unit gross profit:\n%s", profit_summary.to_string())
    return profit_summary["AvgUnitProfit"].to_dict()


def make_predictors(models: dict[str, LinearRegression], avg_unit_profit: dict[str, float], top_categories: list[str]):
    def predicted_sales(space_values) -> dict[str, float]:
        space_values = np.asarray(space_values, dtype=float)
        if np.any(space_values <= 0):
            return {c: 0.0 for c in top_categories}
        x_log = np.log10(space_values).reshape(1, -1)
        return {c: 10 ** models[c].predict(x_log)[0] for c in top_categories}

    def predicted_profit(space_values) -> float:
        sales = predicted_sales(space_values)
        return sum(sales[c] * avg_unit_profit[c] for c in top_categories)

    return predicted_sales, predicted_profit


def optimize_assortment(current_space: np.ndarray, predicted_profit, config: AssortmentConfig) -> optimize.OptimizeResult:
    bounds = tuple((config.min_space_pct, config.max_space_pct) for _ in current_space)
    constraint = {"type": "eq", "fun": lambda x: np.sum(x) - config.total_space_pct}
    result = optimize.minimize(
        lambda x: -predicted_profit(x),
        x0=current_space,
        method="SLSQP",
        bounds=bounds,
        constraints=constraint,
        options={"maxiter": 2000, "ftol": 1e-10},
    )
    if not result.success:
        logger.warning("Optimization did not converge cleanly: %s", result.message)
    return result


def save_plot(results: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_df = results.set_index("Category")[["Current_Space_%", "Recommended_Space_%"]]
    fig, ax = plt.subplots(figsize=(9, 6))
    plot_df.plot(kind="bar", ax=ax, color=["#4C72B0", "#DD8452"])
    ax.set_title("Current vs Recommended Assortment Allocation (All Countries)")
    ax.set_ylabel("Assortment Space Proxy (%)")
    ax.set_xlabel("Category")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(output_dir / "assortment_planning_allocation.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "assortment_planning_allocation.png")


def run(config: Config, assortment_config: AssortmentConfig) -> pd.DataFrame:
    raw = load_transactions(config.data_path, country=None)
    clean = clean_transactions(raw)
    clean = clean[clean["category"].notna()].copy()
    clean["GrossProfit"] = (clean["Price"] - clean["Cost"]) * clean["Quantity"]

    top_categories, category_summary = select_top_categories(clean, assortment_config.top_n)
    space_pct, units_sold, model_df = build_weekly_space_and_sales(clean, top_categories)
    models, coefficients_df = fit_category_regressions(space_pct, units_sold, top_categories)
    avg_unit_profit = compute_avg_unit_profit(model_df, top_categories)
    predicted_sales, predicted_profit = make_predictors(models, avg_unit_profit, top_categories)

    current_space = space_pct.mean().reindex(top_categories).values
    current_pred_sales = predicted_sales(current_space)
    current_profit = predicted_profit(current_space)

    optimization = optimize_assortment(current_space, predicted_profit, assortment_config)
    recommended_space = optimization.x
    recommended_pred_sales = predicted_sales(recommended_space)
    recommended_profit = predicted_profit(recommended_space)

    r2_by_category = dict(zip(coefficients_df["Sales_Category"], coefficients_df["R2"]))
    results = pd.DataFrame({
        "Category": top_categories,
        "Current_Space_%": current_space,
        "Recommended_Space_%": recommended_space,
        "Change_pp": recommended_space - current_space,
        "Current_Predicted_Weekly_Units": [current_pred_sales[c] for c in top_categories],
        "Recommended_Predicted_Weekly_Units": [recommended_pred_sales[c] for c in top_categories],
        "Avg_Unit_Profit": [avg_unit_profit[c] for c in top_categories],
        "R2": [r2_by_category[c] for c in top_categories],
    })

    profit_uplift = recommended_profit / current_profit - 1
    logger.info("Current predicted weekly gross profit: %.2f", current_profit)
    logger.info("Optimized predicted weekly gross profit: %.2f", recommended_profit)
    logger.info("Modelled profit uplift: %.2f%%", profit_uplift * 100)
    logger.info("Total recommended space: %.2f%%", recommended_space.sum())

    output_dir = assortment_config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    excel_path = output_dir / "assortment_planning_results.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        category_summary.to_excel(writer, sheet_name="Category Summary", index=False)
        space_pct.reset_index().to_excel(writer, sheet_name="Weekly Space", index=False)
        units_sold.reset_index().to_excel(writer, sheet_name="Weekly Units", index=False)
        coefficients_df.to_excel(writer, sheet_name="Regression", index=False)
        results.to_excel(writer, sheet_name="Optimization", index=False)
    logger.info("Saved %s", excel_path)

    save_plot(results, output_dir)
    logger.info("Results:\n%s", results.round(3).to_string(index=False))
    return results


def main() -> None:
    run(Config(), AssortmentConfig())


if __name__ == "__main__":
    main()
