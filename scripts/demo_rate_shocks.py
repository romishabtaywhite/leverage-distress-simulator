"""
Phase 3, step 1: deterministic rate shocks.

Different from the historical replay we already built: instead of walking
through REAL rate history over time, this asks a single hypothetical
question at today's snapshot: "if SOFR were X basis points higher or
lower than it actually is right now, what would happen to this company's
interest bill, leverage, and coverage?"

Also: this is the first script that WRITES into the rate_scenarios and
simulation_results tables that have sat empty in the schema since Phase 1
- starting to actually use the part of the database built for exactly
this purpose.
"""

import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from engine.company_interest import (  # noqa: E402
    get_latest_rate,
    get_total_debt_balance,
    total_quarterly_interest,
)
from engine.ebitda import get_ebitda_proxy  # noqa: E402

TICKER = "BHC"
SHOCKS_BPS = [-100, 0, 200, 400, 600]  # 0 = no shock, i.e. today's real rate


def get_cik_for_ticker(ticker):
    for c in CANDIDATES:
        if c["ticker"] == ticker:
            return c["cik"]
    raise ValueError(f"{ticker} not found in candidate_companies.py")


def get_or_create_company_id(conn, ticker):
    row = conn.execute("SELECT company_id FROM companies WHERE ticker = ?", (ticker,)).fetchone()
    return row[0]


def insert_scenario(conn, name, description):
    cur = conn.execute(
        "INSERT INTO rate_scenarios (scenario_name, scenario_type, description) VALUES (?, ?, ?)",
        (name, "deterministic_shock", description),
    )
    return cur.lastrowid


def insert_result(conn, company_id, scenario_id, ebitda, annual_interest, total_debt, leverage, coverage):
    conn.execute(
        """INSERT INTO simulation_results
           (company_id, scenario_id, path_id, period_index, obs_date,
            ebitda, interest_expense, total_debt_balance, leverage_ratio,
            interest_coverage_ratio, covenant_breach_flag)
           VALUES (?, ?, 0, 0, ?, ?, ?, ?, ?, ?, 0)""",
        (company_id, scenario_id, str(date.today()), ebitda, annual_interest,
         total_debt, leverage, coverage),
    )


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    company_id = get_or_create_company_id(conn, TICKER)
    current_sofr = get_latest_rate(conn, "SOFR")
    total_debt, _ = get_total_debt_balance(conn, TICKER)

    cik = get_cik_for_ticker(TICKER)
    ebitda, adjusted_ebitda, _ = get_ebitda_proxy(cik)

    print(f"{TICKER}: current real SOFR = {current_sofr:.2f}%, total debt = ${total_debt:,.0f}, "
          f"Adjusted EBITDA = ${adjusted_ebitda:,.0f}")
    print()
    print(f"{'Shock':<10}{'SOFR used':>11}{'Ann. interest':>16}{'Leverage':>11}{'Coverage':>11}")
    print("-" * 59)

    for shock_bps in SHOCKS_BPS:
        scenario_sofr = current_sofr + (shock_bps / 100)
        total_q, _, _ = total_quarterly_interest(conn, TICKER, sofr_override=scenario_sofr)
        annual_interest = total_q * 4

        leverage = total_debt / adjusted_ebitda if adjusted_ebitda and adjusted_ebitda > 0 else None
        coverage = adjusted_ebitda / annual_interest if adjusted_ebitda and adjusted_ebitda > 0 and annual_interest > 0 else None

        shock_label = "base case" if shock_bps == 0 else f"{shock_bps:+d} bps"
        leverage_str = f"{leverage:.2f}x" if leverage is not None else "undefined"
        coverage_str = f"{coverage:.2f}x" if coverage is not None else "undefined"

        print(f"{shock_label:<10}{scenario_sofr:>10.2f}%{annual_interest:>16,.0f}"
              f"{leverage_str:>11}{coverage_str:>11}")

        scenario_name = f"{TICKER} SOFR {shock_label}"
        scenario_id = insert_scenario(
            conn, scenario_name,
            f"Deterministic shock: SOFR {'+' if shock_bps >= 0 else ''}{shock_bps} bps from today's real rate"
        )
        insert_result(conn, company_id, scenario_id, adjusted_ebitda, annual_interest, total_debt, leverage, coverage)

    conn.commit()
    print()
    print("All 5 scenarios saved to rate_scenarios + simulation_results.")
    conn.close()
