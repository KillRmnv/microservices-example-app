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

## LLM / embeddings

- [x] **Chat stages moved to OpenRouter.** `structure` and `plan` use the
      hosted OpenRouter API (`clients/llm/openrouter.py`); the Ling/llama-chat
      container is no longer part of Compose. The key and model come from
      `ASSISTANT_OPENROUTER_KEY` / `ASSISTANT_OPENROUTER_MODEL` (secret env).
      When the API is unavailable, `/assistant/query` returns the local
      contract and the frontend falls back to its deterministic RU parser;
      the plan stage falls back to cards.
- [ ] **Embeddings stay local.** `llama-embed` (bge-m3, 1024 dims) remains
      under the `llm` profile and still expects `${MODEL_DIR}` with the GGUF
      file. Add a documented download/verify step for a fresh clone.

## Operations / cleanup

- [ ] **Notification service observability.** The Go service exposes
      `/metrics`, but its handlers currently report only standard Go/process
      metrics. Add Kafka-consumed and email-sent counters if per-event
      visibility is needed.
