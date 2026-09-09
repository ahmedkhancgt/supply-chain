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

**A real data mismatch, worked around explicitly rather than silently**:
`data/footfall.xlsx` covers 2016-01-03 to 2020-01-26, while
`data/Data.xlsx`'s transactions cover 2009-12-01 to 2011-12-09 -- these
date ranges do not overlap at all, so joining on real calendar dates
produces zero matched weeks for every one of them. Since footfall is
still needed to compute `conversion_rate` at all, `align_footfall_to_period()`
shifts every footfall date backward by a whole number of weeks (so
Sunday-anchored dates stay Sunday-anchored) until the series brackets the
transaction period. This is a relabeling, not a source of new data: the
213 weekly footfall values and their week-over-week order are completely
unchanged, only the calendar dates attached to them move. The result is
this business's real footfall *pattern* laid over the 2009-2011 window --
**not actual historical footfall for those years**, since no such data
exists. `conversion_rate` computed this way is an illustrative estimate
of what conversion might look like under a plausible footfall pattern,
not a verified historical metric -- the output's `footfall_aligned`
column and the run's log output both flag this. Set
`KPIConfig.align_footfall_to_data=False` to instead see the real,
unmatched (`NaN`-everywhere) join.

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
    # Shift footfall.xlsx's dates onto the transaction data's period so
    # conversion_rate can actually be computed -- see module docstring for
    # exactly what this does and doesn't mean. Set False to see the real,
    # unmatched (NaN-everywhere) join instead.
    align_footfall_to_data: bool = True


def align_footfall_to_period(footfall: pd.DataFrame, period_start: pd.Timestamp) -> tuple[pd.DataFrame, int]:
    """Shifts every date in `footfall` backward by a whole number of weeks
    so its range brackets `period_start` onward. Shifting by a multiple of
    7 days keeps each date on the same day of the week it started on
    (footfall.xlsx is entirely Sundays) -- only the calendar labels move,
    the values and their week-over-week order are untouched. Returns the
    shifted frame and the number of weeks it was shifted by.
    """
    anchor_dow = footfall["date"].dt.dayofweek.iloc[0]
    target_start = period_start - pd.Timedelta(days=(period_start.dayofweek - anchor_dow) % 7)
    offset_weeks = (footfall["date"].min() - target_start).days // 7
    shifted = footfall.copy()
    shifted["date"] = shifted["date"] - pd.Timedelta(weeks=offset_weeks)
    return shifted, offset_weeks


def load_footfall(path: Path, align_to: pd.Timestamp | None = None) -> tuple[pd.DataFrame, bool]:
    footfall = pd.read_excel(path)
    footfall = footfall.rename(columns={"Date": "date", "footfall": "website_visitors"})
    footfall["date"] = pd.to_datetime(footfall["date"]).dt.tz_localize(None)
    raw_start, raw_end = footfall["date"].min(), footfall["date"].max()

    aligned = False
    if align_to is not None:
        footfall, offset_weeks = align_footfall_to_period(footfall, align_to)
        aligned = True
        logger.warning(
            "Shifted footfall.xlsx dates back %d weeks (originally %s to %s -> now %s to "
            "%s) so they overlap the transaction period. This relabels the real footfall "
            "*pattern* onto 2009-2011 dates -- it is NOT actual historical footfall for "
            "those years. Treat conversion_rate as an illustrative estimate, not a "
            "verified historical metric.",
            offset_weeks, raw_start.date(), raw_end.date(), footfall["date"].min().date(), footfall["date"].max().date(),
        )

    iso = footfall["date"].dt.isocalendar()
    footfall["iso_year"] = iso["year"]
    footfall["iso_week"] = iso["week"]
    weekly = footfall.groupby(["iso_year", "iso_week"]).agg(website_visitors=("website_visitors", "sum")).reset_index()
    logger.info(
        "Loaded footfall: %d weekly records, %s to %s",
        len(weekly), footfall["date"].min().date(), footfall["date"].max().date(),
    )
    return weekly, aligned


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


def add_conversion_rate(metrics: pd.DataFrame, footfall_weekly: pd.DataFrame, footfall_aligned: bool) -> pd.DataFrame:
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
    combined["footfall_aligned"] = footfall_aligned

    matched = int(overall["website_visitors"].notna().sum())
    logger.info(
        "Footfall join (All Countries, by iso_year/iso_week): %d of %d weeks matched (footfall_aligned=%s)",
        matched, len(overall), footfall_aligned,
    )
    if matched == 0:
        logger.warning(
            "0 weeks matched -- footfall.xlsx and the transaction data's date range "
            "don't overlap. conversion_rate is NaN for every week until footfall data "
            "covering the same period is supplied, or KPIConfig.align_footfall_to_data "
            "is enabled -- see module docstring.",
        )
    return combined


def log_extremes(metrics: pd.DataFrame) -> None:
    overall = metrics[metrics["Country"] == ALL_COUNTRIES_LABEL]

    if overall["conversion_rate"].notna().any():
        best_conversion = overall.loc[overall["conversion_rate"].idxmax()]
        caveat = " (footfall dates shifted to overlap -- illustrative, not verified historical data)" if overall["footfall_aligned"].iloc[0] else ""
        logger.info(
            "Highest conversion rate week (All Countries): %s (year %d, week %d) -- %.2f%%%s",
            best_conversion["week_start"].date(), best_conversion["iso_year"], best_conversion["iso_week"],
            best_conversion["conversion_rate"] * 100, caveat,
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
    align_to = clean["date"].min() if kpi_config.align_footfall_to_data else None
    footfall_weekly, footfall_aligned = load_footfall(kpi_config.footfall_path, align_to=align_to)
    metrics = add_conversion_rate(metrics, footfall_weekly, footfall_aligned)

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
