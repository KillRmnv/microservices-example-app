# TODO / deferred work

Tracked follow-ups that are intentionally **not** implemented in the current
refactor. Each item explains why it is deferred and what "done" looks like.

## Search

- [x] **In-process BM25 hybrid.** Qdrant `v1.20.2` (`qdrant-client==1.20.0`)
      now carries a Russian-aware BM25 full-text index on the `search_text`
      payload (Snowball stemmer/stopwords, `scoring=True`); the assistant
      fuses dense + sparse + BM25 with RRF under
      `ASSISTANT_HYBRID_MODE=bm25` (Compose default; code default `sparse`).
      A BM25 failure retries dense+sparse, then the collector lexical endpoint.
      `search_text` mirrors the embedding text and legacy points are patched by
      `POST /embed/reindex-hybrid?confirm=true`; the 1.20 volume move required a
      full re-embed (295 events / 70 venues).

- [ ] **Elasticsearch / OpenSearch spike (scale only).** Lexical recall is
      now served by Qdrant BM25, so this is no longer a recall fix — it is a
      scale and analytics decision. Revisit when any of these is true:
      - more than ~1M events/venues, or facet queries need real aggregations;
      - multi-language analyzers with synonyms, or cross-lingual search;
      - per-field boosting/reranking outgrows the payload-index approach.
      This is deliberate — no extra cluster while the catalog is small.
      "Done" means a benchmarked adapter behind the existing `SearchService`
      interface, not a rewrite of routers/services.

- [ ] **Qdrant integration test in CI.** BM25 `TextQuery`, RRF fusion, filters
      on prefetches and `must_not` are covered by `InMemoryStore` only. Add a
      Qdrant service to CI (or a compose smoke job) so a Qdrant-side regression
      in the `search_text` index or fusion path is caught before deploy.

## Booking holds

- [ ] **`booking` intent still falls through to event search.** The `booking`
      intent has its own spec in `assistant-service/app/models/intent.py`, but
      `DialogueService.search_turn` has no `booking` branch, so "забронируй
      концерт" behaves like an ordinary event search. Decide between a
      deterministic refusal (ask the user to pick a card and press "Выбрать")
      and creating a hold directly from the intent — the latter needs the
      user-auth passthrough from stage 3b.
- [ ] **Real inventory hold (stage 3b).** `assistant_db.booking_holds` stores
      a time-limited *intent* and validates zone/price against live tickets;
      it does not decrement inventory. Booking-service has no public hold
      endpoint and needs user-auth passthrough before it can own this.
      Code is marked with `TODO(stage-3b)` in
      `assistant-service/app/services/hold_service.py`.
      "Done" means: authenticating the user, creating/expiring the hold in
      booking-service inside one transaction, and returning a real hold id.
- [ ] **Hold ownership and party-count pagination.** Holds are keyed by a
      client-supplied `session_id` and are not scoped to the JWT subject; the
      gateway gate is the only check, so a reachable caller could reuse/confirm
      another session's hold. `check_availability` also reads page 1 with
      `size=500`, so zones/counts beyond it are invisible. Scope holds by the
      authenticated subject and paginate/aggregate tickets when stage 3b lands.

## Security / configuration

- [ ] **Rate limiting for `/assistant/query` and `/assistant/plan`.** Both call
      the hosted LLM per request and currently have no quota guard beyond the
      per-process breaker. Add a per-user/per-IP token bucket (gateway or
      service-level) with a 429 contract, and surface it in the UI.
- [ ] **Explicit `degraded` response field.** The frontend infers a degraded
      turn from a missing/invalid model answer and shows one notice per chat;
      the API should expose a boolean/enum (`reasoning_used` exists, but not
      failure) so clients do not have to guess.
- [ ] **Next.js security upgrade advisory.** `frontend/package.json` pins
      `next@16.4.0`. Track the Next.js security advisories and upgrade to a
      patched release; re-run the static export and the gateway Selenium
      baseline afterwards.
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
      The structure lane is capped by `ASSISTANT_LLM_STRUCTURE_TIMEOUT_S` and
      guarded by a per-process `BreakerProvider`
      (`ASSISTANT_LLM_BREAKER_FAILURES` / `ASSISTANT_LLM_BREAKER_COOLDOWN_S`);
      an outage raises `LLMUnavailable` (HTTP 502). Prompts wrap user text in
      `<user_query>` delimiters with injection guards. When the API is
      unavailable, the frontend classifies intent locally and stays on the
      deterministic RU `/dialogue/v2` path (one degraded notice per chat); the
      plan stage falls back to cards.
- [ ] **Embeddings stay local.** `llama-embed` (bge-m3, 1024 dims) remains
      under the `llm` profile and still expects `${MODEL_DIR}` with the GGUF
      file. Add a documented download/verify step for a fresh clone.

## Operations / cleanup

- [ ] **Notification service observability.** The Go service exposes
      `/metrics`, but its handlers currently report only standard Go/process
      metrics. Add Kafka-consumed and email-sent counters if per-event
      visibility is needed.
