-- Leverage Distress Simulator: core schema
-- Written for SQLite (works with minimal changes on Postgres too).

CREATE TABLE IF NOT EXISTS companies (
    company_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    ticker          TEXT,
    cik             TEXT UNIQUE,          -- zero-padded 10-digit SEC CIK, stored as text
    sector          TEXT,
    sic_code        TEXT,
    is_distressed   INTEGER DEFAULT 0,    -- 1 if company had a default/Chapter 11/distressed exchange in your labeling window
    distress_date   TEXT,                 -- ISO date if applicable
    notes           TEXT
);

-- One row per disclosed debt tranche (from 10-K debt footnotes)
CREATE TABLE IF NOT EXISTS debt_tranches (
    tranche_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(company_id),
    tranche_name        TEXT NOT NULL,        -- e.g. "Term Loan B", "5.5% Senior Notes due 2028"
    tranche_type        TEXT NOT NULL,        -- revolver | term_loan | senior_notes | sub_notes
    rate_type           TEXT NOT NULL,        -- floating | fixed
    reference_rate       TEXT,                 -- e.g. "SOFR" (null if fixed)
    spread_bps          REAL,                 -- spread over reference rate, in basis points
    rate_floor_pct      REAL,                 -- floor on the floating rate, if disclosed
    fixed_rate_pct      REAL,                 -- coupon if fixed rate
    original_balance     REAL,
    as_of_date           TEXT,                 -- filing date this balance is from
    maturity_date        TEXT,
    seniority_rank       INTEGER,              -- 1 = most senior, used for cash-sweep waterfall order
    source_accession      TEXT                  -- SEC accession number this was sourced from, for traceability
);

-- Disclosed covenant terms, including step schedules (leverage covenants often step down over time)
CREATE TABLE IF NOT EXISTS covenant_terms (
    covenant_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(company_id),
    tranche_id      INTEGER REFERENCES debt_tranches(tranche_id),
    covenant_type   TEXT NOT NULL,     -- leverage_ratio | interest_coverage | fixed_charge_coverage
    threshold_value REAL NOT NULL,
    effective_date  TEXT,
    expiry_date     TEXT
);

-- Raw financial facts pulled from SEC EDGAR XBRL (one row per company/period/concept)
CREATE TABLE IF NOT EXISTS financial_facts (
    fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(company_id),
    fiscal_period   TEXT NOT NULL,     -- e.g. "CY2023Q4" or "CY2023"
    concept         TEXT NOT NULL,     -- e.g. "Revenues", "InterestExpense", "OperatingIncomeLoss"
    value           REAL,
    unit            TEXT,              -- e.g. "USD"
    filed_date      TEXT
);

-- Macro rate series pulled from FRED (SOFR, HY OAS, etc.)
CREATE TABLE IF NOT EXISTS rate_series (
    series_code     TEXT NOT NULL,     -- e.g. "SOFR", "BAMLH0A0HYM2"
    obs_date        TEXT NOT NULL,
    value           REAL,
    PRIMARY KEY (series_code, obs_date)
);

-- Scenario definitions (historical replay, deterministic shocks, stochastic paths)
CREATE TABLE IF NOT EXISTS rate_scenarios (
    scenario_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_name   TEXT NOT NULL,
    scenario_type   TEXT NOT NULL,     -- historical | deterministic_shock | stochastic
    description     TEXT
);

-- Individual simulated rate paths belonging to a scenario (a stochastic scenario has many paths)
CREATE TABLE IF NOT EXISTS scenario_rate_paths (
    scenario_id     INTEGER NOT NULL REFERENCES rate_scenarios(scenario_id),
    path_id         INTEGER NOT NULL,   -- 0 for deterministic/historical scenarios, 0..N for stochastic draws
    period_index    INTEGER NOT NULL,   -- period counter within the simulation
    obs_date        TEXT,
    rate_value      REAL NOT NULL,
    PRIMARY KEY (scenario_id, path_id, period_index)
);

-- Output of Phase 2/3: the debt schedule + covenant engine run across each scenario/path
CREATE TABLE IF NOT EXISTS simulation_results (
    result_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id              INTEGER NOT NULL REFERENCES companies(company_id),
    scenario_id              INTEGER NOT NULL REFERENCES rate_scenarios(scenario_id),
    path_id                  INTEGER NOT NULL,
    period_index             INTEGER NOT NULL,
    obs_date                 TEXT,
    ebitda                   REAL,
    interest_expense         REAL,
    free_cash_flow           REAL,
    total_debt_balance       REAL,
    leverage_ratio           REAL,     -- Net Debt / EBITDA
    interest_coverage_ratio  REAL,     -- EBITDA / Interest Expense
    covenant_breach_flag     INTEGER DEFAULT 0,
    equity_value             REAL
);

CREATE INDEX IF NOT EXISTS idx_tranches_company ON debt_tranches(company_id);
CREATE INDEX IF NOT EXISTS idx_facts_company ON financial_facts(company_id, concept);
CREATE INDEX IF NOT EXISTS idx_results_company_scenario ON simulation_results(company_id, scenario_id);
