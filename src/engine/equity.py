"""
Equity value and return calculations - the last piece of Phase 2.

Core idea: Enterprise Value = EBITDA x Multiple, and Equity Value =
Enterprise Value - Debt. Since debt is (roughly) fixed while EBITDA moves,
all EBITDA growth flows entirely into the equity slice - this is why
equity in a leveraged company is a leveraged, amplified claim on business
growth. That amplification is the whole reason leverage exists in private
equity.
"""


def enterprise_value(ebitda, multiple):
    return ebitda * multiple


def equity_value(ebitda, multiple, total_debt):
    """Equity Value = Enterprise Value - Debt. Can be negative if debt
    exceeds enterprise value entirely - a real, meaningful signal (equity
    holders would get nothing in that scenario), not an error."""
    return enterprise_value(ebitda, multiple) - total_debt


def moic(entry_equity, exit_equity):
    """Multiple on Invested Capital: how many times the equity investment
    multiplied. Undefined if entry equity was zero or negative - you can't
    meaningfully multiply from a starting point of zero or less."""
    if entry_equity is None or entry_equity <= 0:
        return None
    return exit_equity / entry_equity


def irr_approx(moic_value, years):
    """
    Simplified IRR: assumes a single entry and single exit with no interim
    cash flows (no dividends, no interim paydown distributions) - a real
    LBO model would account for those. This is the annualized growth rate
    that would turn entry equity into exit equity over the given period.
    """
    if moic_value is None or moic_value <= 0 or years <= 0:
        return None
    return moic_value ** (1 / years) - 1
