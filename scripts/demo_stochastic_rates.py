"""
Phase 3, step 2: stochastic rate scenarios.

Calibrates a mean-reverting rate model from REAL historical SOFR data,
simulates many random future rate paths 2 years (8 quarters) ahead, and
computes Bausch Health's interest coverage ratio under EVERY simulated
path - producing a genuine DISTRIBUTION of outcomes, not just one number.

This is exactly the "simulated stress signal" the project's research
question is ultimately about: not "what did coverage look like on one
historical path" but "across many plausible futures, how much of the
probability mass falls into distress territory."
"""

import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from engine.company_interest import get_total_debt_balance, total_quarterly_interest  # noqa: E402
from engine.ebitda import get_ebitda_proxy  # noqa: E402
from engine.scenarios import calibrate_ou, simulate_paths  # noqa: E402

TICKER = "BHC"
HORIZON_QUARTERS = 8  # 2 years ahead
N_PATHS = 500
DISTRESS_COVERAGE_THRESHOLD = 2.0  # illustrative threshold - BHC has no real covenant on file


def get_cik_for_ticker(ticker):
    for c in CANDIDATES:
        if c["ticker"] == ticker:
            return c["cik"]
    raise ValueError(f"{ticker} not found in candidate_companies.py")


def get_quarterly_sofr_history(conn):
    df = pd.read_sql(
        "SELECT obs_date, value FROM rate_series WHERE series_code = 'SOFR' ORDER BY obs_date",
        conn, parse_dates=["obs_date"],
    )
    df = df.set_index("obs_date")
    return df.resample("QE").last().dropna()["value"].tolist()


def insert_scenario(conn, name, description):
    cur = conn.execute(
        "INSERT INTO rate_scenarios (scenario_name, scenario_type, description) VALUES (?, ?, ?)",
        (name, "stochastic", description),
    )
    return cur.lastrowid


def insert_path(conn, scenario_id, path_id, path_values):
    rows = [(scenario_id, path_id, i, str(date.today()), v) for i, v in enumerate(path_values)]
    conn.executemany(
        "INSERT INTO scenario_rate_paths (scenario_id, path_id, period_index, obs_date, rate_value) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )


def insert_result(conn, company_id, scenario_id, path_id, ebitda, annual_interest, total_debt, leverage, coverage):
    conn.execute(
        """INSERT INTO simulation_results
           (company_id, scenario_id, path_id, period_index, obs_date,
            ebitda, interest_expense, total_debt_balance, leverage_ratio,
            interest_coverage_ratio, covenant_breach_flag)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (company_id, scenario_id, path_id, HORIZON_QUARTERS, str(date.today()),
         ebitda, annual_interest, total_debt, leverage, coverage,
         1 if coverage is not None and coverage < DISTRESS_COVERAGE_THRESHOLD else 0),
    )


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    # --- Step 1: calibrate the model from real history ---
    quarterly_sofr = get_quarterly_sofr_history(conn)
    current_sofr = quarterly_sofr[-1]
    params = calibrate_ou(quarterly_sofr)

    print("CALIBRATION (from real historical quarterly SOFR)")
    print("-" * 60)
    print(f"  Long-run average (theta):     {params['theta']:.2f}%")
    print(f"  Mean-reversion speed (kappa):  {params['kappa']:.3f} per quarter"
          + (" [fallback used - data didn't show clear reversion]" if params["fallback_used"] else ""))
    print(f"  Quarterly volatility (sigma):  {params['sigma']:.2f} percentage points")
    print(f"  Starting point (today's SOFR): {current_sofr:.2f}%")
    print()

    # --- Step 2: simulate many random paths ---
    paths = simulate_paths(
        current_value=current_sofr, kappa=params["kappa"], theta=params["theta"],
        sigma=params["sigma"], horizon_periods=HORIZON_QUARTERS, n_paths=N_PATHS,
    )
    terminal_rates = [p[-1] for p in paths]

    print(f"Simulated {N_PATHS} paths, {HORIZON_QUARTERS} quarters (2 years) ahead.")
    print(f"Terminal SOFR distribution: min {min(terminal_rates):.2f}%, "
          f"median {np.median(terminal_rates):.2f}%, max {max(terminal_rates):.2f}%")
    print()
    print("SIMPLIFICATION: only the rate varies across these simulated paths - EBITDA and")
    print("total debt are held constant at today's real values. This isolates the pure rate-cycle")
    print("effect, same principle as the historical replay - a fuller model would also simulate")
    print("EBITDA uncertainty, which is future work.")
    print()

    # --- Step 3: run the company engine under every path's terminal rate ---
    company_id = conn.execute("SELECT company_id FROM companies WHERE ticker = ?", (TICKER,)).fetchone()[0]
    total_debt, _ = get_total_debt_balance(conn, TICKER)
    cik = get_cik_for_ticker(TICKER)
    _, adjusted_ebitda, _ = get_ebitda_proxy(cik)

    scenario_id = insert_scenario(
        conn, f"{TICKER} SOFR stochastic {HORIZON_QUARTERS}q",
        f"Mean-reverting simulation, {N_PATHS} paths, {HORIZON_QUARTERS} quarters ahead, "
        f"calibrated from real historical SOFR (kappa={params['kappa']:.3f}, "
        f"theta={params['theta']:.2f}, sigma={params['sigma']:.2f})"
    )

    coverage_ratios = []
    for path_id, path in enumerate(paths):
        terminal_rate = path[-1]
        total_q, _, _ = total_quarterly_interest(conn, TICKER, sofr_override=terminal_rate)
        annual_interest = total_q * 4
        coverage = adjusted_ebitda / annual_interest if annual_interest > 0 else None
        coverage_ratios.append(coverage)

        insert_path(conn, scenario_id, path_id, path)
        insert_result(conn, company_id, scenario_id, path_id, adjusted_ebitda,
                      annual_interest, total_debt, total_debt / adjusted_ebitda, coverage)

    conn.commit()

    # --- Step 4: the distribution of outcomes ---
    coverage_arr = np.array(coverage_ratios)
    breach_probability = float(np.mean(coverage_arr < DISTRESS_COVERAGE_THRESHOLD))

    print(f"INTEREST COVERAGE DISTRIBUTION for {TICKER}, 2 years ahead ({N_PATHS} simulated paths)")
    print("-" * 60)
    print(f"  5th percentile:   {np.percentile(coverage_arr, 5):.2f}x")
    print(f"  25th percentile:  {np.percentile(coverage_arr, 25):.2f}x")
    print(f"  Median:           {np.percentile(coverage_arr, 50):.2f}x")
    print(f"  75th percentile:  {np.percentile(coverage_arr, 75):.2f}x")
    print(f"  95th percentile:  {np.percentile(coverage_arr, 95):.2f}x")
    print()
    print(f"Probability coverage falls below {DISTRESS_COVERAGE_THRESHOLD}x within 2 years: "
          f"{breach_probability:.1%}")
    print()
    print(f"Saved {N_PATHS} rate paths and {N_PATHS} simulation results to the database.")

    conn.close()
