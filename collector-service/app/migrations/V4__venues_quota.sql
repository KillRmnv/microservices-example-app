-- Stage: 2GIS venues catalog + API quota guard (demo key: 1000 req/month).
CREATE TABLE IF NOT EXISTS collected_venues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL DEFAULT 'twogis',
    source_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rubric TEXT,
    address TEXT,
    city TEXT NOT NULL DEFAULT 'Минск',
    lat NUMERIC,
    lon NUMERIC,
    schedule JSONB,
    rating NUMERIC,
    review_count INT,
    source_url TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedded_at TIMESTAMPTZ,
    search_vector TSVECTOR,
    raw JSONB,
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_collected_venues_city ON collected_venues (city);

CREATE OR REPLACE FUNCTION collected_venues_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('russian', coalesce(NEW.name, '')), 'A') ||
        setweight(to_tsvector('russian', coalesce(NEW.rubric, '')), 'B') ||
        setweight(to_tsvector('russian', coalesce(NEW.address, '')), 'C');
    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_collected_venues_search ON collected_venues;
CREATE TRIGGER trg_collected_venues_search
    BEFORE INSERT OR UPDATE OF name, rubric, address ON collected_venues
    FOR EACH ROW EXECUTE FUNCTION collected_venues_search_trigger();

CREATE INDEX IF NOT EXISTS idx_collected_venues_search
    ON collected_venues USING GIN (search_vector);

-- Monthly API quota per provider (hard stop before the cap).
CREATE TABLE IF NOT EXISTS api_quota (
    provider TEXT NOT NULL,
    month TEXT NOT NULL,
    used INT NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, month)
);

-- Cached 2GIS region/rubric ids (discovery costs requests too).
CREATE TABLE IF NOT EXISTS twogis_rubrics (
    name TEXT PRIMARY KEY,
    rubric_id TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS collector_kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
