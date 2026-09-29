"""
Runs the same calibrated stochastic rate simulation across all 4
companies at once. The rate model itself is calibrated ONCE (rates are a
market-wide phenomenon, not company-specific) - only the company-level
consequences (interest, coverage) differ per company, based on each
one's own real floating-rate exposure.

Expected honest result for Party City: since both its tranches are fixed
rate, its coverage ratio will be IDENTICAL across every single simulated
path - it has zero sensitivity to rate scenarios. That's not a bug, it's
the same finding we made earlier (its distress was demand-driven, not
rate-driven) showing up again here as further confirmation.
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

TICKERS = ["DBD", "BHC", "CYH", "PRTYQ"]
HORIZON_QUARTERS = 8
N_PATHS = 500
DISTRESS_COVERAGE_THRESHOLD = 2.0


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

    # Calibrate ONCE - rates are market-wide, not company-specific
    quarterly_sofr = get_quarterly_sofr_history(conn)
    current_sofr = quarterly_sofr[-1]
    params = calibrate_ou(quarterly_sofr)
    print(f"Calibration: kappa={params['kappa']:.3f}, theta={params['theta']:.2f}%, "
          f"sigma={params['sigma']:.2f}pp, starting SOFR={current_sofr:.2f}%")
    print()

    paths = simulate_paths(
        current_value=current_sofr, kappa=params["kappa"], theta=params["theta"],
        sigma=params["sigma"], horizon_periods=HORIZON_QUARTERS, n_paths=N_PATHS,
    )

    summary_rows = []

    for ticker in TICKERS:
        company_id = conn.execute("SELECT company_id FROM companies WHERE ticker = ?", (ticker,)).fetchone()[0]
        total_debt, _ = get_total_debt_balance(conn, ticker)
        cik = get_cik_for_ticker(ticker)
        _, adjusted_ebitda, _ = get_ebitda_proxy(cik)

        scenario_id = insert_scenario(
            conn, f"{ticker} SOFR stochastic {HORIZON_QUARTERS}q",
            f"Mean-reverting simulation, {N_PATHS} paths, {HORIZON_QUARTERS}q ahead, "
            f"kappa={params['kappa']:.3f}, theta={params['theta']:.2f}, sigma={params['sigma']:.2f}"
        )

        coverage_ratios = []
        for path_id, path in enumerate(paths):
            terminal_rate = path[-1]
            total_q, _, _ = total_quarterly_interest(conn, ticker, sofr_override=terminal_rate)
            annual_interest = total_q * 4
            coverage = adjusted_ebitda / annual_interest if annual_interest > 0 and adjusted_ebitda else None
            coverage_ratios.append(coverage)

            insert_path(conn, scenario_id, path_id, path)
            leverage = total_debt / adjusted_ebitda if adjusted_ebitda and adjusted_ebitda > 0 else None
            insert_result(conn, company_id, scenario_id, path_id, adjusted_ebitda,
                          annual_interest, total_debt, leverage, coverage)

        conn.commit()

        valid = [c for c in coverage_ratios if c is not None]
        breach_prob = float(np.mean(np.array(valid) < DISTRESS_COVERAGE_THRESHOLD)) if valid else None
        spread = max(valid) - min(valid) if valid else None

        summary_rows.append({
            "ticker": ticker, "median_coverage": np.median(valid) if valid else None,
            "spread": spread, "breach_prob": breach_prob,
        })

        print(f"{ticker}: median coverage {np.median(valid):.2f}x, "
              f"range across all paths: {spread:.3f}x wide, "
              f"P(coverage < {DISTRESS_COVERAGE_THRESHOLD}x) = {breach_prob:.1%}")

    print()
    print(f"{'Ticker':<8}{'Median Cov.':>13}{'Range width':>14}{'Breach Prob.':>14}")
    print("-" * 49)
    for r in summary_rows:
        print(f"{r['ticker']:<8}{r['median_coverage']:>12.2f}x{r['spread']:>13.3f}x{r['breach_prob']:>13.1%}")

    conn.close()
