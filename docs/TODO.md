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

- [ ] **LFM3 reasoning mode.** `llama-chat` currently runs LFM3 with
      `ASSISTANT_LLM_DISABLE_THINKING=true`
      (`chat_template_kwargs.enable_thinking=false`). With thinking enabled the
      model spends the whole token budget in `reasoning_content` and returns an
      empty `content`, so the structure stage falls back to the deterministic
      parser. Figure out whether this is:
      - how the llama.cpp build handles LFM3 `reasoning_content` / template
        kwargs (`--reasoning-format`, `--no-reasoning-preserve`, `--jinja`);
      - the GGUF chat template metadata itself (check what the model expects for
        enabling/disabling thinking);
      - or just `max_tokens`/`temperature` in
        `assistant-service/app/clients/llm/llama_cpp.py`.
      "Done" means either reasoning works end-to-end (reasoning can be kept or
      discarded explicitly, while the final JSON answer lands in `content`) with
      a test for the structure stage, or a short written decision why thinking
      stays disabled for this model. Do not silently rely on the flag: the
      runtime is built from llama.cpp master, and PyPI `llama-cpp-python` still
      lacks `lfm3`, so a version/template regression is plausible.
- [ ] **Model bootstrap.** `llama.cpp` servers are opt-in Compose profiles and
      expect model files under `${MODEL_DIR}` (bge-m3 for embeddings, LFM3 for
      chat). Add a documented download/verify step so a fresh clone can run
      `structure:local` without manual work, and note that the image is built
      from llama.cpp master (not the PyPI wheel) because of `lfm3` support.

## Operations / cleanup

- [ ] **Notification service observability.** The Go service exposes
      `/metrics`, but its handlers currently report only standard Go/process
      metrics. Add Kafka-consumed and email-sent counters if per-event
      visibility is needed.
