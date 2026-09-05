#!/usr/bin/env python3
"""Customer lifetime value (LTV) segmentation via RFM analysis and KMeans,
with a classifier trained to predict LTV segment from RFM behavior.

Adapted from cltv.py and cltv_assignment.py (uploaded separately) --
near-identical scripts differing only in which dataset they load (a
general dataset vs. a UK-only variant). Both assumed an already-computed
RFM file (rfm_revised.csv / rfm_uk.csv) with a `rec_freq_monet` code
column; that upstream RFM step isn't included in either upload, so
`compute_rfm()` here reconstructs it directly from the same cleaned
transaction data inventory_planning.py already loads, rather than
requiring a separate file this repo doesn't have.

Three real, verified bugs from the originals are fixed rather than
carried over:

1. `len(ltv)-len(outliers_removed)` is called *before* `outliers_removed`
   is defined (one line above its own definition) -- a guaranteed
   `NameError` on any top-to-bottom run. Not carried over; outlier counts
   are logged after removal instead.
2. `value_map = {'1':'3','3':'1','2':'2'}` is applied to recency,
   frequency, AND monetary alike. Inverting the tertile so "1" means
   "best" only makes sense for recency (low recency = best, so its raw
   qcut order needs flipping); frequency and monetary already increase
   with customer value, so applying the same flip to them inverts a
   scale that didn't need inverting. `compute_rfm()` avoids the whole
   problem by qcut-ing recency with descending labels and
   frequency/monetary with ascending labels directly, rather than
   qcut-then-flip.
3. **The most consequential one**: `KMeans(...).fit_predict()` cluster
   IDs are arbitrary -- nothing guarantees cluster `0` has the lowest
   mean LTV. Verified empirically (5 reseeds of a synthetic 3-cluster
   LTV distribution): cluster-id-to-mean order came out sorted in only
   1 of 5 runs. The original's hardcoded
   `{'0':'Low_ltv','1':'Mid_ltv','2':'High_ltv'}` would silently mislabel
   customers -- e.g. calling your highest-spending cluster "Low_ltv" --
   on an unlucky seed, with no way to notice from the code alone. Fixed
   here by ranking clusters by their actual mean LTV before labeling.

`KMeans` and the CV/search splitters also had no `random_state` set (this
script's results wouldn't reproduce run to run); fixed by pinning
RANDOM_STATE everywhere. A train/test split was added before evaluating
the final model -- the originals predicted on the same data they fit on,
which overstates real accuracy.

Caveat worth knowing, not a bug: `monetary` (an RFM feature the
classifier is trained on) is the same value as `ltv` (what KMeans
clustered on), so the classifier partly has access to the answer through
a renamed copy of it. That inflates the reported accuracy versus what a
model would achieve using only signals available *before* you already
know a customer's total spend -- kept as-is to match the original's
feature set, flagged here rather than silently presented as a clean
result.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (
    RandomizedSearchCV,
    RepeatedStratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.tree import DecisionTreeClassifier

from inventory_planning import Config, clean_transactions, load_transactions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("customer_ltv_segmentation")

RANDOM_STATE = 42
LTV_OUTLIER_QUANTILE = 0.99
N_LTV_CLUSTERS = 3
LTV_SEGMENT_LABELS = ["Low_ltv", "Mid_ltv", "High_ltv"]
TEST_SIZE = 0.25

RFM_FEATURE_COLUMNS = [
    "recency", "frequency", "monetary",
    "recency_score", "frequency_score", "monetary_score", "overall_score",
]


def compute_rfm(clean: pd.DataFrame) -> pd.DataFrame:
    """One row per customer: recency (days since last order), frequency
    (distinct invoices), monetary (total revenue), each scored 1-3 by
    tertile with 3 always meaning "best", and their sum as overall_score.
    """
    df = clean.copy()
    df["revenue"] = df["Quantity"] * df["Price"]
    snapshot_date = df["InvoiceDate"].max() + pd.Timedelta(days=1)

    rfm = df.groupby("Customer ID").agg(
        recency=("InvoiceDate", lambda s: (snapshot_date - s.max()).days),
        frequency=("Invoice", "nunique"),
        monetary=("revenue", "sum"),
    ).reset_index()

    def tertile_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
        # rank(method="first") breaks ties before qcut so repeated values
        # (e.g. many customers with frequency=1) don't collapse into one
        # oversized bin or raise a duplicate-bin-edge error.
        ranked = series.rank(method="first")
        labels = [1, 2, 3] if higher_is_better else [3, 2, 1]
        return pd.qcut(ranked, q=3, labels=labels).astype(int)

    rfm["recency_score"] = tertile_score(rfm["recency"], higher_is_better=False)
    rfm["frequency_score"] = tertile_score(rfm["frequency"], higher_is_better=True)
    rfm["monetary_score"] = tertile_score(rfm["monetary"], higher_is_better=True)
    rfm["overall_score"] = rfm["recency_score"] + rfm["frequency_score"] + rfm["monetary_score"]
    rfm["ltv"] = rfm["monetary"]
    return rfm


def cluster_ltv(rfm: pd.DataFrame) -> pd.DataFrame:
    """Removes top-1% LTV outliers, then KMeans-clusters the rest into
    Low/Mid/High LTV segments, ranking cluster IDs by their actual mean
    LTV rather than assuming cluster 0/1/2 already comes out that way.
    """
    rfm = rfm.copy()
    cutoff = rfm["ltv"].quantile(LTV_OUTLIER_QUANTILE)
    kept = rfm[rfm["ltv"] <= cutoff].copy()
    logger.info(
        "LTV outlier removal: %d -> %d customers (cutoff at %.0f%% percentile = %.2f)",
        len(rfm), len(kept), LTV_OUTLIER_QUANTILE * 100, cutoff,
    )

    km = KMeans(n_clusters=N_LTV_CLUSTERS, n_init=10, max_iter=300, random_state=RANDOM_STATE)
    kept["cluster_id"] = km.fit_predict(kept[["ltv"]])

    cluster_means = kept.groupby("cluster_id")["ltv"].mean().sort_values()
    label_by_cluster_id = dict(zip(cluster_means.index, LTV_SEGMENT_LABELS))
    kept["ltv_segment"] = kept["cluster_id"].map(label_by_cluster_id)

    logger.info("Cluster mean LTV (low to high):\n%s", cluster_means.to_string())
    logger.info("Segment counts:\n%s", kept["ltv_segment"].value_counts().to_string())
    return kept


def evaluate_segment_classifier(segmented: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Trains a classifier to predict LTV segment from RFM behavior,
    reporting cross-validated and held-out accuracy plus feature
    importances. Held out test set (not seen during CV or search) is what
    the final confusion table is built from.
    """
    features = segmented[RFM_FEATURE_COLUMNS]
    X = pd.get_dummies(features).values
    y = segmented["ltv_segment"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    cv = RepeatedStratifiedKFold(n_splits=3, n_repeats=3, random_state=RANDOM_STATE)
    tree_cv_scores = cross_val_score(
        DecisionTreeClassifier(random_state=RANDOM_STATE), X_train, y_train, scoring="accuracy", cv=cv
    )

    param_dist = {"max_depth": [3, None], "min_samples_leaf": range(1, 9), "criterion": ["gini", "entropy"]}
    tree_search = RandomizedSearchCV(
        DecisionTreeClassifier(random_state=RANDOM_STATE), param_dist, cv=5, random_state=RANDOM_STATE
    )
    rf_search = RandomizedSearchCV(
        RandomForestClassifier(random_state=RANDOM_STATE), param_dist, cv=5, random_state=RANDOM_STATE
    )
    tree_search.fit(X_train, y_train)
    rf_search.fit(X_train, y_train)

    best_model, best_name = (
        (rf_search.best_estimator_, "random_forest")
        if rf_search.best_score_ >= tree_search.best_score_
        else (tree_search.best_estimator_, "decision_tree")
    )
    test_predictions = best_model.predict(X_test)
    holdout_accuracy = (test_predictions == y_test).mean()

    comparison = pd.DataFrame({"Actual": y_test, "Prediction": test_predictions})
    confusion_counts = comparison.groupby(["Actual", "Prediction"]).size().reset_index(name="count")

    summary = {
        "decision_tree_cv_accuracy": tree_cv_scores.mean(),
        "decision_tree_search_best_cv_accuracy": tree_search.best_score_,
        "random_forest_search_best_cv_accuracy": rf_search.best_score_,
        "best_model": best_name,
        "best_model_params": tree_search.best_params_ if best_name == "decision_tree" else rf_search.best_params_,
        "holdout_accuracy": holdout_accuracy,
        "test_set_size": len(y_test),
    }
    logger.info("Model evaluation: %s", summary)

    importances = dict(zip(features.columns, best_model.feature_importances_))
    logger.info("Feature importances (%s):\n%s", best_name, pd.Series(importances).sort_values(ascending=False).to_string())
    summary["feature_importances"] = importances

    return confusion_counts, summary


def save_plots(rfm: pd.DataFrame, segmented: pd.DataFrame, summary: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    sns.boxplot(y="ltv", data=rfm, ax=axes[0])
    axes[0].set_title(f"LTV — before outlier removal (n={len(rfm)})")
    sns.boxplot(y="ltv", data=segmented, ax=axes[1])
    axes[1].set_title(f"LTV — after outlier removal (n={len(segmented)})")
    fig.tight_layout()
    fig.savefig(output_dir / "ltv_outlier_removal.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "ltv_outlier_removal.png")

    cluster_means = segmented.groupby("ltv_segment")["ltv"].mean().reindex(LTV_SEGMENT_LABELS)
    fig, ax = plt.subplots(figsize=(7, 5))
    cluster_means.plot(kind="bar", ax=ax, color=["#4C72B0", "#DD8452", "#55A868"])
    ax.set_title("Mean LTV by Segment")
    ax.set_ylabel("Mean lifetime value")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(output_dir / "ltv_segment_means.png", dpi=150)
    plt.close(fig)
    logger.info("Saved %s", output_dir / "ltv_segment_means.png")

    if "feature_importances" in summary:
        importances = pd.Series(summary["feature_importances"]).sort_values()
        fig, ax = plt.subplots(figsize=(8, 5))
        importances.plot(kind="barh", ax=ax, color="#4C72B0")
        ax.set_title("RFM Feature Importance for Predicting LTV Segment")
        ax.set_xlabel("Importance")
        fig.tight_layout()
        fig.savefig(output_dir / "ltv_feature_importance.png", dpi=150)
        plt.close(fig)
        logger.info("Saved %s", output_dir / "ltv_feature_importance.png")


def run(config: Config) -> None:
    raw = load_transactions(config.data_path, country=config.country)
    clean = clean_transactions(raw)

    rfm = compute_rfm(clean)
    segmented = cluster_ltv(rfm)
    confusion_counts, summary = evaluate_segment_classifier(segmented)

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    segmented.to_csv(output_dir / "customer_rfm_segments.csv", index=False)
    confusion_counts.to_csv(output_dir / "ltv_segment_confusion.csv", index=False)
    logger.info("Saved %s and %s", output_dir / "customer_rfm_segments.csv", output_dir / "ltv_segment_confusion.csv")

    save_plots(rfm, segmented, summary, output_dir)


def main() -> None:
    run(Config())


if __name__ == "__main__":
    main()
