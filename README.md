# Leveraged Finance Distress Simulator

**Live interactive write-up:** https://leverage-distress-simulator.netlify.app

**Research question:** Given a real leveraged capital structure with floating-rate
(SOFR-indexed) debt, how did the 2020–2026 rate cycle affect interest coverage,
covenant headroom, and equity returns — and can a simulated, mechanism-grounded
breach-probability signal predict financial distress better than static leverage
ratios alone?

Built end-to-end on real data: SEC EDGAR (XBRL financial disclosures) and FRED
(SOFR + credit spread history) — no synthetic or downloaded-once datasets.

---

## Headline findings

| Company | Leverage | Coverage | Status |
|---|---|---|---|
| Diebold Nixdorf (DBD) | 3.38x | 2.60x | Chapter 11 2023, survived — covenant-lite post-restructuring |
| Bausch Health (BHC) | 3.00x | 3.50x | Currently levered, not in default |
| Community Health Systems (CYH) | 1.57x* | 6.92x | Currently levered, not in default (*partial debt data — see caveats) |
| Party City (PRTYQ) | 11.48x | 1.00x | Chapter 11 twice, fully liquidated 2025 |

- **Party City's raw GAAP EBITDA was -$797M**, dominated by an $862.5M one-time impairment. Adjusted for it, EBITDA is +$65.3M, giving the 11.48x/1.00x above — coverage of almost exactly 1.00x, weeks before its actual bankruptcy filing.
- **A calibrated stochastic rate model** (500 simulated 2-year paths per company) found Party City's coverage at *exactly* 1.00x in every single path — mathematically confirming zero rate sensitivity, since both its tranches are fixed-rate. Its distress was demand-driven, not rate-driven — a deliberate contrast case in this dataset.
- **A real classifier trained on 14 labeled companies** (5 distressed, 9 not) scored 64.3% accuracy — identical to the "always guess the majority class" baseline. A permutation test (2,000 reshuffles) confirms this is **not statistically distinguishable from chance** (p=0.278). Its AUC of 0.422 is actually below 0.5, driven by a genuine small-sample extrapolation failure on the dataset's most extreme point.
- **A leverage-stress surface** (varying hypothetical leverage 2x–10x against calibrated rate uncertainty, holding each company's real EBITDA and spread fixed) gives company-specific breakeven leverage: DBD ~4.5x, BHC ~4.9x, CYH ~8.5x — real, mechanism-derived risk thresholds, not generic rules of thumb.

Full detail, interactive charts, and the complete debugging log are in the live write-up linked above.

---

## Project structure

```
leverage-distress-simulator/
├── README.md
├── requirements.txt
├── .env.example
├── db/
│   ├── schema.sql
│   └── leverage_sim.db              (created locally, gitignored)
├── data/
│   ├── raw/                          (gitignored)
│   └── cache/                        (gitignored — EDGAR API response cache)
├── docs/
│   └── index.html                    (GitHub Pages mirror of the live write-up)
├── src/
│   ├── data_ingest/
│   │   ├── edgar_client.py           SEC EDGAR API client, CIK lookup, XBRL extraction
│   │   ├── fred_client.py            FRED API client (SOFR, credit spreads)
│   │   ├── candidate_companies.py    The 4 deep-research case-study companies
│   │   └── ml_dataset_companies.py   24 more companies for the broader ML dataset
│   └── engine/
│       ├── interest.py               Core floating/fixed interest calculation
│       ├── company_interest.py       Sums interest across a company's tranches
│       ├── ebitda.py                 EBITDA extraction incl. Adjusted EBITDA add-backs
│       ├── equity.py                 Enterprise/equity value, MOIC, IRR
│       ├── scenarios.py              Calibrated mean-reverting rate model + simulation
│       └── static_features.py        Standardized total debt / interest expense pull
└── scripts/
    ├── init_db.py                    Creates the database from schema.sql
    ├── seed_debt_data.py              Loads real researched debt tranches + covenants
    ├── load_fred_to_db.py             Loads FRED rate history into the database
    ├── compare_all_companies.py       Cross-company leverage/coverage snapshot
    ├── demo_equity_returns.py          Equity value / MOIC / IRR walkthrough
    ├── historical_covenant_replay.py   Full historical replay for one company
    ├── demo_rate_shocks.py             Deterministic rate shock scenarios
    ├── demo_stochastic_all_companies.py  Calibrated stochastic simulation, all companies
    ├── build_ml_dataset.py             Builds the 28-company standardized ML dataset
    ├── train_classifier.py             LOOCV classifier + permutation test + AUC
    ├── illustrative_feature_comparison.py  n=4 static-vs-simulated feature comparison
    └── leverage_stress_surface.py      Leverage x rate-stress breach-probability surface
```

A handful of smaller step-by-step scripts used while first building the engine
(`demo_one_tranche.py`, `demo_leverage_ratio.py`, etc.) are also in `scripts/` —
kept as a readable record of how the engine was built up piece by piece, not
because they're needed to reproduce the final results.

---

## Setup

1. Clone this repo and `cd` into it.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate      # on Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in:
   - `FRED_API_KEY` — free, register at https://fred.stlouisfed.org/docs/api/api_key.html
   - `SEC_EDGAR_USER_AGENT` — your name + email (SEC requires this, no key needed)
5. Initialize the database:
   ```bash
   python scripts/init_db.py
   ```

## Reproducing the results, phase by phase

**Phase 1 — data infrastructure**
```bash
python scripts/load_fred_to_db.py      # loads real SOFR + credit spread history
python scripts/seed_debt_data.py       # loads the 4 companies' real researched debt tranches
```

**Phase 2 — interest, EBITDA, covenant engine**
```bash
python scripts/compare_all_companies.py   # real leverage/coverage across all 4 companies
python scripts/demo_equity_returns.py     # equity value / MOIC / IRR walkthrough
```

**Phase 3 — rate scenarios**
```bash
python scripts/demo_rate_shocks.py               # deterministic shock scenarios
python scripts/demo_stochastic_all_companies.py  # calibrated 500-path simulation, all companies
```

**Phase 4 — ML distress prediction**
```bash
python scripts/build_ml_dataset.py                  # builds the 28-company standardized dataset
python scripts/train_classifier.py                  # LOOCV classifier + permutation test + AUC
python scripts/illustrative_feature_comparison.py    # n=4 static-vs-simulated comparison
python scripts/leverage_stress_surface.py            # leverage x rate-stress breach surface
```

---

## Data sources

- **SEC EDGAR** (`data.sec.gov`) — free, no API key, requires a descriptive `User-Agent` header. Used for all company financial disclosures (XBRL).
- **FRED** (Federal Reserve Economic Data) — free API key required. Used for SOFR and ICE BofA credit spread index history.

No paid data (PitchBook, S&P LCD, Bloomberg) was used anywhere in this project — every figure traces back to a public filing or a free government API.

---

## Known limitations (stated honestly, not hidden)

- **CYH's total debt in the deep-research dataset is understated** — only 3 of its disclosed tranches were captured (real total closer to $11.4B, not the ~$3.0B reflected in leverage calculations built on that dataset). The standardized ML dataset (built independently via EDGAR tags) does not have this issue.
- **The ML classifier (n=14) is honestly underpowered** — its result is not statistically distinguishable from chance. This is stated as a finding, not smoothed over.
- **The simulated breach-probability feature only exists for the 4 deep-research companies** — extending it to the other 24 would require the same tranche-level manual research, not yet done.
- **J.C. Penney was excluded entirely** — its EDGAR company-facts data returns a 404, likely predating this API's coverage.
- Several genuinely distressed companies (WeWork, Rite Aid, Big Lots, Joann, Avaya) were excluded from the ML dataset because they had real negative EBITDA in their bankruptcy year — a true economic signal, not a data gap, but one the leverage/coverage ratio framework can't represent as a finite multiple.

---

## What's next

Phases 1–4 are complete. Remaining: further polish of the write-up and CV
packaging. See the live write-up linked at the top for full narrative detail,
the complete debugging log, and interactive charts.
