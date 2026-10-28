-- Holds are booking intents, not inventory locks (stage 3b will replace them
-- with a real hold in booking-service). Guard the invariants we own today.

-- One live intent per session and event: retries are idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_holds_pending
    ON booking_holds (session_id, event_id) WHERE status = 'PENDING';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_booking_holds_price') THEN
        ALTER TABLE booking_holds
            ADD CONSTRAINT chk_booking_holds_price CHECK (price >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_booking_holds_party_size') THEN
        ALTER TABLE booking_holds
            ADD CONSTRAINT chk_booking_holds_party_size
            CHECK (party_size BETWEEN 1 AND 20);
    END IF;
END $$;
