-- Collector schema, single migration (volumes are dropped on launch).
--
-- Lookup tables own the vocabularies that used to live in code
-- (SOURCE_PRIORITY, CATEGORIES, default city/currency). collected_events
-- keeps transitional text columns next to the new FK ids.

-- ---------------------------------------------------------------- sources
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'scraper'
        CHECK (kind IN ('scraper', 'api', 'debug')),
    priority INT NOT NULL DEFAULT 99,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO sources (code, display_name, kind, priority) VALUES
    ('ticketpro', 'Ticketpro.by', 'scraper', 10),
    ('bycard', 'ByCard', 'scraper', 20),
    ('relax', 'Afisha.relax.by', 'scraper', 30),
    ('afisha_me', 'Afisha.me', 'scraper', 40),
    ('24afisha', '24afisha', 'scraper', 50),
    ('telegram', 'Telegram previews', 'scraper', 60),
    ('twogis_places', '2GIS Places', 'api', 70),
    ('booking', 'Booking service', 'api', 5),
    ('probe', 'Manual probe', 'debug', 100);

-- ------------------------------------------------------------- categories
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 100,
    parent_id INT REFERENCES categories (id)
);

INSERT INTO categories (code, display_name, sort_order) VALUES
    ('concert', 'Concerts', 10),
    ('theatre', 'Theatre', 20),
    ('exhibition', 'Exhibitions', 30),
    ('film', 'Cinema', 40),
    ('sport', 'Sport', 50),
    ('kids', 'Kids', 60),
    ('other', 'Other', 1000);

-- ------------------------------------------------------------- currencies
CREATE TABLE currencies (
    code CHAR(3) PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT,
    minor_unit INT NOT NULL DEFAULT 2
);

INSERT INTO currencies (code, name, symbol, minor_unit) VALUES
    ('BYN', 'Belarusian ruble', 'Br', 2),
    ('USD', 'US dollar', '$', 2),
    ('EUR', 'Euro', '€', 2),
    ('RUB', 'Russian ruble', '₽', 2);

-- ----------------------------------------------------------------- cities
CREATE TABLE cities (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL,
    center_lat NUMERIC(9, 6) NOT NULL,
    center_lon NUMERIC(9, 6) NOT NULL
);

INSERT INTO cities (name, timezone, center_lat, center_lon) VALUES
    ('Минск', 'Europe/Minsk', 53.905600, 27.553900);

-- ------------------------------------------------------------------ venues
CREATE TABLE collected_venues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL DEFAULT 'twogis',
    source_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rubric TEXT,
    address TEXT,
    city TEXT NOT NULL DEFAULT 'Минск',
    city_id INT REFERENCES cities (id),
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    schedule JSONB,
    rating NUMERIC,
    review_count INT,
    source_url TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedded_at TIMESTAMPTZ,
    search_vector TSVECTOR,
    raw JSONB,
    UNIQUE (source, source_id),
    CONSTRAINT chk_venues_coords CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180))
);

-- ------------------------------------------------------------------ events
CREATE TABLE collected_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Provenance: external identity lives here during the transition,
    -- event_sources is the full many-to-many record.
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    primary_source_id INT REFERENCES sources (id),
    -- Set for rows mirrored from booking-service: their id is the bookable id.
    booking_event_id BIGINT UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL DEFAULT 'other',
    category_id INT REFERENCES categories (id),
    start_at TIMESTAMPTZ,
    end_at TIMESTAMPTZ,
    venue_id UUID REFERENCES collected_venues (id) ON DELETE SET NULL,
    venue_name TEXT,
    address TEXT,
    city TEXT NOT NULL DEFAULT 'Минск',
    city_id INT REFERENCES cities (id),
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    price_min NUMERIC(12, 2),
    price_max NUMERIC(12, 2),
    currency CHAR(3) NOT NULL DEFAULT 'BYN',
    currency_code CHAR(3) REFERENCES currencies (code),
    age_limit INT,
    ticket_url TEXT,
    image_url TEXT,
    organizer TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'cancelled', 'sold_out')),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedded_at TIMESTAMPTZ,
    search_vector TSVECTOR,
    raw JSONB,
    dedup_key TEXT,
    UNIQUE (source, source_id),
    CONSTRAINT chk_events_dates CHECK (end_at IS NULL OR start_at IS NULL
        OR end_at >= start_at),
    CONSTRAINT chk_events_prices CHECK (
        (price_min IS NULL OR price_min >= 0)
        AND (price_max IS NULL OR price_max >= 0)
        AND (price_min IS NULL OR price_max IS NULL OR price_max >= price_min)),
    CONSTRAINT chk_events_coords CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)),
    CONSTRAINT chk_events_age CHECK (age_limit IS NULL OR age_limit BETWEEN 0 AND 21)
);

CREATE INDEX idx_collected_events_start ON collected_events (start_at);
CREATE INDEX idx_collected_events_city ON collected_events (city);
CREATE INDEX idx_collected_events_lookup
    ON collected_events (city_id, category_id, start_at);
CREATE INDEX idx_collected_events_last_seen ON collected_events (last_seen_at);
CREATE UNIQUE INDEX idx_collected_events_dedup
    ON collected_events (dedup_key) WHERE dedup_key IS NOT NULL;

-- Cinema screenings live apart so one film doesn't multiply into dozens of events.
CREATE TABLE screenings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES collected_events (id) ON DELETE CASCADE,
    cinema TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    price NUMERIC(12, 2)
);
CREATE INDEX idx_screenings_event ON screenings (event_id);

-- Dedup: one logical event, many source URLs.
CREATE TABLE event_sources (
    event_id UUID NOT NULL REFERENCES collected_events (id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_id INT REFERENCES sources (id),
    source_url TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, source, source_url)
);
CREATE INDEX idx_event_sources_source ON event_sources (source_id, last_seen_at);

-- Run monitoring: alert if a source yields 0 rows twice in a row.
CREATE TABLE source_runs (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_id INT REFERENCES sources (id),
    status TEXT NOT NULL DEFAULT 'ok'
        CHECK (status IN ('ok', 'partial', 'error', 'skipped', 'quota_exhausted')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_s DOUBLE PRECISION,
    fetched INT NOT NULL DEFAULT 0, -- HTTP requests performed
    parsed INT NOT NULL DEFAULT 0, -- source items successfully parsed
    parse_errors INT NOT NULL DEFAULT 0,
    fetch_errors INT NOT NULL DEFAULT 0,
    duplicates INT NOT NULL DEFAULT 0,
    rows_inserted INT NOT NULL DEFAULT 0,
    rows_updated INT NOT NULL DEFAULT 0,
    quota_stopped BOOLEAN NOT NULL DEFAULT FALSE,
    error_code TEXT,
    error TEXT
);
CREATE INDEX idx_source_runs_source ON source_runs (source, started_at DESC);

-- Monthly API quota guard (2GIS demo key: 1000 req/month).
CREATE TABLE api_quota (
    provider TEXT NOT NULL,
    month TEXT NOT NULL CHECK (month ~ '^[0-9]{4}-[0-9]{2}$'),
    used INT NOT NULL DEFAULT 0 CHECK (used >= 0),
    PRIMARY KEY (provider, month)
);

-- 2GIS rubric discovery cache.
CREATE TABLE twogis_rubrics (
    name TEXT PRIMARY KEY,
    rubric_id TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Small key/value shelf (2GIS region id, ...).
CREATE TABLE collector_kv (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Lexical search (BM25-ish via tsvector) + embed tracking.
CREATE OR REPLACE FUNCTION collected_events_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('russian', coalesce(NEW.venue_name, '')), 'B') ||
        setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'C');
    NEW.updated_at := now();
    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_collected_events_search ON collected_events;
CREATE TRIGGER trg_collected_events_search
    BEFORE INSERT OR UPDATE OF title, venue_name, description ON collected_events
    FOR EACH ROW EXECUTE FUNCTION collected_events_search_trigger();

CREATE INDEX idx_collected_events_search
    ON collected_events USING GIN (search_vector);

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

CREATE INDEX idx_collected_venues_search
    ON collected_venues USING GIN (search_vector);
