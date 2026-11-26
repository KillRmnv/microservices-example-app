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

- [ ] **Geo/distance filters.** The contract still accepts `location.districts`,
      `location.geo_radius` and `landmarks`; landmark coordinates are used only
      for weather, and districts have no data source yet. Event/venue payloads
      now carry `lat`/`lon`, so a Python `GeoRadiusFilter` (haversine, or a
      Qdrant geo condition) is the next step; districts need 2GIS `adm_div` or
      `address_name` extraction first.
- [x] **`themes` as a retrieval signal.** `SearchPlan.themes` now feeds the
      sparse and BM25 lexical queries; `dense_only` is no longer flipped by
      themes (the structure prompt also backfills `vector_query` from themes).
      A dedicated weighted term boost is still the next refinement.
- [x] **`semantic_payload.target_collection` / `language`.** `target_collection`
      is sanitized to `events|venues|both` (aliases `venues_atmosphere`/`places`)
      and overrides the intent scope on search turns; `language` is clamped to
      ru/en for presentation only — retrieval stays Russian-only (documented).

- [x] **Opening hours: overnight and multi-window.** Collector emits `hours`
      as a list of `[open, close]` pairs per day (e.g.
      `{"fri": [["18:00","02:00"]]}`), so night bars and lunch breaks survive;
      `VenueHoursFilter` rolls overnight closes into the next day and treats
      missing hours as unknown (never "closed").
- [x] **Availability freshness TTL.** Event payloads carry `availability_at`
      (last fetch); `PartyFilter`/`StatusFilter` trust `seats_left`/`sold_out`
      only within `ASSISTANT_AVAILABILITY_TTL_H` (48 h). `cancelled` is always
      dropped; stale inventory passes as unknown.
- [x] **Automatic payload reindex.** `PAYLOAD_VERSION` is stored in
      `collector_kv['embed:payload_version']`; a mismatch runs one hybrid
      reindex in the background under an advisory lock (and
      `POST /embed/reindex-hybrid` stamps the version). Health exposes
      `payload_version`; no manual step after deploy.
- [x] **Venue-linking coverage + address fallback.** Health exposes
      `venue_link` (linked/total per source); `link_event_venues` adds a
      second pass matching a normalised venue address inside the event address
      and resets `embedded_at` for newly linked rows.
- [x] **Group relevance for places (no capacity).** A party >= 6 enriches the
      venue query with group terms and softly boosts venues whose `amenities`
      intersect the configured group tags; capacity is deliberately not used
      and no venue is filtered out.
- [ ] **2GIS attribute groups are unavailable in the live API.** A live
      `GET /3.0/items` with `items.attribute_groups`/`attributes`/`adm_div`
      returned none, so `amenities`, `avg_check`, `price_level` and `district`
      stay null for live data. Group boosts and venue budgets therefore rely on
      text/unknown-pass. Next step: probe the by-id endpoint
      (`/3.0/items/byid`), a different provider, or derive amenities from
      reviews; until then keep the defensive parser.
- [ ] **Events without a linked venue have no rating.** `venue_rating` comes
      from the joined 2GIS venue; the new coverage metric shows the share of
      unlinked events. Extend linking by coordinates (events currently carry
      no coords of their own) or by a venue alias table.
- [ ] **Conditional `embedded_at` reset at scale.** Every re-crawl, merge,
      venue upsert and `link_event_venues` pass now resets `embedded_at`, so the
      next collect re-embeds even unchanged rows. That is the right default for
      a small catalog (accuracy over cost) but wasteful at 100k+ rows: switch to
      `embedded_at = CASE WHEN <payload fields> IS DISTINCT FROM EXCLUDED.* THEN
      NULL ELSE embedded_at END` once embeddings become a bottleneck.

## Media / cinema

- [x] **Cinema sources.** Ticketpro `/bilety-v-kino/` (category `film`, run
      intervals, ~20 live events) and afisha.me `map-film-minsk-1.xml`
      (46/46 pages validated; 79 cinema-run events / 396 sessions parsed,
      runs aggregated per cinema with `end_at = latest session`). Both are
      configured and exercised by the collector suite.
- [x] **ByCard film metadata.** `POST /collect/film_metadata?limit=&dry_run=`
      enriches existing film rows with description/image and
      `raw.film={genre,duration}` by normalized title; never inserts events,
      never overwrites non-empty fields.
- [x] **Telegram film channels.** `skyline_by` (50% keep) and
      `cinemascopeby` (63%) enabled with `film` default category and
      no-housing/jobs/ads rules; film keywords added to the relevance regex.
- [ ] **Exact showtimes (`screenings`).** The table is still empty. Proven
      session sources: mooon / Silver Screen (`__NEXT_DATA__`, 65 events /
      154 shows, no price) and `kinominska.by` (SSR schedule, Oktyabr, 151
      time tokens). Next step: adapters write `screenings`, match by film
      title + cinema, aggregate `MIN(start_at) WHERE start_at >= now()` into
      payload `next_session_at` + `cinema`, bump `PAYLOAD_VERSION`, reset
      `embedded_at` when the nearest session changes. The assistant/frontend
      already consume `next_session_at`/`cinema` null-safely.
- [ ] **Blocked/avoided cinema sources.** `kinoafisha.by` resolves but the TLS
      handshake is rejected from the sandbox; retry from another network.
      `afisha.yandex.by` disallows `/api` and core paths — official API only,
      no scraping. bycard film pages expose `Movie` JSON-LD but no showtimes.
- [ ] **Afisha.me film run is heavy.** 46 film pages at the 10 s source
      interval take ~8 minutes; keep it on the nightly schedule (or add a
      category filter to collect only `film`), do not run it in interactive
      smoke tests.

## Telegram sources

- [x] **Relevance filter + channel gate.** `parsing/relevance.py` drops
      housing/jobs/ads/resale/companion-search posts, detects digests/
      no-event/undated, and applies per-channel flags. `telegram_preview`
      dry-runs a channel; `telegram_rescore?dry_run=true` re-scores existing
      rows (current live dry-run: 2 deletions, no writes). Enabled channels
      must pass the 40% keep gate; low-ratio channels stay in observe.
- [x] **Channel set.** Enabled: `minsk_kuda`, `kuda_shodit_by`, `Minsk_kudaGo`,
      `paci_hub_minsk`, `eventsforstudents`, `minsk_detskiy`, `deti_minsk`,
      `skyline_by`, `cinemascopeby`. Observe (no writes): `adpachinak`,
      `mafia_meets`. Dead/private handles (`ominske`, `cityminsk`,
      `merkzy_kokobay`) were removed — they only produced fetch errors.
      The Mininform check remains the owner's responsibility.

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
- [ ] **Hold ownership.** Holds are keyed by a client-supplied `session_id`
      and are not scoped to the JWT subject; the gateway gate is the only check,
      so a reachable caller could reuse/confirm another session's hold. Scope
      holds by the authenticated subject when stage 3b lands.
      *Party counts are no longer blind:* the assistant now calls
      `GET /booking/events/{id}/availability?party=N` (exact seats per zone,
      `insufficient` when no zone fits) and the fallback ticket search walks
      every page instead of `page=1&size=500`.

## Security / configuration

- [x] **Rate limiting for `/assistant/query` and `/assistant/plan`.** Redis
      fixed-window limiter (`app/core/rate_limit.py`), identity = body
      `session_id` else client IP, `ASSISTANT_RATE_LIMIT_QUERY_PER_MIN=30` /
      `..._PLAN_PER_MIN=10`; 429 ProblemDetail + `Retry-After`, fail-open when
      Redis is down. The frontend shows a plain throttle notice. Availability
      answers are additionally cached for 30 s.
- [ ] **Public `GET /booking/events/{id}/availability` has no gateway limit.**
      The assistant caches answers, but a direct caller can hit the endpoint
      freely. It is a cheap aggregate query, yet a per-IP limit or an edge
      cache in the gateway is still worth adding if the endpoint is exposed
      beyond the demo.
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
