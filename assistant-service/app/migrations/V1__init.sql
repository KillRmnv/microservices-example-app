-- Assistant schema: dialogue observability (stage 0).
-- Booking holds arrive at stage 3.
CREATE TABLE IF NOT EXISTS dialogue_runs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn INT NOT NULL,
    action TEXT NOT NULL,
    needs_clarification BOOLEAN NOT NULL DEFAULT FALSE,
    duration_ms INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dialogue_runs_session ON dialogue_runs (session_id, created_at DESC);
