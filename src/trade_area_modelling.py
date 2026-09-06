#!/usr/bin/env python3
"""Trade-area / Huff gravity model: which competing store each market's
demand is likely captured by, and how much synthetic market potential
each store is expected to capture.

Adapted from Trade_Area_Modelling.py (uploaded separately, along with
Trade_Area_Synthetic_Inputs.xlsx -- Trade_Area_Census, Store_Attributes,
and Distance_Matrix sheets), which already targeted this repo's
`Trade_Area_ID` column added to `data/Data.xlsx`. Two real issues are
fixed rather than carried over:

1. **The original reads `Data.xlsx` raw, with no cleaning at all.**
   Rebuilt to compute "actual" revenue/customers/invoices per trade area
   from `inventory_planning.clean_transactions()` instead, for the same
   reason every other script in this repo does: it removes duplicates,
   cancelled invoices, and non-product line items. Checked directly:
   this changes `Actual_Revenue`/`Actual_Invoices` for exactly the 4
   trade areas that have a `StockCode == "C2"` ("Carriage" -- a shipping
   charge, not a product) row -- Channel Islands (-$100, invoice count
   unaffected), EIRE (-$1,500, -3 invoices), France (-$110, -1 invoice),
   and United Kingdom (-$700, -2 invoices) -- all under 1.5% of that
   trade area's revenue. The other 37 trade areas are unaffected. This
   keeps "actual demand" here consistent with what the rest of this repo
   counts as a real transaction, rather than trusting the uploaded
   Trade_Area_Census sheet's own (uncleaned) `Actual_Revenue` column.
2. **A fragile-but-currently-correct positional join.** The original
   assumes `Distance_Matrix`'s rows are in the same order as
   `Trade_Area_Census`'s and indexes into it positionally
   (`distance[dcol]` used directly, never merged on a key). Checked
   directly: this dataset's two sheets do happen to be in identical
   `Trade_Area_ID` order, so the original produces the right answer
   here -- but nothing enforces that, and a resorted or reordered
   `Distance_Matrix` would silently misassign every trade area's
   distances with no error raised. Fixed by merging explicitly on
   `(Trade_Area_ID, Country)`.

### Model logic (unchanged from the original -- the classic Huff gravity model)
1. Synthetic market potential per trade area = `Households_SYN x
   Expenditure_Grocery_SYN`.
2. Store attractiveness = sum of each store's 7 characteristics (size,
   parking, highway access, traffic, accessibility, design,
   business-community score), each min-max scaled 0-1 across the
   competing stores first, so no single characteristic's raw units
   (e.g. "square feet" vs. "number of highways") dominates the sum.
3. Huff numerator for (trade area, store) = `attractiveness / distance^2`
   -- a market is drawn to a store more if it's more attractive, and
   less if it's farther away, with distance penalized quadratically.
4. Capture probability = that store's numerator / the sum of every
   competing store's numerator for that trade area -- so each trade
   area's probability always splits 100% across the stores it's
   choosing between.
5. Expected capture = capture probability x that trade area's market
   potential.

Verified against `data/Data.xlsx` and the uploaded
`Trade_Area_Synthetic_Inputs.xlsx`: reproduces the uploaded reference
`Trade_Area_Modelling.xlsx`'s `Huff_Detail` sheet to within ~1 part in a
million (41 trade areas x 3 stores), other than the 4 trade areas'
`Actual_Revenue` described above. That tiny remaining gap is because
this recomputes store attractiveness from the raw
Size/Parking/Highways/.../Business_Communities columns at full
precision -- matching what `Trade_Area_Modelling.py` itself does -- while
the reference workbook was generated from `Store_Attributes`'
`Attractiveness_Scaled` column, which is rounded to 4 decimal places.
Confirmed directly: substituting that rounded column reproduces the
reference numbers exactly. Recomputing from the raw attributes is kept
here as the more robust choice -- it can't silently drift out of sync
with a precomputed column if the raw attributes ever change.
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

from inventory_planning import Config, clean_transactions, load_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("trade_area_modelling")

STORE_ATTRIBUTE_COLUMNS = [
    "Size_SYN", "Parking_Spaces_SYN", "Highways_SYN", "Traffic_SYN",
    "Accessibility_SYN", "Design_SYN", "Business_Communities_SYN",
]


@dataclass(frozen=True)
class TradeAreaConfig:
    synthetic_inputs_path: Path = Path("data/Trade_Area_Synthetic_Inputs.xlsx")
    output_dir: Path = Path("output")


def load_synthetic_inputs(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    census = pd.read_excel(path, sheet_name="Trade_Area_Census")
    stores = pd.read_excel(path, sheet_name="Store_Attributes")
    distance = pd.read_excel(path, sheet_name="Distance_Matrix")
    logger.info(
        "Loaded synthetic inputs: %d trade areas, %d stores", len(census), len(stores),
    )
    return census, stores, distance


def compute_actual_demand(clean: pd.DataFrame) -> pd.DataFrame:
    """Real per-trade-area demand from cleaned transactions -- see module
    docstring for how this differs from the uploaded census sheet's own
    (uncleaned) Actual_Revenue/Actual_Invoices for 4 trade areas.
    """
    actual = (
        clean.groupby(["Trade_Area_ID", "Country"], as_index=False)
        .agg(
            Actual_Revenue=("Revenue", "sum"),
            Actual_Customers=("Customer ID", "nunique"),
            Actual_Invoices=("Invoice", "nunique"),
        )
    )
    return actual


def compute_store_attractiveness(stores: pd.DataFrame) -> pd.DataFrame:
    """Min-max scales each of the 7 raw attribute columns across the
    competing stores (0-1), then sums them into one Attractiveness score.
    """
    stores = stores.copy()
    attrs = stores[STORE_ATTRIBUTE_COLUMNS]
    scaled = (attrs - attrs.min()) / (attrs.max() - attrs.min())
    stores["Attractiveness"] = scaled.fillna(0).sum(axis=1)
    logger.info(
        "Store attractiveness:\n%s",
        stores[["Store_ID", "Store", "Attractiveness"]].to_string(index=False),
    )
    return stores


def compute_huff_allocation(census: pd.DataFrame, stores: pd.DataFrame, distance: pd.DataFrame, actual: pd.DataFrame) -> pd.DataFrame:
    """The Huff gravity allocation: capture probability and expected
    demand capture per (trade area, store).

    Joins `distance` onto `census` explicitly on (Trade_Area_ID,
    Country) rather than assuming matching row order -- see module
    docstring.
    """
    store_ids = stores["Store_ID"].tolist()
    huff = census[["Trade_Area_ID", "Country", "Market_Potential_SYN"]].merge(
        distance, on=["Trade_Area_ID", "Country"], how="left"
    )
    missing_distance = huff[[f"Distance_{sid}_SYN" for sid in store_ids]].isna().any(axis=1).sum()
    if missing_distance:
        logger.warning("%d trade areas have no matching Distance_Matrix row -- Huff allocation will be NaN for them", missing_distance)

    numerators = {}
    for store_id in store_ids:
        attractiveness = stores.loc[stores["Store_ID"].eq(store_id), "Attractiveness"].iloc[0]
        numerators[f"Numerator_{store_id}"] = attractiveness / (huff[f"Distance_{store_id}_SYN"].astype(float) ** 2)
        huff = huff.rename(columns={f"Distance_{store_id}_SYN": f"Distance_{store_id}"})

    numerator_df = pd.DataFrame(numerators)
    denominator = numerator_df.sum(axis=1)

    for store_id in store_ids:
        huff[f"Numerator_{store_id}"] = numerator_df[f"Numerator_{store_id}"]
        huff[f"P_{store_id}"] = numerator_df[f"Numerator_{store_id}"] / denominator
        huff[f"Expected_{store_id}"] = huff[f"P_{store_id}"] * huff["Market_Potential_SYN"]

    huff = huff.merge(actual[["Trade_Area_ID", "Country", "Actual_Revenue"]], on=["Trade_Area_ID", "Country"], how="left")

    logger.info(
        "Total expected capture by store:\n%s",
        pd.Series({sid: huff[f"Expected_{sid}"].sum() for sid in store_ids}).to_string(),
    )
    return huff


def save_plot(huff: pd.DataFrame, store_ids: list[str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_totals = pd.Series({sid: huff[f"Expected_{sid}"].sum() for sid in store_ids})

    fig, ax = plt.subplots(figsize=(7, 5))
    expected_totals.plot(kind="bar", ax=ax, color="#4C72B0")
    ax.set_title("Total Expected Demand Capture by Store")
    ax.set_ylabel("Expected capture (synthetic market potential units)")
    ax.set_xlabel("Store")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(output_dir / "trade_area_expected_capture.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "trade_area_expected_capture.png")


def build_executive_summary(census: pd.DataFrame, stores: pd.DataFrame, huff: pd.DataFrame, config: TradeAreaConfig) -> pd.DataFrame:
    store_ids = stores["Store_ID"].tolist()
    rows = [
        ("Trade Areas", len(census)),
        ("Join Key", "Trade_Area_ID"),
        ("Synthetic Input File", config.synthetic_inputs_path.name),
        ("Total Synthetic Market Potential", census["Market_Potential_SYN"].sum()),
    ]
    for store_id in store_ids:
        store_name = stores.loc[stores["Store_ID"].eq(store_id), "Store"].iloc[0]
        rows.append((f"Expected Capture - {store_name}", huff[f"Expected_{store_id}"].sum()))
    return pd.DataFrame(rows, columns=["Trade Area Modelling Summary", "Value"])


def run(config: Config, trade_area_config: TradeAreaConfig) -> pd.DataFrame:
    raw = load_transactions(config.data_path, country=None)
    clean = clean_transactions(raw)

    census, stores, distance = load_synthetic_inputs(trade_area_config.synthetic_inputs_path)
    actual = compute_actual_demand(clean)
    stores = compute_store_attractiveness(stores)
    huff = compute_huff_allocation(census, stores, distance, actual)

    summary = build_executive_summary(census, stores, huff, trade_area_config)
    logger.info("Executive summary:\n%s", summary.to_string(index=False))

    output_dir = trade_area_config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    excel_path = output_dir / "trade_area_modelling_results.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        summary.to_excel(writer, sheet_name="Executive_Summary", index=False)
        huff.to_excel(writer, sheet_name="Huff_Detail", index=False)
        census.to_excel(writer, sheet_name="Trade_Area_Census", index=False)
        stores.to_excel(writer, sheet_name="Store_Attributes", index=False)
        distance.to_excel(writer, sheet_name="Distance_Matrix", index=False)
    logger.info("Saved %s", excel_path)

    save_plot(huff, stores["Store_ID"].tolist(), output_dir)

    logger.info(
        "Top 10 trade areas by market potential:\n%s",
        huff.sort_values("Market_Potential_SYN", ascending=False)
        .head(10)[["Trade_Area_ID", "Country", "Market_Potential_SYN", "Actual_Revenue"]]
        .to_string(index=False),
    )
    return huff


def main() -> None:
    run(Config(), TradeAreaConfig())


if __name__ == "__main__":
    main()
