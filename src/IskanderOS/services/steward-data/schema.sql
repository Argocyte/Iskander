-- steward-data schema — iskander_ledger database
-- Run once on first startup. Idempotent (IF NOT EXISTS throughout).
--
-- Tables are insert/update only by the treasurer tooling.
-- steward-data has SELECT-only access via the steward_data role.

-- ---------------------------------------------------------------------------
-- Accounts — the cooperative's named bank/reserve accounts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ledger_accounts (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL UNIQUE,   -- e.g. "Operating", "Reserve"
    balance     NUMERIC(14,2) NOT NULL DEFAULT 0,
    currency    CHAR(3)     NOT NULL DEFAULT 'GBP',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Transactions — aggregate financial activity (no individual attribution)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS financial_transactions (
    id               SERIAL PRIMARY KEY,
    transaction_date DATE        NOT NULL,
    category         TEXT        NOT NULL,  -- e.g. 'member_contribution', 'rent'
    amount           NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    direction        TEXT        NOT NULL CHECK (direction IN ('credit', 'debit')),
    description      TEXT        NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ft_date ON financial_transactions (transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_ft_category ON financial_transactions (category);

-- ---------------------------------------------------------------------------
-- Annual budget — optional, enables variance reporting
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS financial_year_budget (
    financial_year       CHAR(9)       PRIMARY KEY,  -- e.g. '2025-2026'
    budget_income        NUMERIC(14,2),
    budget_expenditure   NUMERIC(14,2),
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Compliance deadlines — regulatory and governance filing dates
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS compliance_deadlines (
    id          SERIAL PRIMARY KEY,
    title       TEXT    NOT NULL,
    due_date    DATE    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    consequence TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'upcoming'
                CHECK (status IN ('upcoming', 'overdue', 'completed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cd_due_date ON compliance_deadlines (due_date);
CREATE INDEX IF NOT EXISTS idx_cd_status   ON compliance_deadlines (status);
