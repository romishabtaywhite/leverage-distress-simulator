"""
Phase 4: the actual ML classifier.

With only 14 labeled companies, a normal train/test split would leave far
too few points on either side to mean anything. The correct technique
here is Leave-One-Out Cross-Validation (LOOCV): train on 13 companies,
predict the 1 left out, repeat once per company, so every single company
gets a genuine out-of-sample prediction (the model never saw that
company while learning). This is standard, honest practice for small
samples - not a shortcut, the RIGHT tool for this specific size dataset.

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
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"

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

    loo = LeaveOneOut()
    predictions = []
    probabilities = []

    for train_idx, test_idx in loo.split(X):
        pipeline = Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(class_weight="balanced", C=1.0)),
        ])
        pipeline.fit(X[train_idx], y[train_idx])
        pred = pipeline.predict(X[test_idx])[0]
        prob = pipeline.predict_proba(X[test_idx])[0][1]  # probability of class 1 (distressed)
        predictions.append(pred)
        probabilities.append(prob)

    predictions = np.array(predictions)
    probabilities = np.array(probabilities)

    print(f"{'Ticker':<8}{'Actual':<12}{'Predicted':<12}{'P(distressed)':>15}")
    print("-" * 47)
    for i in range(len(df)):
        actual = "distressed" if y[i] == 1 else "not"
        predicted = "distressed" if predictions[i] == 1 else "not"
        flag = "  <-- WRONG" if predictions[i] != y[i] else ""
        print(f"{tickers[i]:<8}{actual:<12}{predicted:<12}{probabilities[i]:>14.1%}{flag}")

    accuracy = (predictions == y).mean()
    cm = confusion_matrix(y, predictions)

    print()
    print(f"LOOCV accuracy: {accuracy:.1%} ({(predictions == y).sum()}/{len(y)} correct)")
    print(f"Confusion matrix (rows=actual, cols=predicted, order=[not distressed, distressed]):")
    print(cm)
    print()
    print("HONEST CAVEAT: with n=14, this accuracy figure has a wide real margin of error -")
    print("getting 1-2 more predictions right or wrong would move it substantially. Treat this")
    print("as a genuine but low-confidence result, not a validated production model.")
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
