#!/usr/bin/env python3
"""Safety-stock, reorder-point, and order-quantity planning pipeline.

Loads cleaned order history for a country, classifies each product into a
volume/revenue mix (ABC analysis), computes reorder points and safety
stock under two demand models (a fixed lead time, and a lead time that is
itself uncertain), and computes each product's economic order quantity
(EOQ) — how much to order each time, complementing the reorder point's
answer of when to order. Results and summary charts are written to
OUTPUT_DIR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import inventorize3 as inv
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import norm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("inventory_planning")

# Administrative line items in this dataset (postage, manual adjustments,
# bank charges, etc.) share the transaction schema but aren't stockable
# products, so they must not appear in a reorder plan.
NON_PRODUCT_STOCK_CODES = {"POST", "M", "MANUAL", "D", "DOT", "BANK CHARGES", "C2", "PADS", "CRUK", "AMAZONFEE", "S"}

DEFAULT_SERVICE_LEVEL_MAP = {
    "A_A": 0.95, "A_B": 0.95, "A_C": 0.95,
    "B_A": 0.70, "B_B": 0.70, "B_C": 0.75,
    "C_A": 0.80, "C_B": 0.80, "C_C": 0.70,
}


# Columns Data.xlsx carries per-transaction that a source might not have.
# extract_supply_parameters() averages each per SKU when the column is
# present, and falls back independently -- one field at a time, not
# all-or-nothing -- to the matching Config placeholder when it's missing,
# so a source with only some of these still works.
SUPPLY_PARAM_COLUMNS = {
    "lead_time_days": "lead_time_days",
    "lead_time_sd_days": "lead_time_sd_days",
    "ordering_cost_per_order": "ordering_cost_per_order",
    "holding_rate": "holding_rate",
}


@dataclass(frozen=True)
class Config:
    data_path: Path = Path("data/Data.xlsx")
    output_dir: Path = Path("output")
    country: str = "Germany"
    analysis_window_months: int = 4
    default_service_level: float = 0.75
    service_level_map: dict = field(default_factory=lambda: dict(DEFAULT_SERVICE_LEVEL_MAP))
    # Fallback values, used only for a SKU/source missing the matching real
    # column (lead_time_days, lead_time_sd_days, ordering_cost_per_order,
    # holding_rate, Cost). Data.xlsx supplies all of these except for the
    # newsvendor salvage/penalty inputs in advanced_analytics.py, which
    # remain placeholders regardless.
    lead_time_days: float = 12
    lead_time_sd_days: float = 2
    ordering_cost_per_order: float = 50.0
    holding_rate: float = 0.20


def load_transactions(path: Path, country: str | None = None) -> pd.DataFrame:
    logger.info("Loading transactions from %s", path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    if country:
        df = df[df["Country"] == country]
    logger.info("Loaded %d raw rows for country=%s", len(df), country)
    return df


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates()
    df = df.dropna(subset=["Invoice", "Description", "Quantity", "InvoiceDate", "Price"])
    df = df[~df["Invoice"].astype(str).str.startswith("C")]
    df = df[~df["StockCode"].astype(str).str.upper().isin(NON_PRODUCT_STOCK_CODES)]
    df = df[(df["Quantity"] > 0) & (df["Price"] > 0)]
    df = df.copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["date"] = df["InvoiceDate"].dt.normalize()
    logger.info(
        "Cleaned transactions: %d -> %d rows (%d dropped as duplicates, "
        "cancellations, or non-positive qty/price)",
        before, len(df), before - len(df),
    )
    return df


def extract_supply_parameters(clean: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Per-SKU lead time, cost, and holding-rate parameters, plus a real
    per-unit cost when the source has one.

    Data.xlsx carries lead_time_days/lead_time_sd_days/ordering_cost_per_
    order/holding_rate/Cost as per-transaction columns -- not perfectly
    constant per SKU (a handful of products show 2-6 distinct
    lead_time_days values across their rows), so each is averaged per SKU
    here rather than looked up per row. A source lacking one of these
    columns falls back to Config's flat placeholder for that field alone
    -- each column is independent, so a source with only some of them
    still gets real data for the rest.

    unit_cost feeds anything that values inventory at what it cost to buy
    rather than what it sells for (EOQ's holding-cost basis, safety-stock
    investment) -- falls back to avg_unit_price (selling price) when there's
    no real Cost column, which is what this pipeline used unconditionally
    before Data.xlsx existed.
    """
    descriptions = clean[["Description"]].drop_duplicates()
    params = descriptions.copy()

    for field_name, column in SUPPLY_PARAM_COLUMNS.items():
        default = getattr(config, field_name)
        if column in clean.columns:
            per_sku = clean.groupby("Description")[column].mean()
            params[field_name] = params["Description"].map(per_sku)
            logger.info(
                "%s: real per-SKU data from column '%s' (mean %.3g, range %.3g-%.3g)",
                field_name, column, per_sku.mean(), per_sku.min(), per_sku.max(),
            )
        else:
            params[field_name] = default
            logger.info(
                "%s: column '%s' not in source data; using Config placeholder %.3g for every SKU",
                field_name, column, default,
            )

    if "Cost" in clean.columns:
        per_sku_cost = clean.groupby("Description")["Cost"].mean()
        params["unit_cost"] = params["Description"].map(per_sku_cost)
        params["unit_cost_is_real"] = True
        logger.info("unit_cost: real per-SKU data from column 'Cost'")
    else:
        params["unit_cost"] = np.nan  # filled in from avg_unit_price once merged (see run())
        params["unit_cost_is_real"] = False
        logger.info("unit_cost: no 'Cost' column in source data; will fall back to avg_unit_price per SKU")

    return params


def filter_recent_window(df: pd.DataFrame, months: int) -> pd.DataFrame:
    max_date = df["date"].max()
    cutoff = max_date - pd.DateOffset(months=months)
    windowed = df[df["date"] > cutoff].copy()
    windowed["revenue"] = windowed["Quantity"] * windowed["Price"]
    logger.info(
        "Analysis window: %s to %s (%d rows, most recent %d months)",
        cutoff.date(), max_date.date(), len(windowed), months,
    )
    return windowed


def daily_product_sales(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["date", "Description"])
        .agg(total_daily=("Quantity", "sum"), total_revenue=("revenue", "sum"))
        .reset_index()
    )


def product_stats(daily: pd.DataFrame) -> pd.DataFrame:
    stats = (
        daily.groupby("Description")
        .agg(
            average=("total_daily", "mean"),
            sd=("total_daily", "std"),
            total_sales=("total_daily", "sum"),
            total_revenue=("total_revenue", "sum"),
        )
        .reset_index()
    )
    no_variance = stats["sd"].isna().sum()
    if no_variance:
        logger.warning(
            "%d products sold on only one day in the window; treating their "
            "demand as constant (sd=0) rather than unknown.",
            no_variance,
        )
    stats["sd"] = stats["sd"].fillna(0.0)
    stats["avg_unit_price"] = stats["total_revenue"] / stats["total_sales"]
    return stats


def classify_products(stats: pd.DataFrame, service_level_map: dict, default_service_level: float) -> pd.DataFrame:
    mix = inv.productmix(stats["Description"], stats["total_sales"], stats["total_revenue"])
    mix = mix.rename(columns={"skus": "Description"})

    unmapped = set(mix["product_mix"]) - set(service_level_map)
    if unmapped:
        logger.warning(
            "No service-level target defined for classes %s; falling back to %.2f",
            sorted(unmapped), default_service_level,
        )
    mix["service_level"] = mix["product_mix"].map(service_level_map).fillna(default_service_level)

    logger.info("Product mix distribution:\n%s", mix["product_mix"].value_counts().to_string())
    return pd.merge(stats, mix[["Description", "product_mix", "service_level"]], on="Description", how="left")


def compute_reorder_points(df: pd.DataFrame) -> pd.DataFrame:
    """Requires df to already have (per-SKU) average, sd, service_level,
    lead_time_days, lead_time_sd_days, and unit_cost -- see
    extract_supply_parameters().
    """
    df = df.copy()
    lead_time_days = df["lead_time_days"]
    lead_time_sd_days = df["lead_time_sd_days"]
    demand_lead_time = df["average"] * lead_time_days
    safety_factor = norm.ppf(df["service_level"])

    sigma_dl_fixed = df["sd"] * np.sqrt(lead_time_days)
    df["safety_stock_fixed_leadtime"] = safety_factor * sigma_dl_fixed
    df["reorder_point_fixed_leadtime"] = demand_lead_time + df["safety_stock_fixed_leadtime"]

    # inventorize3.reorderpoint_leadtime_variability() has a bug: it computes
    # `sd_leadtime_days ^ 2` (bitwise XOR) instead of `** 2`, which silently
    # understates safety stock and only avoids crashing when every input
    # happens to be an int. Computing the standard combined demand/lead-time
    # variance formula directly here instead of calling that function.
    sigma_dl_variable = np.sqrt(
        lead_time_days * df["sd"] ** 2 + df["average"] ** 2 * lead_time_sd_days ** 2
    )
    df["safety_stock_variable_leadtime"] = safety_factor * sigma_dl_variable
    df["reorder_point_variable_leadtime"] = demand_lead_time + df["safety_stock_variable_leadtime"]

    df["demand_lead_time"] = demand_lead_time
    df["safety_stock_uplift_pct"] = np.where(
        df["safety_stock_fixed_leadtime"] > 0,
        (df["safety_stock_variable_leadtime"] / df["safety_stock_fixed_leadtime"] - 1) * 100,
        np.nan,
    )
    # Valued at what the unit cost to acquire (real Cost data when available,
    # selling price otherwise) -- capital tied up in safety stock, not the
    # unrealized margin on it.
    df["safety_stock_investment"] = df["safety_stock_variable_leadtime"] * df["unit_cost"]
    return df


def compute_eoq(df: pd.DataFrame) -> pd.DataFrame:
    """Requires df to already have (per-SKU) average, unit_cost,
    ordering_cost_per_order, and holding_rate -- see
    extract_supply_parameters().
    """
    df = df.copy()
    df["annual_demand"] = df["average"] * 365
    ordering_cost_per_order = df["ordering_cost_per_order"]
    holding_rate = df["holding_rate"]

    holding_cost_per_unit = holding_rate * df["unit_cost"]
    order_cycle_years = np.sqrt(
        2 * ordering_cost_per_order / (df["annual_demand"] * holding_cost_per_unit)
    )
    df["eoq_units"] = order_cycle_years * df["annual_demand"]
    df["eoq_order_cycle_weeks"] = order_cycle_years * 52

    # Round the order cycle to the nearest power-of-two weeks (1, 2, 4, 8, ...)
    # -- a standard practical simplification: EOQ's cost curve is flat near its
    # minimum, so rounding to an operationally convenient cycle costs little,
    # per inventorize3.TQpractical (verified correct; unlike
    # reorderpoint_leadtime_variability, no bug in this one).
    practical_cycle_weeks = 2 ** np.round(np.log(df["eoq_order_cycle_weeks"] / np.sqrt(2)) / np.log(2))
    df["eoq_practical_units"] = practical_cycle_weeks / 52 * df["annual_demand"]

    df["annual_ordering_cost"] = (df["annual_demand"] / df["eoq_units"]) * ordering_cost_per_order
    df["annual_holding_cost"] = (df["eoq_units"] / 2) * holding_cost_per_unit
    df["annual_logistics_cost"] = (
        df["annual_ordering_cost"] + df["annual_holding_cost"] + df["unit_cost"] * df["annual_demand"]
    )
    return df


def evaluate_quantity_discount(
    annual_demand: float,
    unit_price: float,
    ordering_cost_per_order: float,
    holding_rate: float,
    discount_quantity: float,
    discount_pct: float,
) -> dict:
    """Compare total annual cost at EOQ vs. at a supplier's discounted order
    quantity, for one product. Not run automatically over every SKU -- call
    this manually when a real discount offer (quantity + %) comes in, since
    that isn't something present in the transaction data.
    """
    holding_cost_per_unit = holding_rate * unit_price
    eoq_units = np.sqrt(2 * annual_demand * ordering_cost_per_order / holding_cost_per_unit)
    cost_at_eoq = (
        (annual_demand / eoq_units) * ordering_cost_per_order
        + (eoq_units / 2) * holding_cost_per_unit
        + unit_price * annual_demand
    )

    discounted_price = unit_price * (1 - discount_pct)
    cost_at_discount = (
        (annual_demand / discount_quantity) * ordering_cost_per_order
        + (discount_quantity / 2) * (holding_rate * discounted_price)
        + discounted_price * annual_demand
    )

    return {
        "eoq_units": eoq_units,
        "cost_at_eoq": cost_at_eoq,
        "cost_at_discount_quantity": cost_at_discount,
        "accept_discount": cost_at_discount < cost_at_eoq,
        "annual_savings": cost_at_eoq - cost_at_discount,
    }


def build_summary(df: pd.DataFrame) -> dict:
    return {
        "skus_analyzed": len(df),
        "window_revenue": round(df["total_revenue"].sum(), 2),
        "total_safety_stock_units_fixed_leadtime": round(df["safety_stock_fixed_leadtime"].sum(), 1),
        "total_safety_stock_units_variable_leadtime": round(df["safety_stock_variable_leadtime"].sum(), 1),
        "avg_safety_stock_uplift_pct_from_leadtime_variability": round(
            df["safety_stock_uplift_pct"].replace([np.inf, -np.inf], np.nan).mean(), 1
        ),
        "safety_stock_investment_at_cost": round(df["safety_stock_investment"].sum(), 2),
        "total_annual_ordering_and_holding_cost": round(
            (df["annual_ordering_cost"] + df["annual_holding_cost"]).sum(), 2
        ),
    }


def _trim_for_plot(df: pd.DataFrame, column: str, upper_percentile: float = 0.99) -> pd.DataFrame:
    cap = df[column].quantile(upper_percentile)
    return df[df[column] <= cap]


def save_plots(df: pd.DataFrame, output_dir: Path, country: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_df = _trim_for_plot(df, "safety_stock_variable_leadtime")

    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(data=plot_df, x="sd", y="safety_stock_variable_leadtime", hue="service_level", ax=ax)
    ax.set_title(f"Safety Stock vs Demand Variability ({country})")
    ax.set_xlabel("Daily demand standard deviation (units)")
    ax.set_ylabel("Safety stock (units, lead-time variability model)")
    fig.tight_layout()
    fig.savefig(output_dir / "safety_stock_vs_variability.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    df["product_mix"].value_counts().sort_index().plot(kind="bar", ax=ax, color="#4C72B0")
    ax.set_title(f"Product Mix (ABC by volume x revenue) - {country}")
    ax.set_xlabel("Class")
    ax.set_ylabel("Number of SKUs")
    fig.tight_layout()
    fig.savefig(output_dir / "product_mix_distribution.png", dpi=150)
    plt.close(fig)

    logger.info("Saved charts to %s", output_dir)


def save_outputs(df: pd.DataFrame, summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ranked = df.sort_values("safety_stock_investment", ascending=False)

    csv_path = output_dir / "reorder_recommendations.csv"
    ranked.to_csv(csv_path, index=False)

    excel_path = output_dir / "inventory_report.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        ranked.to_excel(writer, sheet_name="Reorder Recommendations", index=False)
        pd.DataFrame([summary]).T.rename(columns={0: "value"}).to_excel(
            writer, sheet_name="Executive Summary"
        )

    logger.info("Saved %s and %s", csv_path, excel_path)


def run(config: Config) -> pd.DataFrame:
    raw = load_transactions(config.data_path, country=config.country)
    clean = clean_transactions(raw)
    windowed = filter_recent_window(clean, config.analysis_window_months)
    daily = daily_product_sales(windowed)
    stats = product_stats(daily)
    classified = classify_products(stats, config.service_level_map, config.default_service_level)

    # extract_supply_parameters() runs on the full cleaned history (not just
    # the analysis window) since lead time/cost are supplier attributes, not
    # a demand outcome -- more rows to average over, and no reason to
    # restrict them to the same recent-sales window as `average`/`sd`.
    supply_params = extract_supply_parameters(clean, config)
    merged = pd.merge(classified, supply_params, on="Description", how="left")
    merged["unit_cost"] = merged["unit_cost"].where(merged["unit_cost_is_real"], merged["avg_unit_price"])

    reorder = compute_reorder_points(merged)
    reorder = compute_eoq(reorder)

    summary = build_summary(reorder)
    logger.info("Executive summary: %s", summary)

    save_plots(reorder, config.output_dir, config.country)
    save_outputs(reorder, summary, config.output_dir)
    return reorder


def main() -> None:
    run(Config())


if __name__ == "__main__":
    main()
