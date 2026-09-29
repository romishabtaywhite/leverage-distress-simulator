"""
Phase 4, illustrative piece: does the simulated breach-probability feature
(from Phase 3's stochastic simulation) separate distressed from
non-distressed companies better than static leverage/coverage ratios
alone?

DELIBERATELY NOT a trained classifier with an accuracy number: with only
4 companies, even Leave-One-Out CV produces an "accuracy" that can only
land on 0%, 25%, 50%, 75%, or 100% - a single flipped prediction swings
the whole figure by 25 points. Reporting that as if it were a real,
stable metric would be worse than not reporting anything - a classic
case of false precision. This is a qualitative, honest look at the raw
numbers instead: does the feature actually separate the two real classes
we have, looking directly at the values?

Uses the deep tranche-research figures from Phase 2/3 (not the
standardized ml_dataset figures from the broader 28-company set) since
those are what the Phase 3 breach-probability simulation was itself
built from - mixing the two bases would be an inconsistent comparison.
"""

DATA = [
    {"ticker": "DBD", "is_distressed": 1, "leverage": 3.38, "coverage": 2.60, "breach_prob": 0.8},
    {"ticker": "BHC", "is_distressed": 0, "leverage": 3.00, "coverage": 3.50, "breach_prob": 0.0},
    {"ticker": "CYH", "is_distressed": 0, "leverage": 1.57, "coverage": 6.92, "breach_prob": 0.0},
    {"ticker": "PRTYQ", "is_distressed": 1, "leverage": 11.48, "coverage": 1.00, "breach_prob": 100.0},
]

if __name__ == "__main__":
    print(f"{'Ticker':<8}{'Distressed?':<13}{'Leverage':>10}{'Coverage':>10}{'Breach Prob.':>14}")
    print("-" * 55)
    for d in DATA:
        flag = "Yes" if d["is_distressed"] else "No"
        print(f"{d['ticker']:<8}{flag:<13}{d['leverage']:>9.2f}x{d['coverage']:>9.2f}x"
              f"{d['breach_prob']:>13.1f}%")

    print()
    print("QUALITATIVE READ (n=4 - too small for a formal accuracy metric; this is a direct")
    print("look at whether each feature actually separates the two real outcomes we have):")
    print()
    print("STATIC RATIOS: PRTYQ (11.48x / 1.00x) stands out clearly. But DBD (3.38x / 2.60x)")
    print("sits comfortably between BHC and CYH's healthy-looking numbers - static ratios alone")
    print("do NOT separate DBD from the non-distressed group. That's not a flaw in the ratios -")
    print("it's because DBD's CURRENT numbers genuinely are healthy; its restructuring worked.")
    print()
    print("BREACH PROBABILITY: PRTYQ's 100% is unambiguous and mechanism-grounded, not just a")
    print("high ratio - it's the direct output of simulating real debt terms across calibrated")
    print("future rate paths. But DBD still reads as low-risk (0.8%), same as BHC and CYH -")
    print("the simulation doesn't fix DBD's case either, for the same honest reason: today's")
    print("real risk IS low. Both approaches agree on DBD precisely because both are looking")
    print("at DBD's genuinely recovered current state, not its resolved past.")
    print()
    print("THE REAL DIFFERENTIATOR: for PRTYQ specifically, the simulated feature converts an")
    print("ambiguous static picture (high leverage, weak coverage - concerning, but not obviously")
    print("'this will fail') into a stark, actionable signal (100% breach probability under")
    print("calibrated real rate uncertainty) - because it models the underlying mechanism")
    print("directly, rather than comparing one snapshot to a historical average. That is a real,")
    print("meaningful advantage, but it's a claim about ONE company's clarity, not a validated")
    print("population-level classifier result - n=4 cannot support the latter, and this piece")
    print("does not pretend otherwise.")
