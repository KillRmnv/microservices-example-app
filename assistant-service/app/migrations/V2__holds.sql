-- Stage 3: booking holds (PENDING -> CONFIRMED/EXPIRED).
CREATE TABLE IF NOT EXISTS booking_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    event_id INT NOT NULL,
    zone TEXT NOT NULL,
    price NUMERIC NOT NULL,
    party_size INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + make_interval(mins => 10),
    confirmed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_booking_holds_session
    ON booking_holds (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_booking_holds_expiry
    ON booking_holds (status, expires_at) WHERE status = 'PENDING';
