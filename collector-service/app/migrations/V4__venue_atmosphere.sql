-- Venue atmosphere tags (deterministic RU lexicon over review/event text and
-- rubric heuristics). Additive and idempotent: V1-V3 stay untouched, the
-- column stays nullable until the enrichment job writes a JSONB array.
--
-- The whole file runs as one transaction by the migration runner.

ALTER TABLE collected_venues
    ADD COLUMN IF NOT EXISTS atmosphere JSONB;

COMMENT ON COLUMN collected_venues.atmosphere IS
    'Atmosphere tags (JSONB array of quiet/cozy/loud/...); NULL = not enriched yet';
