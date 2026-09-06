#!/usr/bin/env python3
"""Hybrid 12-week SKU demand forecasting: a classical statistical/
intermittent-demand suite competing against a machine-learning panel
model, per SKU, with the better backtested one winning.

Adapted from Forecasting_PyCaret_Hybrid.py (uploaded separately, along
with reference output CSVs/xlsx from a prior run). Two substitutions
from the original, both already precedented by the uploaded reference
file's own "Methodology" sheet, which notes its numbers were produced
the same way: "PyCaret could not be installed in this runtime, so the
completed benchmark used the same underlying LightGBM / scikit-learn
algorithms and identical feature/holdout logic."

1. **No PyCaret.** `pycaret[full]` pulls in a large, fast-moving
   dependency tree this repo doesn't otherwise need (every other model
   here runs on pandas/numpy/scipy/scikit-learn already in
   requirements.txt). Rebuilt to fit `HistGradientBoostingRegressor`,
   `RandomForestRegressor`, and `Ridge` directly -- three
   directly-comparable estimators standing in for the original's
   `compare_models(include=["lightgbm","xgboost","et","rf","gbr","ridge"])`
   shortlist, backtested and picked by MAE exactly like the original's
   PyCaret-wrapped models were. `lightgbm` isn't installed here either
   (the reference run substituted it with `HistGradientBoostingRegressor`
   for the same reason), so this keeps the same substitution.
2. **No separate "Version 1" statistical script.** The original expects
   `_forecast_summary.csv`/`_forecast_detail.csv` from a companion
   script this repo doesn't have. Rebuilt directly here: `Naive`,
   4- and 8-week moving averages, simple exponential smoothing,
   52-week seasonal naive, and Croston's method (classic and the SBA
   bias-corrected variant) and TSB -- the same seven-method family named
   in the reference `Hybrid_SKU_Model_Comparison.csv`'s `Champion_Model`
   column, implemented directly from their standard formulas rather than
   a hidden dependency.

One real, verified issue fixed rather than carried over: the original's
`History_Weeks`/`Positive_Weeks`/ADI are computed against the full
106-week panel for every SKU, regardless of when that SKU actually
started selling -- checked directly against `data/Data.xlsx`: 502 of
3,080 SKUs (16%) don't appear until more than a year into the panel, so
crediting them with a 106-week "history" materially overstates how
lumpy/intermittent their demand looks (a SKU selling 3 of its own first
16 weeks gets ADI = 106/3 = 35.3 -- "extremely lumpy" -- instead of the
16/3 = 5.3 its own actual selling window would show). Fixed by measuring
each SKU's history from its own first sale week through the end of the
panel.

### Model logic
1. Build a weekly (Monday-start) SKU x week demand panel, keyed by
   `StockCode` (not `Description` -- unlike the rest of this repo,
   `StockCode` is the finer-grained key here: 3,081 distinct codes vs.
   3,037 descriptions, with 30 descriptions covering more than one
   StockCode).
2. Classify each SKU's demand pattern (smooth/intermittent/erratic/
   lumpy, via ADI/CV², Syntetos-Boylan-Croston) over its own selling
   window.
3. Backtest 7 classical methods and 3 ML candidates against the last
   `HOLDOUT_WEEKS` weeks of real demand; pick each side's per-SKU
   champion by MAE, then pick the overall winner between the two sides.
4. Refit the winning approach per SKU on full history and produce a
   `FORECAST_HORIZON`-week forecast, converted to revenue and gross
   profit using that SKU's average price and cost.

Verified end-to-end against `data/Data.xlsx` (all countries, 3,081
SKUs) -- see README.md for the resulting win-rate split and forecast
totals, benchmarked against the uploaded reference run's own numbers.
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
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge

from inventory_planning import Config, clean_transactions, load_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("hybrid_forecasting")

HOLDOUT_WEEKS = 12
FORECAST_HORIZON = 12
MIN_WEEKS_FOR_BACKTEST = 4
SEASONAL_LAG = 52
RANDOM_STATE = 42

ADI_THRESHOLD = 1.34
CV2_THRESHOLD = 0.49

LAGS = [1, 2, 4, 8, 13, 26, 52]
ROLL_WINDOWS = [4, 8, 13, 26]

ML_MODEL_FACTORIES = {
    "HistGBR": lambda: HistGradientBoostingRegressor(max_iter=200, random_state=RANDOM_STATE),
    "RandomForest": lambda: RandomForestRegressor(n_estimators=200, max_depth=12, n_jobs=-1, random_state=RANDOM_STATE),
    "Ridge": lambda: Ridge(alpha=1.0, random_state=RANDOM_STATE),
}


@dataclass(frozen=True)
class ForecastConfig:
    output_dir: Path = Path("output")


# --------------------------------------------------------------------------
# Panel construction
# --------------------------------------------------------------------------

def load_weekly_panel(clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str], pd.DatetimeIndex]:
    df = clean.copy()
    df["StockCode"] = df["StockCode"].astype(str)
    df["Week"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")

    weekly = df.groupby(["StockCode", "Week"], as_index=False).agg(Quantity=("Quantity", "sum"))

    meta = (
        df.sort_values("InvoiceDate")
        .groupby("StockCode", as_index=False)
        .agg(
            Description=("Description", "last"),
            Category=("category", "last"),
            Subcategory=("subcategory", "last"),
            Supplier=("supplier", "last"),
            Avg_Price=("Price", "mean"),
            Avg_Cost=("Cost", "mean"),
            Lead_Time_Days=("lead_time_days", "mean"),
            Lead_Time_SD_Days=("lead_time_sd_days", "mean"),
        )
    )

    skus = meta["StockCode"].tolist()
    weeks = pd.date_range(weekly["Week"].min(), weekly["Week"].max(), freq="W-MON")

    y = (
        weekly.pivot(index="Week", columns="StockCode", values="Quantity")
        .reindex(index=weeks, columns=skus)
        .fillna(0.0)
        .astype(float)
    )

    meta = meta.set_index("StockCode").reindex(skus)
    for col in ["Category", "Subcategory", "Supplier"]:
        meta[col] = meta[col].fillna("Unknown").astype(str)
        meta[col + "_code"] = pd.Categorical(meta[col]).codes.astype(int)
    meta["SKU_code"] = np.arange(len(meta), dtype=int)

    first_sale_idx = (y.values > 0).argmax(axis=0)
    never_sold = (y.values > 0).sum(axis=0) == 0
    first_sale_idx[never_sold] = len(weeks)
    meta["first_sale_idx"] = first_sale_idx

    logger.info(
        "Weekly panel: %d SKUs, %d weeks (%s to %s)",
        len(skus), len(weeks), weeks[0].date(), weeks[-1].date(),
    )
    return y, meta, skus, weeks


# --------------------------------------------------------------------------
# Demand classification (ADI / CV^2), measured over each SKU's own window
# --------------------------------------------------------------------------

def classify_demand(y: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    arr = y.values
    n_weeks = arr.shape[0]
    rows = []
    for j, sku in enumerate(y.columns):
        start = meta["first_sale_idx"].iloc[j]
        window = arr[start:, j]
        history_weeks = len(window)
        positive = window[window > 0]
        positive_weeks = len(positive)

        if positive_weeks == 0:
            adi, cv2 = np.nan, np.nan
        else:
            adi = history_weeks / positive_weeks
            cv2 = (positive.std() / positive.mean()) ** 2 if positive.mean() > 0 else np.nan

        rows.append((sku, history_weeks, positive_weeks, adi, cv2, window.mean() if history_weeks else 0.0))

    out = pd.DataFrame(rows, columns=["StockCode", "History_Weeks", "Positive_Weeks", "ADI", "CV2", "Avg_Weekly_Units"])
    out["Last_12W_Units"] = y.tail(HOLDOUT_WEEKS).sum().reindex(out["StockCode"]).values

    out["Demand_Class"] = np.select(
        [
            (out["ADI"] <= ADI_THRESHOLD) & (out["CV2"] <= CV2_THRESHOLD),
            (out["ADI"] > ADI_THRESHOLD) & (out["CV2"] <= CV2_THRESHOLD),
            (out["ADI"] <= ADI_THRESHOLD) & (out["CV2"] > CV2_THRESHOLD),
        ],
        ["Smooth", "Intermittent", "Erratic"],
        default="Lumpy",
    )
    out.loc[out["Positive_Weeks"] == 0, "Demand_Class"] = "No demand"
    logger.info("Demand pattern distribution:\n%s", out["Demand_Class"].value_counts().to_string())
    return out


# --------------------------------------------------------------------------
# Classical statistical / intermittent-demand methods
# --------------------------------------------------------------------------
# Each function takes a 1-D array of a SKU's own history (from its first
# sale onward, up to "now") and returns a single flat forecast value,
# except seasonal_naive() which returns one value per horizon step.

def _naive(hist: np.ndarray) -> float:
    return float(hist[-1]) if len(hist) else 0.0


def _moving_average(hist: np.ndarray, k: int) -> float:
    if len(hist) == 0:
        return 0.0
    window = hist[-k:] if len(hist) >= k else hist
    return float(window.mean())


def _ses(hist: np.ndarray, alpha: float = 0.3) -> float:
    if len(hist) == 0:
        return 0.0
    level = hist[0]
    for v in hist[1:]:
        level = alpha * v + (1 - alpha) * level
    return float(level)


def _seasonal_naive(hist: np.ndarray, horizon: int, season: int = SEASONAL_LAG) -> np.ndarray | None:
    if len(hist) < season:
        return None
    tail = hist[-season:]
    return np.resize(tail, horizon).astype(float)


def _croston(hist: np.ndarray, alpha: float = 0.1, sba: bool = False) -> float | None:
    nonzero_idx = np.flatnonzero(hist > 0)
    if len(nonzero_idx) == 0:
        return None
    z = hist[nonzero_idx[0]]
    q = nonzero_idx[0] + 1.0
    since_last = 0
    for t in range(nonzero_idx[0] + 1, len(hist)):
        since_last += 1
        if hist[t] > 0:
            z = alpha * hist[t] + (1 - alpha) * z
            q = alpha * since_last + (1 - alpha) * q
            since_last = 0
    rate = z / q if q > 0 else 0.0
    if sba:
        rate *= (1 - alpha / 2)
    return float(rate)


def _tsb(hist: np.ndarray, alpha: float = 0.1, beta: float = 0.1) -> float | None:
    nonzero_idx = np.flatnonzero(hist > 0)
    if len(nonzero_idx) == 0:
        return None
    k = nonzero_idx[0]
    p = 1.0 / (k + 1)
    z = hist[k]
    for t in range(k + 1, len(hist)):
        if hist[t] > 0:
            p = p + beta * (1 - p)
            z = z + alpha * (hist[t] - z)
        else:
            p = p * (1 - beta)
    return float(p * z)


def statistical_forecasts(hist: np.ndarray, horizon: int) -> dict[str, np.ndarray]:
    """Every classical method that's computable from `hist`, each as a
    length-`horizon` array (flat-repeated, except SeasonalNaive52).
    """
    out: dict[str, np.ndarray] = {"Naive": np.full(horizon, _naive(hist))}
    if len(hist) >= 4:
        out["MA4"] = np.full(horizon, _moving_average(hist, 4))
    if len(hist) >= 8:
        out["MA8"] = np.full(horizon, _moving_average(hist, 8))
    out["SES"] = np.full(horizon, _ses(hist))
    seasonal = _seasonal_naive(hist, horizon)
    if seasonal is not None:
        out["SeasonalNaive52"] = seasonal
    croston = _croston(hist, sba=False)
    if croston is not None:
        out["Croston"] = np.full(horizon, croston)
    sba = _croston(hist, sba=True)
    if sba is not None:
        out["CrostonSBA"] = np.full(horizon, sba)
    tsb = _tsb(hist)
    if tsb is not None:
        out["TSB"] = np.full(horizon, tsb)
    return out


# --------------------------------------------------------------------------
# Machine-learning panel model (global regression across all SKUs)
# --------------------------------------------------------------------------

def feature_columns() -> list[str]:
    cols = [
        "sku_code", "category_code", "subcategory_code", "supplier_code",
        "time_idx", "weekofyear", "month", "sin52", "cos52", "sin12", "cos12",
    ]
    cols += [f"lag_{lag}" for lag in LAGS]
    for w in ROLL_WINDOWS:
        cols += [f"roll_mean_{w}", f"roll_std_{w}", f"nonzero_rate_{w}"]
    cols += ["hist_mean", "hist_std", "hist_nonzero_rate"]
    return cols


FEATURES = feature_columns()


def _calendar_block(meta: pd.DataFrame, t: int, date: pd.Timestamp) -> pd.DataFrame:
    week = int(date.isocalendar().week)
    return pd.DataFrame({
        "sku_code": meta["SKU_code"].values,
        "category_code": meta["Category_code"].values,
        "subcategory_code": meta["Subcategory_code"].values,
        "supplier_code": meta["Supplier_code"].values,
        "time_idx": t,
        "weekofyear": week,
        "month": date.month,
        "sin52": np.sin(2 * np.pi * week / 52.0),
        "cos52": np.cos(2 * np.pi * week / 52.0),
        "sin12": np.sin(2 * np.pi * date.month / 12.0),
        "cos12": np.cos(2 * np.pi * date.month / 12.0),
    })


def _add_history_features(block: pd.DataFrame, arr: np.ndarray, t: int) -> None:
    hist = arr[:t, :]
    for lag in LAGS:
        block[f"lag_{lag}"] = arr[t - lag, :]
    for w in ROLL_WINDOWS:
        h = arr[t - w:t, :]
        block[f"roll_mean_{w}"] = h.mean(axis=0)
        block[f"roll_std_{w}"] = h.std(axis=0)
        block[f"nonzero_rate_{w}"] = (h > 0).mean(axis=0)
    block["hist_mean"] = hist.mean(axis=0)
    block["hist_std"] = hist.std(axis=0)
    block["hist_nonzero_rate"] = (hist > 0).mean(axis=0)


def make_training_matrix(y_panel: pd.DataFrame, meta: pd.DataFrame, end_idx: int) -> pd.DataFrame:
    arr = y_panel.values
    dates = y_panel.index
    rows = []
    for t in range(SEASONAL_LAG, end_idx):
        block = _calendar_block(meta, t, dates[t])
        block["target"] = arr[t, :]
        _add_history_features(block, arr, t)
        rows.append(block)
    out = pd.concat(rows, ignore_index=True)
    out["target_sqrt"] = np.sqrt(np.clip(out["target"], 0, None))
    return out


def make_prediction_features(history: np.ndarray, meta: pd.DataFrame, t: int, date: pd.Timestamp) -> pd.DataFrame:
    block = _calendar_block(meta, t, date)
    _add_history_features(block, history, len(history))
    return block[FEATURES]


def recursive_ml_forecast(model, initial_history: np.ndarray, meta: pd.DataFrame, start_t: int, steps: int, start_date: pd.Timestamp) -> np.ndarray:
    history = initial_history.copy()
    preds = []
    for step in range(steps):
        d = start_date + pd.Timedelta(weeks=step)
        x_future = make_prediction_features(history, meta, start_t + step, d)
        pred_sqrt = model.predict(x_future)
        pred_units = np.clip(pred_sqrt, 0, None) ** 2

        cap = np.maximum(
            np.quantile(history, 0.995, axis=0) * 3,
            history.mean(axis=0) * 8 + 1,
        )
        pred_units = np.minimum(pred_units, cap)

        preds.append(pred_units)
        history = np.vstack([history, pred_units])
    return np.vstack(preds)


def per_sku_metrics(actual: np.ndarray, pred: np.ndarray, skus: list[str], model_name: str, source: str) -> pd.DataFrame:
    err = actual - pred
    mae = np.mean(np.abs(err), axis=0)
    rmse = np.sqrt(np.mean(err ** 2, axis=0))
    denom = np.sum(np.abs(actual), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        wape = np.where(denom > 0, np.sum(np.abs(err), axis=0) / denom, np.nan)
        bias = np.where(denom > 0, np.sum(pred - actual, axis=0) / denom, np.nan)
    return pd.DataFrame({
        "StockCode": skus, "Source": source, "Model": model_name,
        "MAE": mae, "RMSE": rmse, "WAPE": wape, "Bias": bias,
    })


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def backtest_statistical(y_panel: pd.DataFrame, meta: pd.DataFrame, skus: list[str], train_end: int) -> pd.DataFrame:
    arr = y_panel.values
    actual = arr[train_end:train_end + HOLDOUT_WEEKS, :]
    frames = []
    for j, sku in enumerate(skus):
        start = meta["first_sale_idx"].iloc[j]
        hist = arr[start:train_end, j]
        if len(hist) < MIN_WEEKS_FOR_BACKTEST:
            continue
        forecasts = statistical_forecasts(hist, HOLDOUT_WEEKS)
        for name, fc in forecasts.items():
            err = actual[:, j] - fc
            mae = np.mean(np.abs(err))
            rmse = np.sqrt(np.mean(err ** 2))
            denom = np.sum(np.abs(actual[:, j]))
            wape = np.abs(err).sum() / denom if denom > 0 else np.nan
            bias = (fc - actual[:, j]).sum() / denom if denom > 0 else np.nan
            frames.append({"StockCode": sku, "Source": "Statistical", "Model": name, "MAE": mae, "RMSE": rmse, "WAPE": wape, "Bias": bias})
    return pd.DataFrame(frames)


def run(config: Config, forecast_config: ForecastConfig) -> pd.DataFrame:
    raw = load_transactions(config.data_path, country=None)
    clean = clean_transactions(raw)

    y_panel, meta, skus, weeks = load_weekly_panel(clean)
    demand_class = classify_demand(y_panel, meta)

    train_end = len(weeks) - HOLDOUT_WEEKS
    logger.info("Backtest: training on weeks 1-%d, holding out the last %d weeks", train_end, HOLDOUT_WEEKS)

    # --- statistical backtest ---
    stat_all = backtest_statistical(y_panel, meta, skus, train_end)
    stat_best = stat_all.sort_values(["StockCode", "MAE", "RMSE"]).groupby("StockCode", as_index=False).first()
    logger.info("Statistical champions:\n%s", stat_best["Model"].value_counts().to_string())

    # --- ML backtest ---
    train_df = make_training_matrix(y_panel, meta, train_end)
    holdout_actual = y_panel.values[train_end:train_end + HOLDOUT_WEEKS, :]
    holdout_start = weeks[train_end]
    history_train = y_panel.values[:train_end, :]

    ml_frames = []
    fitted_backtest_models = {}
    for name, factory in ML_MODEL_FACTORIES.items():
        model = factory()
        model.fit(train_df[FEATURES], train_df["target_sqrt"])
        fitted_backtest_models[name] = model
        pred = recursive_ml_forecast(model, history_train, meta, train_end, HOLDOUT_WEEKS, holdout_start)
        ml_frames.append(per_sku_metrics(holdout_actual, pred, skus, name, "ML"))
    ml_all = pd.concat(ml_frames, ignore_index=True)
    ml_best = ml_all.sort_values(["StockCode", "MAE", "RMSE"]).groupby("StockCode", as_index=False).first()
    logger.info("ML champions:\n%s", ml_best["Model"].value_counts().to_string())

    # --- hybrid selection ---
    comparison = demand_class.merge(meta[["Category", "Subcategory", "Supplier", "Avg_Price", "Avg_Cost", "Lead_Time_Days", "Lead_Time_SD_Days"]], left_on="StockCode", right_index=True, how="left")
    comparison = comparison.merge(stat_best.rename(columns={"Model": "Champion_Model", "MAE": "Backtest_MAE", "RMSE": "Backtest_RMSE", "WAPE": "Backtest_WAPE", "Bias": "Backtest_Bias"}).drop(columns="Source"), on="StockCode", how="left")
    comparison = comparison.merge(ml_best.rename(columns={"Model": "ML_Model", "MAE": "ML_MAE", "RMSE": "ML_RMSE", "WAPE": "ML_WAPE", "Bias": "ML_Bias"}).drop(columns="Source"), on="StockCode", how="left")

    comparison["Overall_Source"] = np.where(
        comparison["ML_MAE"] < comparison["Backtest_MAE"], "ML", "Statistical",
    )
    comparison.loc[comparison["Backtest_MAE"].isna() & comparison["ML_MAE"].notna(), "Overall_Source"] = "ML"
    comparison["Overall_Model"] = np.where(comparison["Overall_Source"].eq("ML"), comparison["ML_Model"], comparison["Champion_Model"])
    comparison["Overall_MAE"] = np.where(comparison["Overall_Source"].eq("ML"), comparison["ML_MAE"], comparison["Backtest_MAE"])
    comparison["MAE_Improvement_vs_Stat"] = np.where(
        comparison["Backtest_MAE"] > 0, 1 - comparison["Overall_MAE"] / comparison["Backtest_MAE"], 0.0,
    )
    logger.info("Overall source:\n%s", comparison["Overall_Source"].value_counts().to_string())

    # --- refit on full history and forecast the future ---
    full_df = make_training_matrix(y_panel, meta, len(weeks))
    final_ml_models = {}
    for name, factory in ML_MODEL_FACTORIES.items():
        model = factory()
        model.fit(full_df[FEATURES], full_df["target_sqrt"])
        final_ml_models[name] = model

    future_start = weeks[-1] + pd.Timedelta(weeks=1)
    future_weeks = pd.date_range(future_start, periods=FORECAST_HORIZON, freq="W-MON")
    ml_future = {
        name: recursive_ml_forecast(model, y_panel.values, meta, len(weeks), FORECAST_HORIZON, future_start)
        for name, model in final_ml_models.items()
    }

    comp_idx = comparison.set_index("StockCode")
    detail_rows = []
    for j, sku in enumerate(skus):
        r = comp_idx.loc[sku]
        if r["Overall_Source"] == "ML":
            forecast = ml_future[r["Overall_Model"]][:, j]
        else:
            start = meta["first_sale_idx"].iloc[j]
            hist = y_panel.values[start:, j]
            methods = statistical_forecasts(hist, FORECAST_HORIZON)
            forecast = methods.get(r["Overall_Model"], methods["Naive"])

        price, cost = float(r["Avg_Price"]), float(r["Avg_Cost"])
        for h, week in enumerate(future_weeks):
            units = max(float(forecast[h]), 0.0)
            detail_rows.append({
                "StockCode": sku, "Week": week, "Forecast_Units": units,
                "Overall_Source": r["Overall_Source"], "Overall_Model": r["Overall_Model"],
                "Forecast_Revenue": units * price, "Forecast_GrossProfit": units * (price - cost),
            })
    detail = pd.DataFrame(detail_rows)

    sku_forecast = detail.groupby("StockCode", as_index=False).agg(
        Hybrid_Forecast_12W_Units=("Forecast_Units", "sum"),
        Hybrid_Forecast_12W_Revenue=("Forecast_Revenue", "sum"),
        Hybrid_Forecast_12W_GrossProfit=("Forecast_GrossProfit", "sum"),
    )
    comparison = comparison.merge(sku_forecast, on="StockCode", how="left")
    comparison = comparison.merge(meta[["Description"]], left_on="StockCode", right_index=True, how="left")

    output_dir = forecast_config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output_dir / "hybrid_forecast_sku_comparison.csv", index=False)
    pd.concat([stat_all, ml_all], ignore_index=True).to_csv(output_dir / "hybrid_forecast_all_candidate_metrics.csv", index=False)
    detail.to_csv(output_dir / "hybrid_forecast_12w_detail.csv", index=False)
    logger.info(
        "Saved hybrid_forecast_sku_comparison.csv, hybrid_forecast_all_candidate_metrics.csv, "
        "hybrid_forecast_12w_detail.csv to %s", output_dir,
    )

    save_plots(comparison, output_dir)

    logger.info("Median Statistical MAE: %.4f", comparison["Backtest_MAE"].median())
    logger.info("Median ML MAE: %.4f", comparison["ML_MAE"].median())
    logger.info("Median Hybrid MAE: %.4f", comparison["Overall_MAE"].median())
    logger.info("Hybrid 12-week forecast units: %.2f", detail["Forecast_Units"].sum())
    logger.info("Hybrid 12-week forecast revenue: %.2f", detail["Forecast_Revenue"].sum())
    return comparison


def save_plots(comparison: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    comparison["Demand_Class"].value_counts().reindex(
        ["Smooth", "Intermittent", "Erratic", "Lumpy", "No demand"]
    ).dropna().plot(kind="bar", ax=axes[0], color="#4C72B0")
    axes[0].set_title("Demand Pattern Classification")
    axes[0].set_ylabel("Number of SKUs")
    axes[0].tick_params(axis="x", rotation=30)

    comparison["Overall_Source"].value_counts().plot(kind="bar", ax=axes[1], color="#DD8452")
    axes[1].set_title("Hybrid Forecast: Winning Source per SKU")
    axes[1].set_ylabel("Number of SKUs")
    axes[1].tick_params(axis="x", rotation=0)

    fig.tight_layout()
    fig.savefig(output_dir / "hybrid_forecast_overview.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "hybrid_forecast_overview.png")


def main() -> None:
    run(Config(), ForecastConfig())


if __name__ == "__main__":
    main()
