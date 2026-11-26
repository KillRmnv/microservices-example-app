-- Trustworthy catalog fields: ticket availability/capacity on events and
-- enrichment attributes on venues (average check, amenities, price level,
-- district).
--
-- Volumes are kept across deploys, so this file is additive and idempotent:
-- V1/V2 stay untouched, columns use IF NOT EXISTS and constraints are guarded
-- by pg_constraint lookups (ALTER TABLE ... ADD CONSTRAINT has no IF NOT
-- EXISTS). The whole file runs as one transaction.

ALTER TABLE collected_events
    ADD COLUMN IF NOT EXISTS capacity INT,
    ADD COLUMN IF NOT EXISTS seats_left INT,
    ADD COLUMN IF NOT EXISTS availability TEXT;

ALTER TABLE collected_venues
    ADD COLUMN IF NOT EXISTS avg_check NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS amenities JSONB,
    ADD COLUMN IF NOT EXISTS price_level TEXT,
    ADD COLUMN IF NOT EXISTS district TEXT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_events_capacity') THEN
        ALTER TABLE collected_events ADD CONSTRAINT chk_events_capacity
            CHECK (capacity IS NULL OR capacity >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_events_seats_left') THEN
        ALTER TABLE collected_events ADD CONSTRAINT chk_events_seats_left
            CHECK (seats_left IS NULL OR seats_left >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_events_seats_within_capacity') THEN
        ALTER TABLE collected_events ADD CONSTRAINT chk_events_seats_within_capacity
            CHECK (capacity IS NULL OR seats_left IS NULL
                   OR seats_left <= capacity);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_events_availability') THEN
        ALTER TABLE collected_events ADD CONSTRAINT chk_events_availability
            CHECK (availability IS NULL
                   OR availability IN ('in_stock', 'limited', 'sold_out', 'unknown'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_venues_avg_check') THEN
        ALTER TABLE collected_venues ADD CONSTRAINT chk_venues_avg_check
            CHECK (avg_check IS NULL OR avg_check >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_venues_price_level') THEN
        ALTER TABLE collected_venues ADD CONSTRAINT chk_venues_price_level
            CHECK (price_level IS NULL
                   OR price_level IN ('low', 'medium', 'high'));
    END IF;
END $$;

-- Booking mirrors now carry dedup_key so the same event seen by booking-service
-- and a scraper collapses into one row. Their bookable id remains the
-- authoritative identity: two bookable performances may legitimately share
-- title/time/venue, so the unique guard only covers scraped rows. The
-- non-unique lookup index keeps booking rows reachable by key as well.
DROP INDEX IF EXISTS idx_collected_events_dedup;
CREATE UNIQUE INDEX IF NOT EXISTS idx_collected_events_dedup
    ON collected_events (dedup_key)
    WHERE dedup_key IS NOT NULL AND source <> 'booking';
CREATE INDEX IF NOT EXISTS idx_collected_events_dedup_lookup
    ON collected_events (dedup_key) WHERE dedup_key IS NOT NULL;

-- Public catalog reads hide cancelled events; most rows are 'scheduled'.
CREATE INDEX IF NOT EXISTS idx_collected_events_status_start
    ON collected_events (status, start_at);
