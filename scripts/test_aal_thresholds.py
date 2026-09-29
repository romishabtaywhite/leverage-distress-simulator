"""
Tests AAL's simulated breach probability across several thresholds,
using data ALREADY stored from the stochastic simulation - no need to
rerun anything, since every path's coverage ratio was persisted to
simulation_results.

Grounded in a real reference point: Delta Air Lines' actual disclosed
debt covenants use a 1.20x minimum Fixed Charge Coverage Ratio (per its
10-K) - much lower than the generic 2.0x used elsewhere in this project.
More importantly: AAL's OWN real covenants aren't interest-coverage-based
at all - they're structured around loan-to-value, collateral coverage on
secured aircraft financing, and a $2.0B minimum liquidity buffer (per its
own 10-Q disclosures). So even a "corrected" threshold is still an
approximation of a fundamentally different real risk framework - stated
plainly, not glossed over.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"

THRESHOLDS_TO_TEST = [1.0, 1.2, 1.5, 1.75, 2.0]

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    # Pull AAL's most recent stochastic scenario's per-path coverage ratios
    row = conn.execute(
        """SELECT sr.scenario_id FROM rate_scenarios sr
           WHERE sr.scenario_name = 'AAL SOFR stochastic 8q'
           ORDER BY sr.scenario_id DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        print("No AAL stochastic scenario found - run demo_stochastic_extended.py first.")
        sys.exit(1)
    scenario_id = row[0]

    df = pd.read_sql(
        "SELECT interest_coverage_ratio FROM simulation_results WHERE scenario_id = ?",
        conn, params=(scenario_id,),
    )
    coverage = df["interest_coverage_ratio"].dropna().values

    print(f"AAL: {len(coverage)} simulated paths loaded from storage "
          f"(min {coverage.min():.2f}x, median {np.median(coverage):.2f}x, max {coverage.max():.2f}x)")
    print()
    print(f"{'Threshold':<12}{'Breach Probability':>20}{'Reference point':>30}")
    print("-" * 62)
    for t in THRESHOLDS_TO_TEST:
        breach_prob = float(np.mean(coverage < t))
        ref = ""
        if t == 1.2:
            ref = "Delta's real 1.20x FCCR covenant"
        elif t == 2.0:
            ref = "generic threshold used elsewhere"
        print(f"{t:<12.2f}{breach_prob:>19.1%}{ref:>30}")

    print()
    print("At Delta's real 1.20x benchmark, AAL's breach probability drops to the figure")
    print("shown above - if near 0%, that CORRECTLY matches AAL's real non-default status,")
    print("confirming the earlier '100% breach' was a threshold mismatch, not a genuine")
    print("distress signal.")
    print()
    print("HONEST REMAINING CAVEAT: AAL's own real covenants aren't interest-coverage-based")
    print("at all - they're structured around loan-to-value and collateral coverage on")
    print("secured aircraft financing, plus a $2.0B minimum liquidity buffer. Even a")
    print("corrected numeric threshold is still testing the WRONG KIND of metric for this")
    print("company - a more complete fix would model AAL's actual liquidity-based covenant")
    print("structure directly, which this project does not attempt.")

    conn.close()
