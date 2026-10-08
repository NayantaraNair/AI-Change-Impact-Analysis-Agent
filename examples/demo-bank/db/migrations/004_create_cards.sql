-- Card-service owns display metadata and customer-controlled card status.
-- Full card numbers and security values are held by the card processor.
BEGIN;

CREATE TABLE cards (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(id),
    account_id UUID NOT NULL,
    processor_reference VARCHAR(120) NOT NULL UNIQUE,
    last_four VARCHAR(4) NOT NULL CHECK (last_four ~ '^[0-9]{4}$'),
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED')),
    frozen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version BIGINT NOT NULL DEFAULT 0,
    CONSTRAINT frozen_card_timestamp CHECK (status <> 'FROZEN' OR frozen_at IS NOT NULL)
);

CREATE INDEX ix_cards_customer ON cards (customer_id);
CREATE INDEX ix_cards_account ON cards (account_id);

COMMENT ON COLUMN cards.processor_reference IS 'Opaque card processor identifier';
COMMENT ON COLUMN cards.frozen_at IS 'UTC timestamp of the latest customer freeze';
COMMENT ON COLUMN cards.version IS 'Optimistic locking version for status writes';

COMMIT;
