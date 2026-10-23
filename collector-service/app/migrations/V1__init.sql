-- Collector schema: unified playbill events (see SCRAPPING.md §4).
CREATE TABLE IF NOT EXISTS collected_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL DEFAULT 'other',
    start_at TIMESTAMPTZ,
    end_at TIMESTAMPTZ,
    venue_name TEXT,
    address TEXT,
    city TEXT NOT NULL DEFAULT 'Минск',
    lat NUMERIC,
    lon NUMERIC,
    price_min NUMERIC,
    price_max NUMERIC,
    currency CHAR(3) NOT NULL DEFAULT 'BYN',
    age_limit INT,
    ticket_url TEXT,
    image_url TEXT,
    organizer TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw JSONB,
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_collected_events_start ON collected_events (start_at);
CREATE INDEX IF NOT EXISTS idx_collected_events_city ON collected_events (city);

-- Cinema screenings live apart so one film doesn't multiply into dozens of events.
CREATE TABLE IF NOT EXISTS screenings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES collected_events (id) ON DELETE CASCADE,
    cinema TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    price NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_screenings_event ON screenings (event_id);

-- Dedup: one logical event, many source URLs.
CREATE TABLE IF NOT EXISTS event_sources (
    event_id UUID NOT NULL REFERENCES collected_events (id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    PRIMARY KEY (event_id, source, source_url)
);

-- Run monitoring: alert if a source yields 0 events twice in a row.
CREATE TABLE IF NOT EXISTS source_runs (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_s DOUBLE PRECISION,
    fetched INT NOT NULL DEFAULT 0,
    parsed INT NOT NULL DEFAULT 0,
    parse_errors INT NOT NULL DEFAULT 0,
    duplicates INT NOT NULL DEFAULT 0,
    new_events INT NOT NULL DEFAULT 0,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_runs_source ON source_runs (source, started_at DESC);
