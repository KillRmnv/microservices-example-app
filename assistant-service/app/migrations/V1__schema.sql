-- Assistant schema, single migration (volumes are dropped on launch).

-- Dialogue observability: one row per turn. Read only by /metrics.
CREATE TABLE dialogue_runs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn INT NOT NULL CHECK (turn > 0),
    action TEXT NOT NULL CHECK (action IN (
        'search', 'update_filters', 'ask_clarification', 'confirm_booking')),
    needs_clarification BOOLEAN NOT NULL DEFAULT FALSE,
    duration_ms INT NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_dialogue_runs_session ON dialogue_runs (session_id, created_at DESC);
CREATE INDEX idx_dialogue_runs_action ON dialogue_runs (action);

-- Booking intents ("holds"), NOT inventory locks: booking-service has no
-- hold API yet (stage 3b). PENDING (10-min TTL) -> CONFIRMED / EXPIRED.
CREATE TABLE booking_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    event_id INT NOT NULL CHECK (event_id > 0),
    zone TEXT NOT NULL CHECK (zone IN ('VIP', 'FAN_ZONE', 'BASIC')),
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    party_size INT NOT NULL DEFAULT 1 CHECK (party_size BETWEEN 1 AND 20),
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'CONFIRMED', 'EXPIRED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + make_interval(mins => 10),
    confirmed_at TIMESTAMPTZ,
    CONSTRAINT chk_booking_holds_expiry CHECK (expires_at > created_at),
    CONSTRAINT chk_booking_holds_confirmed CHECK (
        (status = 'CONFIRMED') = (confirmed_at IS NOT NULL))
);
CREATE INDEX idx_booking_holds_session
    ON booking_holds (session_id, created_at DESC);
CREATE INDEX idx_booking_holds_expiry
    ON booking_holds (status, expires_at) WHERE status = 'PENDING';

-- One live intent per session and event: retries are idempotent.
CREATE UNIQUE INDEX uq_booking_holds_pending
    ON booking_holds (session_id, event_id) WHERE status = 'PENDING';
