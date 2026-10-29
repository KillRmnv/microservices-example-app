# TODO / deferred work

Tracked follow-ups that are intentionally **not** implemented in the current
refactor. Each item explains why it is deferred and what "done" looks like.

## Search

- [ ] **Elasticsearch / OpenSearch spike.** Hybrid search currently runs in
      Python: one dense call to Qdrant, one lexical call to Postgres
      (`plainto_tsquery` + `ts_rank_cd`), RRF fusion, then one filter pass.
      This is deliberate — no extra cluster while the catalog is small.
      Revisit when any of these is true:
      - lexical recall is limited by stemming/collation tuning;
      - more than ~1M events/venues, or facet queries need real aggregations;
      - we need multi-language analyzers with synonyms.
      "Done" means a benchmarked adapter behind the existing `SearchService`
      interface, not a rewrite of routers/services.

## Booking holds

- [ ] **Real inventory hold (stage 3b).** `assistant_db.booking_holds` stores
      a time-limited *intent* and validates zone/price against live tickets;
      it does not decrement inventory. Booking-service has no public hold
      endpoint and needs user-auth passthrough before it can own this.
      Code is marked with `TODO(stage-3b)` in
      `assistant-service/app/services/hold_service.py`.
      "Done" means: authenticating the user, creating/expiring the hold in
      booking-service inside one transaction, and returning a real hold id.

## Security / configuration

- [ ] **Gateway JWT secret.** `gateway/src/main/resources/application.yml`
      still falls back to a default signing secret; root `.env.example` only
      documents a placeholder. Move to a required env var (fail fast when
      missing) and rotate the development secret.
- [ ] **Frontend deployment env.** `NEXT_PUBLIC_DEFAULT_CITY` /
      `NEXT_PUBLIC_DEFAULT_LANGUAGE` now exist, but the Compose `frontend`
      build does not pass them through yet; exported static assets bake the
      defaults at build time.

## Local LLM / embeddings

- [ ] **LFM3 reasoning is too verbose for the structure stage.** With thinking
      enabled, LFM3-1.7B spends the whole budget in `reasoning_content`
      (1024/2048 tokens, `finish_reason=length`) and returns an empty `content`;
      only very short prompts close around ~1550 tokens (~2.5 min on CPU at
      ~11 t/s). llama.cpp master supports `lfm3`, so this is model behaviour,
      not a missing architecture. The assistant therefore runs
      **Ling-3.0-tiny-Q4_K_M** for the reasoning-enabled `structure` stage
      (`--jinja`, temp 1.0, top-p 0.95, top-k 20). Revisit LFM3 with a newer
      chat template/runtime, a larger budget (4k+), or a reasoning budget knob;
      "done" means a valid JSON contract within a usable token/time budget while
      thinking stays on, covered by a structure-stage test. Update: `structure`
      is now split — the fast no-think lane is the default and reasoning runs
      only for complex requests (`services/query_complexity.py`) or
      `force_reasoning=true`; the dedicated reasoning consumer is the new
      `POST /assistant/plan` stage (`services/plan_service.py`).
- [ ] **Model bootstrap.** `llama.cpp` servers are opt-in Compose profiles and
      expect model files under `${MODEL_DIR}` (bge-m3 for embeddings,
      Ling-3.0-tiny-Q4_K_M for chat; LFM3 remains an optional experiment). Add a documented download/verify step so a fresh clone can run
      `structure:local` without manual work, and note that the image is built
      from llama.cpp master (not the PyPI wheel) because of `lfm3` support.

## Operations / cleanup

- [ ] **Notification service observability.** The Go service exposes
      `/metrics`, but its handlers currently report only standard Go/process
      metrics. Add Kafka-consumed and email-sent counters if per-event
      visibility is needed.
