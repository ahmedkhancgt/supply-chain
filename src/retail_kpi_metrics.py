#!/usr/bin/env python3
"""Weekly retail KPIs: conversion rate, average transaction value (ATV),
units per transaction (UPT), and average selling price (ASP).

Adapted from section2.py (uploaded separately), which read a
`retail_clean.csv` this repo doesn't have and restricted every metric to
the UK only. Rebuilt on the same cleaned transaction data
`inventory_planning.py` already loads, and computes every metric for
**every country** in `data/Data.xlsx`, not just one -- both a combined
"All Countries" total (the direct generalization of the original's
single UK series) and a per-country breakdown, since this repo has
already found real cross-country differences worth surfacing (see
`supplier_segmentation.py`'s cross-country product mix).

Two real issues from the original are fixed rather than carried over:

1. **Joining on raw resampled calendar dates.** The original computes
   `uk_weekly` and `footfall_weekly` as two independently-`resample('W')`-d
   series and merges on the resulting `date` column. This is fragile: two
   series resampled from different starting dates can anchor their
   "week" boundaries on different days, so even genuinely overlapping
   data can silently fail to join -- with nothing to explain why the
   result came back all `NaN`. Fixed by keying both sides on
   `(iso_year, iso_week)` instead, which doesn't depend on which day of
   the week either series happened to start counting from.
2. **A convoluted invoice count.**
   `uk.groupby(['date','Invoice']).agg(n_invoices=('Invoice','count')).reset_index().groupby('date').agg(n_invoices=('Invoice','count'))`
   counts rows per (date, Invoice) group only to immediately throw that
   count away and count the number of groups instead -- equivalent to,
   and replaced with, a single `nunique()`.

**A real finding, not a bug**: `data/footfall.xlsx` covers 2016-01-03 to
2020-01-26, while `data/Data.xlsx`'s transactions cover 2009-12-01 to
2011-12-09 -- these date ranges do not overlap at all. Checked directly:
the `(iso_year, iso_week)` join between the two produces zero matched
weeks, so `conversion_rate` and `website_visitors` are `NaN` for every
row in the output. This isn't a code bug to work around -- it's a real
mismatch between the two source files that no join logic can paper over.
`website_visitors`/`conversion_rate` are still computed and left in the
output (rather than silently dropped) so this is visible rather than
hidden; ATV/UPT/ASP don't depend on footfall and are unaffected.

`footfall.xlsx` also carries no country breakdown (a single combined
series, unlike the original's UK-specific `footfall_uk.xlsx`), so
conversion rate is only ever computed at the "All Countries" grain --
there's no way to allocate one undifferentiated footfall number across
countries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from inventory_planning import Config, clean_transactions, load_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("retail_kpi_metrics")

ALL_COUNTRIES_LABEL = "All Countries"


@dataclass(frozen=True)
class KPIConfig:
    footfall_path: Path = Path("data/footfall.xlsx")
    output_dir: Path = Path("output")


def load_footfall(path: Path) -> pd.DataFrame:
    footfall = pd.read_excel(path)
    footfall = footfall.rename(columns={"Date": "date", "footfall": "website_visitors"})
    footfall["date"] = pd.to_datetime(footfall["date"]).dt.tz_localize(None)
    iso = footfall["date"].dt.isocalendar()
    footfall["iso_year"] = iso["year"]
    footfall["iso_week"] = iso["week"]
    weekly = footfall.groupby(["iso_year", "iso_week"]).agg(website_visitors=("website_visitors", "sum")).reset_index()
    logger.info(
        "Loaded footfall: %d weekly records, %s to %s",
        len(weekly), footfall["date"].min().date(), footfall["date"].max().date(),
    )
    return weekly


def weekly_transaction_metrics(clean: pd.DataFrame) -> pd.DataFrame:
    """Weekly (ISO year+week) ATV, UPT, and ASP for every country, plus a
    combined 'All Countries' row per week.
    """
    df = clean.copy()
    df["revenue"] = df["Quantity"] * df["Price"]
    iso = df["date"].dt.isocalendar()
    df["iso_year"] = iso["year"]
    df["iso_week"] = iso["week"]

    per_invoice = (
        df.groupby(["Country", "iso_year", "iso_week", "Invoice"])
        .agg(revenue=("revenue", "sum"), units=("Quantity", "sum"), week_start=("date", "min"))
        .reset_index()
    )

    def summarize(group_cols: list[str]) -> pd.DataFrame:
        summary = per_invoice.groupby(group_cols).agg(
            week_start=("week_start", "min"),
            n_invoices=("Invoice", "nunique"),
            ATV=("revenue", "mean"),
            UPT=("units", "mean"),
        ).reset_index()
        summary["ASP"] = summary["ATV"] / summary["UPT"]
        return summary

    by_country = summarize(["Country", "iso_year", "iso_week"])

    overall = summarize(["iso_year", "iso_week"])
    overall.insert(0, "Country", ALL_COUNTRIES_LABEL)

    metrics = pd.concat([overall, by_country], ignore_index=True)
    logger.info(
        "Weekly metrics: %d countries, %d country-weeks (plus %d '%s' weeks)",
        clean["Country"].nunique(), len(by_country), len(overall), ALL_COUNTRIES_LABEL,
    )
    return metrics


def add_conversion_rate(metrics: pd.DataFrame, footfall_weekly: pd.DataFrame) -> pd.DataFrame:
    """Joins footfall onto the 'All Countries' rows only -- footfall.xlsx
    has no per-country breakdown, so it can't be allocated to individual
    countries (see module docstring).
    """
    is_overall = metrics["Country"] == ALL_COUNTRIES_LABEL
    overall = pd.merge(metrics[is_overall], footfall_weekly, on=["iso_year", "iso_week"], how="left")
    rest = metrics[~is_overall].copy()
    rest["website_visitors"] = pd.NA

    combined = pd.concat([overall, rest], ignore_index=True)
    combined["conversion_rate"] = combined["n_invoices"] / combined["website_visitors"]

    matched = int(overall["website_visitors"].notna().sum())
    logger.info(
        "Footfall join (All Countries, by iso_year/iso_week): %d of %d weeks matched", matched, len(overall),
    )
    if matched == 0:
        logger.warning(
            "0 weeks matched -- footfall.xlsx (%s to %s) and the transaction data's "
            "date range don't overlap at all. conversion_rate is NaN for every week "
            "until footfall data covering the same period is supplied -- see module docstring.",
            footfall_weekly.assign(
                d=pd.to_datetime(footfall_weekly["iso_year"].astype(str) + "-W" + footfall_weekly["iso_week"].astype(str) + "-1", format="%G-W%V-%u")
            )["d"].min().date(),
            footfall_weekly.assign(
                d=pd.to_datetime(footfall_weekly["iso_year"].astype(str) + "-W" + footfall_weekly["iso_week"].astype(str) + "-1", format="%G-W%V-%u")
            )["d"].max().date(),
        )
    return combined


def log_extremes(metrics: pd.DataFrame) -> None:
    overall = metrics[metrics["Country"] == ALL_COUNTRIES_LABEL]

    if overall["conversion_rate"].notna().any():
        best_conversion = overall.loc[overall["conversion_rate"].idxmax()]
        logger.info(
            "Highest conversion rate week (All Countries): %s (year %d, week %d) -- %.2f%%",
            best_conversion["week_start"].date(), best_conversion["iso_year"], best_conversion["iso_week"],
            best_conversion["conversion_rate"] * 100,
        )
    else:
        logger.info("Highest conversion rate week: undefined -- conversion_rate is NaN for every week (see above)")

    best_atv = overall.loc[overall["ATV"].idxmax()]
    worst_upt = overall.loc[overall["UPT"].idxmin()]
    worst_asp = overall.loc[overall["ASP"].idxmin()]
    logger.info(
        "Highest ATV week (All Countries): %s -- %.2f", best_atv["week_start"].date(), best_atv["ATV"],
    )
    logger.info(
        "Lowest UPT week (All Countries): %s -- %.2f", worst_upt["week_start"].date(), worst_upt["UPT"],
    )
    logger.info(
        "Lowest ASP week (All Countries): %s -- %.2f", worst_asp["week_start"].date(), worst_asp["ASP"],
    )


def run(config: Config, kpi_config: KPIConfig) -> pd.DataFrame:
    raw = load_transactions(config.data_path, country=None)
    clean = clean_transactions(raw)

    metrics = weekly_transaction_metrics(clean)
    footfall_weekly = load_footfall(kpi_config.footfall_path)
    metrics = add_conversion_rate(metrics, footfall_weekly)

    log_extremes(metrics)

    output_dir = kpi_config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "retail_kpi_metrics.csv"
    metrics.sort_values(["Country", "iso_year", "iso_week"]).to_csv(csv_path, index=False)
    logger.info("Saved %s", csv_path)

    return metrics


def main() -> None:
    run(Config(), KPIConfig())


if __name__ == "__main__":
    main()
