-- Read-path and backfill indexes for the public catalog.
-- Added after read queries switched from LATERAL name matching to venue_id.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_collected_events_venue_start
    ON collected_events (venue_id, start_at);

CREATE INDEX IF NOT EXISTS idx_collected_events_city_category_start_end
    ON collected_events (city, category, start_at, end_at);

CREATE INDEX IF NOT EXISTS idx_collected_venues_city_rubric
    ON collected_venues (city, rubric);

CREATE INDEX IF NOT EXISTS idx_collected_events_embed_pending
    ON collected_events (source, fetched_at)
    WHERE embedded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_collected_venues_embed_pending
    ON collected_venues (fetched_at)
    WHERE embedded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_collected_events_venue_name_trgm
    ON collected_events USING GIN (venue_name gin_trgm_ops);
