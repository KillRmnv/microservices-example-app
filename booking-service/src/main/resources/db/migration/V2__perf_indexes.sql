-- Query indexes for catalog/ticket lookups.
-- Small seed data does not need them, but the API filters are already here.

CREATE INDEX IF NOT EXISTS idx_events_category_starts
    ON events (category, starts_at);

CREATE INDEX IF NOT EXISTS idx_events_starts
    ON events (starts_at);

CREATE INDEX IF NOT EXISTS idx_tickets_event_active
    ON tickets (event_id, active);

CREATE INDEX IF NOT EXISTS idx_tickets_user_active
    ON tickets (user_id, active);
