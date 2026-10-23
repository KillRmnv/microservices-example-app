-- Stage 2: lexical search (BM25-ish via tsvector) + embed tracking.
ALTER TABLE collected_events ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ;
ALTER TABLE collected_events ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;

CREATE OR REPLACE FUNCTION collected_events_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('russian', coalesce(NEW.venue_name, '')), 'B') ||
        setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'C');
    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_collected_events_search ON collected_events;
CREATE TRIGGER trg_collected_events_search
    BEFORE INSERT OR UPDATE OF title, venue_name, description ON collected_events
    FOR EACH ROW EXECUTE FUNCTION collected_events_search_trigger();

CREATE INDEX IF NOT EXISTS idx_collected_events_search
    ON collected_events USING GIN (search_vector);

-- Backfill existing rows (trigger only fires on future writes).
UPDATE collected_events SET search_vector =
    setweight(to_tsvector('russian', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('russian', coalesce(venue_name, '')), 'B') ||
    setweight(to_tsvector('russian', coalesce(description, '')), 'C')
WHERE search_vector IS NULL;
