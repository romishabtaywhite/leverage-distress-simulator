"""
Phase 4: the actual ML classifier.

With only 14 labeled companies, a normal train/test split would leave far
too few points on either side to mean anything. The correct technique
here is Leave-One-Out Cross-Validation (LOOCV): train on 13 companies,
predict the 1 left out, repeat once per company, so every single company
gets a genuine out-of-sample prediction (the model never saw that
company while learning). This is standard, honest practice for small
samples - not a shortcut, the RIGHT tool for this specific size dataset.

Two additions beyond raw accuracy, both standard practice in real credit
risk modeling and both directly answer "is this result actually
meaningful, or could pure chance produce something similar":

1. ROC-AUC from the LOOCV out-of-fold probabilities - less sensitive to
   the arbitrary 50% classification cutoff than raw accuracy, since it
   measures rank-ordering quality across ALL possible thresholds at once.
2. A permutation test - reshuffle the labels randomly thousands of times,
   rerun the ENTIRE LOOCV procedure on each shuffled version, and see what
   fraction of random reshuffles do as well as or better than our real
   result by pure chance. This is the honest way to answer "could a
   coin flip have produced this."

Features: leverage ratio and interest coverage ratio (both static,
standardized single-point-in-time figures). Logistic regression with
L2 regularization and balanced class weights, since our 14 companies
split 5 distressed / 9 not - not perfectly balanced.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"

N_PERMUTATIONS = 2000


def run_loocv(X, y):
    """Runs the full LOOCV procedure once, returns (predictions, probabilities)."""
    loo = LeaveOneOut()
    predictions = np.zeros(len(y), dtype=int)
    probabilities = np.zeros(len(y))
    for train_idx, test_idx in loo.split(X):
        pipeline = Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(class_weight="balanced", C=1.0)),
        ])
        pipeline.fit(X[train_idx], y[train_idx])
        predictions[test_idx[0]] = pipeline.predict(X[test_idx])[0]
        probabilities[test_idx[0]] = pipeline.predict_proba(X[test_idx])[0][1]
    return predictions, probabilities


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT ticker, leverage_ratio, interest_coverage_ratio, is_distressed "
        "FROM ml_dataset WHERE data_complete = 1",
        conn,
    )
    conn.close()

    print(f"Dataset: {len(df)} companies "
          f"({df['is_distressed'].sum()} distressed, {(1 - df['is_distressed']).sum()} not)")
    print()

    X = df[["leverage_ratio", "interest_coverage_ratio"]].values
    y = df["is_distressed"].values
    tickers = df["ticker"].values

    predictions, probabilities = run_loocv(X, y)

    print(f"{'Ticker':<8}{'Actual':<12}{'Predicted':<12}{'P(distressed)':>15}")
    print("-" * 47)
    for i in range(len(df)):
        actual = "distressed" if y[i] == 1 else "not"
        predicted = "distressed" if predictions[i] == 1 else "not"
        flag = "  <-- WRONG" if predictions[i] != y[i] else ""
        print(f"{tickers[i]:<8}{actual:<12}{predicted:<12}{probabilities[i]:>14.1%}{flag}")

    accuracy = (predictions == y).mean()
    baseline_accuracy = max(y.mean(), 1 - y.mean())
    cm = confusion_matrix(y, predictions)
    auc = roc_auc_score(y, probabilities)

    print()
    print(f"LOOCV accuracy: {accuracy:.1%} ({(predictions == y).sum()}/{len(y)} correct)")
    print(f"Majority-class baseline: {baseline_accuracy:.1%} (always guessing 'not distressed')")
    print(f"ROC-AUC: {auc:.3f} (0.5 = no better than chance, 1.0 = perfect rank-ordering)")
    print(f"Confusion matrix (rows=actual, cols=predicted, order=[not distressed, distressed]):")
    print(cm)
    print()

    # --- Permutation test: is this result distinguishable from chance? ---
    print(f"Running permutation test ({N_PERMUTATIONS} reshuffles - this takes a few seconds)...")
    rng = np.random.default_rng(42)
    permuted_accuracies = np.zeros(N_PERMUTATIONS)
    permuted_aucs = np.zeros(N_PERMUTATIONS)

    for i in range(N_PERMUTATIONS):
        y_shuffled = rng.permutation(y)
        perm_preds, perm_probs = run_loocv(X, y_shuffled)
        permuted_accuracies[i] = (perm_preds == y_shuffled).mean()
        # AUC is undefined if a shuffle produces all-one-class - skip those safely
        if len(np.unique(y_shuffled)) == 2:
            permuted_aucs[i] = roc_auc_score(y_shuffled, perm_probs)
        else:
            permuted_aucs[i] = np.nan

    p_value_accuracy = (permuted_accuracies >= accuracy).mean()
    valid_aucs = permuted_aucs[~np.isnan(permuted_aucs)]
    p_value_auc = (valid_aucs >= auc).mean()

    print()
    print(f"PERMUTATION TEST RESULTS:")
    print(f"  Real accuracy {accuracy:.1%} vs. random-shuffle accuracies: "
          f"mean {permuted_accuracies.mean():.1%}, so {p_value_accuracy:.1%} of random")
    print(f"  reshuffles did AS WELL OR BETTER than our real result by pure chance (p={p_value_accuracy:.3f}).")
    print(f"  Real AUC {auc:.3f} vs. random-shuffle AUCs: mean {np.nanmean(valid_aucs):.3f}, "
          f"p={p_value_auc:.3f}.")
    if auc < 0.5:
        print(f"  Note: an AUC below 0.5 means this model's predicted probabilities actually rank")
        print(f"  distressed and non-distressed companies WORSE than random guessing would - driven")
        print(f"  here specifically by PRTYQ's extreme leverage value pulling the model badly off in")
        print(f"  the wrong direction (see its near-zero predicted probability above). A genuinely")
        print(f"  informative failure mode, not just a low score.")
    print()
    if p_value_accuracy < 0.05 or p_value_auc < 0.05:
        print("  -> By the conventional p<0.05 bar, this result WOULD be considered distinguishable")
        print("     from chance - but with n=14, treat that bar itself with caution.")
    else:
        print("  -> Honestly: this result is NOT clearly distinguishable from random chance at n=14.")
        print("     That's a real, important finding in itself - not a failure to hide. It's exactly")
        print("     why the simulated breach-probability feature (built from real mechanism, not")
        print("     correlational curve-fitting on a tiny sample) is the more defensible approach.")
    print()

    # Fit on ALL data for coefficient inspection (not for evaluation - that's what LOOCV was for)
    final_pipeline = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(class_weight="balanced", C=1.0)),
    ])
    final_pipeline.fit(X, y)
    coefs = final_pipeline.named_steps["model"].coef_[0]

    print("Coefficients (on standardized features, fit on all 14 companies):")
    print(f"  Leverage ratio:   {coefs[0]:+.3f}  "
          f"({'higher leverage -> more likely distressed, as expected' if coefs[0] > 0 else 'unexpected sign - worth investigating'})")
    print(f"  Interest coverage: {coefs[1]:+.3f}  "
          f"({'higher coverage -> less likely distressed, as expected' if coefs[1] < 0 else 'unexpected sign - worth investigating'})")
