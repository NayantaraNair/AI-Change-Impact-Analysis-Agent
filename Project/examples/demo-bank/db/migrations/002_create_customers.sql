-- Customer-service owns profile data and channel preferences.
BEGIN;

CREATE TABLE customers (
    id UUID PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL UNIQUE REFERENCES users(id),
    display_name VARCHAR(120) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone_number VARCHAR(16),
    phone_verified_at TIMESTAMPTZ,
    phone_verification_evidence UUID,
    phone_verified_by VARCHAR(120),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT customer_phone_format CHECK (phone_number ~ '^\+[1-9][0-9]{7,14}$'),
    CONSTRAINT customer_verification_evidence CHECK (
        (phone_verified_at IS NULL AND phone_verification_evidence IS NULL AND phone_verified_by IS NULL)
        OR (phone_verified_at IS NOT NULL AND phone_number IS NOT NULL
            AND phone_verification_evidence IS NOT NULL AND phone_verified_by IS NOT NULL)
    )
);

CREATE TABLE contact_preferences (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel VARCHAR(16) NOT NULL CHECK (channel IN ('sms', 'email')),
    purpose VARCHAR(24) NOT NULL CHECK (purpose IN ('marketing', 'service_updates')),
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (customer_id, channel, purpose)
);

CREATE INDEX ix_customers_email ON customers (email);
COMMENT ON COLUMN customers.phone_verification_evidence IS 'Reference to a staff-reviewed contact-evidence case';
COMMIT;
