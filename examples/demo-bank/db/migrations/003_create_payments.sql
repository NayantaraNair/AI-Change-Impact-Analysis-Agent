-- Payment-service owns transfer instructions and daily allowance reservations.
-- Account IDs refer to the core ledger, which is outside this demo folder.
BEGIN;

CREATE TABLE payments (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL,
    beneficiary_reference VARCHAR(120) NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'AED' CHECK (currency = 'AED'),
    status VARCHAR(24) NOT NULL DEFAULT 'ACCEPTED'
        CHECK (status IN ('ACCEPTED', 'SETTLED', 'FAILED')),
    request_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (account_id, request_id)
);

CREATE INDEX ix_payments_account_created ON payments (account_id, created_at DESC);

CREATE TABLE daily_limit_usage (
    id VARCHAR(80) PRIMARY KEY,
    account_id UUID NOT NULL,
    usage_date DATE NOT NULL,
    used_amount NUMERIC(18, 2) NOT NULL DEFAULT 0 CHECK (used_amount >= 0),
    UNIQUE (account_id, usage_date)
);

COMMENT ON COLUMN daily_limit_usage.usage_date IS 'Calendar day in Asia/Dubai';
COMMENT ON COLUMN daily_limit_usage.used_amount IS 'AED amount reserved by accepted transfers';
-- The AED 25,000 standard ceiling is enforced by DailyLimitPolicy.
-- No numeric ceiling is embedded here, so a policy change needs no table rewrite.
COMMIT;
