"""
Starting shortlist of real, publicly-filing companies worth researching as
case studies. All are picked because they are (a) public SEC filers, so
their debt footnotes are pullable via EDGAR, and (b) carried meaningful
leveraged/floating-rate debt through the 2022-2024 rate cycle.

IMPORTANT: verify current facts yourself before relying on these - filing
status, debt structure, and distress outcomes can change, and this list is
a research starting point, not a verified dataset. Confirm each company's
actual debt footnote (10-K, "Debt" or "Long-Term Debt" note) before treating
any tranche detail as fact.

Add your own as you research using EDGAR full-text search:
https://www.sec.gov/edgar/search/  -- try phrases like "Term Loan B" AND "SOFR"
combined with a sector/date filter to find more candidates.
"""

CANDIDATES = [
    {
        "ticker": "PRTYQ",  # Party City Holdco - ticker changed post-Chapter 11 (Jan 2023)
        "name": "Party City Holdco Inc.",
        "notes": "Filed Chapter 11 Jan 2023. Good real example of a public company "
                 "with disclosed floating-rate term loan debt and a documented distress event.",
    },
    {
        "ticker": "DBD",
        "name": "Diebold Nixdorf Inc.",
        "notes": "Restructured in 2023 (Chapter 11 in the US, scheme of arrangement in the UK). "
                 "Heavily levered industrial/tech company, useful non-PE-sponsor comparison case.",
    },
    {
        "ticker": "BHC",
        "name": "Bausch Health Companies Inc.",
        "notes": "Highly levered post-Valeant, large floating-rate term loan exposure, "
                 "faced credit stress through the rate-hike period. Verify current status.",
    },
    {
        "ticker": "CYH",
        "name": "Community Health Systems Inc.",
        "notes": "Heavily levered hospital operator with disclosed floating-rate term loan "
                 "facilities. Useful for a healthcare-sector comparison.",
    },
    {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "notes": "NOT a leverage case study - included only as a low-leverage 'control' "
                 "company if you want a contrast case, and as the smoke-test ticker in "
                 "edgar_client.py.",
    },
]
