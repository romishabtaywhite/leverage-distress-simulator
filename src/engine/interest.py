"""
The single most important calculation in this whole project: how much
interest a debt tranche costs for one period, given a reference rate.

Everything else in Phase 2 (the cash flow waterfall, the covenant tests,
running this across many quarters and many rate scenarios) is just this
same calculation applied over and over. Get this function right and
understood, and the rest is mechanical repetition of it.
"""


def floating_rate_interest(balance, spread_bps, reference_rate_pct, floor_pct=None):
    """
    Calculates interest for a FLOATING rate tranche (e.g. "SOFR + 6.25%").

    Plain-English walkthrough of the math:
      1. spread_bps is the fixed spread in "basis points" - finance's way of
         writing percentages very precisely. 100 basis points = 1.00%.
         So 625 basis points = 6.25%. We convert it to a percentage here.
      2. If a floor is specified (e.g. "the reference rate can't be treated
         as less than 0% for this loan"), we apply it - this just protects
         the lender if the reference rate ever went negative.
      3. effective_rate = reference rate + spread. This is the actual
         all-in interest rate the company pays this period.
      4. annual_interest = balance * effective_rate. This is what one full
         year of interest would cost at this rate.
      5. quarterly_interest = annual_interest / 4, since companies report
         (and often pay) interest every quarter, not once a year.

    Args:
        balance: outstanding principal balance of the tranche, in dollars
                 (e.g. 3_000_000_000 for $3 billion)
        spread_bps: the fixed spread over the reference rate, in basis
                    points (e.g. 625 for 6.25%)
        reference_rate_pct: the current reference rate (e.g. SOFR) as a
                             percentage (e.g. 4.33 for 4.33%)
        floor_pct: optional minimum the reference rate is treated as, as a
                   percentage (e.g. 0.0). None means no floor.

    Returns:
        A dictionary with every step of the calculation spelled out, so you
        can see exactly how the final number was reached - not just the
        answer, but the working.
    """
    spread_pct = spread_bps / 100.0

    effective_reference_rate = reference_rate_pct
    if floor_pct is not None and reference_rate_pct < floor_pct:
        effective_reference_rate = floor_pct

    effective_rate_pct = effective_reference_rate + spread_pct

    annual_interest = balance * (effective_rate_pct / 100.0)
    quarterly_interest = annual_interest / 4

    return {
        "balance": balance,
        "reference_rate_pct": reference_rate_pct,
        "floor_pct": floor_pct,
        "effective_reference_rate": effective_reference_rate,
        "spread_pct": spread_pct,
        "effective_rate_pct": effective_rate_pct,
        "annual_interest": annual_interest,
        "quarterly_interest": quarterly_interest,
    }


def fixed_rate_interest(balance, fixed_rate_pct):
    """
    The much simpler counterpart: interest for a FIXED rate tranche (e.g.
    Bausch Health's 10.00% Senior Secured Notes). No reference rate, no
    spread - just the fixed coupon applied straight to the balance.
    """
    annual_interest = balance * (fixed_rate_pct / 100.0)
    quarterly_interest = annual_interest / 4

    return {
        "balance": balance,
        "fixed_rate_pct": fixed_rate_pct,
        "annual_interest": annual_interest,
        "quarterly_interest": quarterly_interest,
    }
