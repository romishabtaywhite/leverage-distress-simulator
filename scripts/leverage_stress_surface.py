"""
Phase 4b: the leverage x rate-stress breach-probability surface.

Different question from anything built so far: Phase 3 asked "what if
rates moved, holding this company's REAL leverage fixed?" This asks the
reverse: "holding this company's REAL EBITDA and REAL floating-rate
spread fixed, what if it had been levered at a DIFFERENT multiple -
combined with real calibrated rate uncertainty - at what point does
distress become likely?"

This is the classic "how much leverage is too much" question, but
answered with this specific company's own real cash-generating capacity
and real cost of debt, not a generic industry rule of thumb. It produces
a genuine two-dimensional result (leverage x rate uncertainty), not a
restatement of anything already computed - each hypothetical leverage
level requires its own fresh 500-path simulation.

Party City is deliberately EXCLUDED here: it has zero floating-rate debt,
so a rate-uncertainty surface doesn't meaningfully apply to it - the same
honest reason it's been treated as a "demand-driven, not rate-driven"
contrast case throughout this project.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from engine.ebitda import get_ebitda_proxy  # noqa: E402
from engine.interest import floating_rate_interest  # noqa: E402
from engine.scenarios import calibrate_ou, simulate_paths  # noqa: E402

HORIZON_QUARTERS = 8
N_PATHS = 500
DISTRESS_COVERAGE_THRESHOLD = 2.0
LEVERAGE_MULTIPLES = [2, 3, 4, 5, 6, 7, 8, 9, 10]

# Real disclosed primary floating-rate tranche terms for each company -
# used to price a HYPOTHETICAL balance at this company's own real cost of
# debt, not a generic assumption.
COMPANIES = {
    "DBD": {"spread_bps": 750, "floor_pct": 0.0, "real_leverage": 3.38},
    "BHC": {"spread_bps": 625, "floor_pct": 0.0, "real_leverage": 3.00},
    "CYH": {"spread_bps": 200, "floor_pct": 0.0, "real_leverage": 1.57},
}


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


def find_breakeven_leverage(multiples, breach_probs):
    """Linear interpolation to find the leverage multiple where breach
    probability crosses 50%. Returns None if it never crosses in the
    tested range (always above or always below 50%)."""
    for i in range(len(multiples) - 1):
        if breach_probs[i] < 0.5 <= breach_probs[i + 1]:
            x0, x1 = multiples[i], multiples[i + 1]
            y0, y1 = breach_probs[i], breach_probs[i + 1]
            return x0 + (0.5 - y0) * (x1 - x0) / (y1 - y0)
    return None


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS leverage_stress_surface (
        ticker TEXT NOT NULL, leverage_multiple REAL NOT NULL,
        breach_probability REAL NOT NULL, n_paths INTEGER NOT NULL,
        horizon_quarters INTEGER NOT NULL,
        PRIMARY KEY (ticker, leverage_multiple))""")

    quarterly_sofr = get_quarterly_sofr_history(conn)
    current_sofr = quarterly_sofr[-1]
    params = calibrate_ou(quarterly_sofr)
    print(f"Calibration (shared across all companies): kappa={params['kappa']:.3f}, "
          f"theta={params['theta']:.2f}%, sigma={params['sigma']:.2f}pp")
    print()

    results = {}

    for ticker, info in COMPANIES.items():
        cik = get_cik_for_ticker(ticker)
        _, adjusted_ebitda, _ = get_ebitda_proxy(cik)

        print(f"{ticker} (real EBITDA ${adjusted_ebitda:,.0f}, spread {info['spread_bps']}bps):")
        breach_probs = []

        for multiple in LEVERAGE_MULTIPLES:
            hypothetical_balance = multiple * adjusted_ebitda

            # Fresh 500-path simulation for EACH leverage level - this is
            # the genuinely new two-dimensional exploration, not a reuse
            # of Phase 3's single-leverage-level paths.
            paths = simulate_paths(
                current_value=current_sofr, kappa=params["kappa"], theta=params["theta"],
                sigma=params["sigma"], horizon_periods=HORIZON_QUARTERS, n_paths=N_PATHS,
            )

            breaches = 0
            for path in paths:
                terminal_rate = path[-1]
                r = floating_rate_interest(
                    balance=hypothetical_balance, spread_bps=info["spread_bps"],
                    reference_rate_pct=terminal_rate, floor_pct=info["floor_pct"],
                )
                coverage = adjusted_ebitda / r["annual_interest"]
                if coverage < DISTRESS_COVERAGE_THRESHOLD:
                    breaches += 1

            breach_prob = breaches / N_PATHS
            breach_probs.append(breach_prob)

            conn.execute(
                "INSERT OR REPLACE INTO leverage_stress_surface "
                "(ticker, leverage_multiple, breach_probability, n_paths, horizon_quarters) "
                "VALUES (?, ?, ?, ?, ?)",
                (ticker, multiple, breach_prob, N_PATHS, HORIZON_QUARTERS),
            )

            print(f"  {multiple}x EBITDA -> P(breach) = {breach_prob:.1%}")

        conn.commit()
        results[ticker] = breach_probs
        print()

    conn.close()

    print("=" * 65)
    print("BREAKEVEN LEVERAGE (where simulated breach probability crosses 50%)")
    print("=" * 65)
    for ticker, info in COMPANIES.items():
        breakeven = find_breakeven_leverage(LEVERAGE_MULTIPLES, results[ticker])
        real_lev = info["real_leverage"]
        if breakeven is not None:
            margin = breakeven - real_lev
            print(f"{ticker}: breakeven ~{breakeven:.1f}x, real leverage {real_lev:.2f}x "
                  f"-> {margin:+.1f} turns of headroom before this company's own real cash flows,")
            print(f"       under real calibrated rate uncertainty, would statistically tip into distress.")
        else:
            direction = "above" if results[ticker][-1] < 0.5 else "below"
            print(f"{ticker}: breach probability stayed {direction} 50% across the entire "
                  f"{LEVERAGE_MULTIPLES[0]}x-{LEVERAGE_MULTIPLES[-1]}x range tested "
                  f"(real leverage {real_lev:.2f}x) - no breakeven found in this range.")
