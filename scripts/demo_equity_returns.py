"""
Computes a real, honest equity-return figure for Diebold Nixdorf: entry at
FY2024 (the first clean full fiscal year after its 2023 restructuring),
exit at FY2025 (the most recent clean full year), using real EBITDA
figures and a constant $1.25B debt balance (the same simplification used
throughout this project's historical replay).

ASSUMPTION flagged explicitly: the 6.0x EV/EBITDA multiple below is an
assumed, illustrative figure, not a real observed market valuation - we
haven't yet pulled real market cap / trading multiple data (that's future
work). The point here is to demonstrate the mechanism (leverage amplifies
equity returns), not to claim a precise real-world return figure.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engine.equity import equity_value, irr_approx, moic  # noqa: E402

TOTAL_DEBT = 1_250_000_000
ASSUMED_MULTIPLE = 6.0

ENTRY_EBITDA = 314_400_000  # FY2024 - first clean full year post-restructuring
EXIT_EBITDA = 369_500_000   # FY2025 - most recent clean full year
YEARS = 1  # FY2024 -> FY2025

if __name__ == "__main__":
    entry_equity = equity_value(ENTRY_EBITDA, ASSUMED_MULTIPLE, TOTAL_DEBT)
    exit_equity = equity_value(EXIT_EBITDA, ASSUMED_MULTIPLE, TOTAL_DEBT)

    ebitda_growth = (EXIT_EBITDA / ENTRY_EBITDA) - 1
    equity_growth = (exit_equity / entry_equity) - 1 if entry_equity > 0 else None

    print(f"Assumed EV/EBITDA multiple: {ASSUMED_MULTIPLE}x (illustrative, not a real observed multiple)")
    print()
    print(f"Entry (FY2024): EBITDA ${ENTRY_EBITDA:,.0f} x {ASSUMED_MULTIPLE}x = "
          f"EV ${ENTRY_EBITDA * ASSUMED_MULTIPLE:,.0f}")
    print(f"  Equity value = EV - Debt = ${ENTRY_EBITDA * ASSUMED_MULTIPLE:,.0f} - ${TOTAL_DEBT:,.0f} "
          f"= ${entry_equity:,.0f}")
    print()
    print(f"Exit (FY2025): EBITDA ${EXIT_EBITDA:,.0f} x {ASSUMED_MULTIPLE}x = "
          f"EV ${EXIT_EBITDA * ASSUMED_MULTIPLE:,.0f}")
    print(f"  Equity value = EV - Debt = ${EXIT_EBITDA * ASSUMED_MULTIPLE:,.0f} - ${TOTAL_DEBT:,.0f} "
          f"= ${exit_equity:,.0f}")
    print()

    m = moic(entry_equity, exit_equity)
    irr = irr_approx(m, YEARS)

    print(f"EBITDA growth:  {ebitda_growth:+.1%}")
    print(f"Equity growth:  {equity_growth:+.1%}")
    print(f"MOIC:           {m:.2f}x")
    print(f"IRR (1-year):   {irr:.1%}")
    print()
    print(f"Leverage amplification: {ebitda_growth:.1%} EBITDA growth became "
          f"{equity_growth:.1%} equity growth - roughly "
          f"{equity_growth / ebitda_growth:.1f}x amplified, purely from debt being fixed "
          f"while EBITDA grew on top of it.")
