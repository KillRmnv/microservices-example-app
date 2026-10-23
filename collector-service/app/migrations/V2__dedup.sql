-- Dedup key for cross-source merge (stage 1).
ALTER TABLE collected_events ADD COLUMN IF NOT EXISTS dedup_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_collected_events_dedup
    ON collected_events (dedup_key) WHERE dedup_key IS NOT NULL;
