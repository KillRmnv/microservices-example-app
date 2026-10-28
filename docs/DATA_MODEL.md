# Data model

Four PostgreSQL databases are provisioned by `init-postgres.sql`:
`user_service`, `booking_service`, `collector_db`, `assistant_db`.
Services never read each other's database — they integrate through HTTP and
Kafka. The diagrams below use UML/ER notation: `||--o{` is one-to-many,
`||--||` is one-to-one, `}o--||` is many-to-one.

The same diagrams are checked in as PlantUML sources under
[`docs/uml/`](uml/), so they can be rendered or reviewed without a browser.

---

## 1. `user_service` — identity and roles

```mermaid
erDiagram
    ROLES ||--o{ USERS : "assigned to"
    ROLES ||--o{ ROLE_PERMISSIONS : grants
    PERMISSIONS ||--o{ ROLE_PERMISSIONS : "granted by"

    ROLES {
        bigint id PK
        varchar name UK "CUSTOMER | EVENT_MANAGER | ADMIN"
    }

    PERMISSIONS {
        bigint id PK
        varchar name UK "CREATE_BOOKING ... ADMIN_BYPASS"
    }

    ROLE_PERMISSIONS {
        bigint role_id PK, FK
        bigint permission_id PK, FK
    }

    USERS {
        bigint id PK
        varchar username UK
        varchar email UK
        varchar password_hash
        bigint role_id FK
        boolean is_system "protected by triggers"
    }
```

Notes

- `role_permissions` is a pure join table; its primary key is the pair.
- Triggers forbid changing the role or deleting a user with `is_system = true`.
- `users.role_id` uses `ON DELETE RESTRICT`, so a role cannot disappear while
  it is still assigned.

---

## 2. `booking_service` — catalog, seats and tickets

```mermaid
erDiagram
    TOWNS ||--o{ VENUES : contains
    VENUES ||--o{ EVENTS : hosts
    VENUES ||--o{ SEATS : has
    VENUES ||--|| VENUE_FULLNESS : "live counter"
    EVENTS ||--o{ TICKETS : sells
    TICKETS ||--o| SEATABLE_TICKETS : "seat assignment"
    SEATS ||--o{ SEATABLE_TICKETS : "assigned to"

    TOWNS {
        bigserial id PK
        varchar name UK
    }

    VENUES {
        bigserial id PK
        bigint town_id FK
        varchar place
        int capacity "CHECK > 0"
    }

    EVENTS {
        bigserial id PK
        varchar title
        timestamp starts_at "CHECK future"
        timestamp ends_at "CHECK > starts_at"
        bigint venue_id FK
        varchar category "concert | theatre | sport | ..."
        varchar admission_mode "SEATABLE | GENERAL"
    }

    SEATS {
        bigserial id PK
        varchar sector
        varchar row_label
        varchar seat_number
        bigint venue_id FK
    }

    TICKETS {
        bigserial id PK
        bigint event_id FK
        varchar zone "VIP | FAN_ZONE | BASIC"
        decimal price "CHECK > 0"
        boolean active
        bigint user_id "auth user, nullable"
    }

    SEATABLE_TICKETS {
        bigint ticket_id PK, FK
        bigint seat_id FK
    }

    VENUE_FULLNESS {
        bigint venue_id PK, FK
        int fullness "CHECK > 0"
    }
```

Notes

- `seatable_tickets` is a 1:1 extension of `tickets` for seatable events;
  general-admission tickets have no row there.
- `uq_seats_venue_sector_row_number` prevents duplicate physical seats.
- Trigger `check_venue_fullness` increments `venue_fullness` before a ticket
  update and raises once capacity is exceeded.
- `active = true` is what the assistant asks for through
  `GET /booking/tickets/search?active=true`.
- Every id is a `BIGINT` (`Long` in Java): 32-bit identity columns were
  replaced before the first release, so URLs/JSON stay plain numbers.
- `events.category` uses the same vocabulary as the collector
  (`concert`, `theatre`, `exhibition`, `film`, `sport`, `kids`, `other`),
  so mirrored events pass the assistant's category filters.

---

## 3. `collector_db` — mirrored playbill, lookups and search

```mermaid
erDiagram
    SOURCES ||--o{ COLLECTED_EVENTS : "primary source"
    CATEGORIES ||--o{ COLLECTED_EVENTS : "category"
    CITIES ||--o{ COLLECTED_EVENTS : "city"
    CURRENCIES ||--o{ COLLECTED_EVENTS : "currency"
    COLLECTED_VENUES ||--o{ COLLECTED_EVENTS : "venue"
    SOURCES ||--o{ EVENT_SOURCES : "provenance"
    COLLECTED_EVENTS ||--o{ EVENT_SOURCES : "also published as"
    COLLECTED_EVENTS ||--o{ SCREENINGS : "cinema showings"
    CITIES ||--o{ COLLECTED_VENUES : "city"
    SOURCES ||--o{ SOURCE_RUNS : "run log"

    SOURCES {
        serial id PK
        text code UK "ticketpro | booking | ..."
        text display_name
        text kind "scraper | api | debug"
        int priority "merge/order rank"
        boolean enabled
    }

    CATEGORIES {
        serial id PK
        text code UK "concert | theatre | ..."
        text display_name
        int sort_order
        int parent_id FK "nullable"
    }

    CURRENCIES {
        char code PK "BYN | USD | EUR | RUB"
        text name
        text symbol
        int minor_unit
    }

    CITIES {
        serial id PK
        text name UK
        text timezone
        numeric center_lat
        numeric center_lon
    }

    COLLECTED_EVENTS {
        uuid id PK
        text source "denormalised for dedup"
        text source_id "UNIQUE(source, source_id)"
        text source_url
        int primary_source_id FK
        bigint booking_event_id UK "mirrored booking id, nullable"
        text title
        text description
        text category
        int category_id FK
        timestamptz start_at
        timestamptz end_at
        uuid venue_id FK
        text venue_name
        text address
        text city
        int city_id FK
        numeric latitude
        numeric longitude
        numeric price_min
        numeric price_max
        char currency
        char currency_code FK
        int age_limit
        text ticket_url
        text image_url
        text organizer
        text status "scheduled | cancelled | sold_out"
        timestamptz first_seen_at
        timestamptz last_seen_at
        timestamptz updated_at
        timestamptz fetched_at
        timestamptz embedded_at "Qdrant backfill marker"
        tsvector search_vector "russian, weighted A/B/C"
        jsonb raw
        text dedup_key UK "nullable"
    }

    COLLECTED_VENUES {
        uuid id PK
        text source
        text source_id "UNIQUE(source, source_id)"
        text name
        text rubric
        text address
        text city
        int city_id FK
        numeric latitude
        numeric longitude
        jsonb schedule
        numeric rating
        int review_count
        text source_url
        timestamptz fetched_at
        timestamptz embedded_at
        tsvector search_vector
        jsonb raw
    }

    EVENT_SOURCES {
        uuid event_id PK, FK
        text source PK
        text source_url PK
        int source_id FK
        boolean is_primary
        timestamptz first_seen_at
        timestamptz last_seen_at
    }

    SCREENINGS {
        uuid id PK
        uuid event_id FK
        text cinema
        timestamptz start_at
        numeric price
    }

    SOURCE_RUNS {
        bigserial id PK
        text source
        int source_id FK
        text status "ok | partial | error | skipped | quota_exhausted"
        timestamptz started_at
        timestamptz finished_at
        float duration_s
        int fetched "HTTP requests"
        int parsed "source items parsed"
        int parse_errors
        int fetch_errors
        int duplicates
        int rows_inserted
        int rows_updated
        boolean quota_stopped
        text error_code
        text error
    }

    API_QUOTA {
        text provider PK "twogis"
        text month PK "YYYY-MM"
        int used "hard stop at cap - reserve"
    }

    TWOGIS_RUBRICS {
        text name PK
        text rubric_id
        timestamptz fetched_at
    }

    COLLECTOR_KV {
        text key PK "2GIS region id, ..."
        text value
        timestamptz updated_at
    }
```

Notes

- Lookup tables own the vocabularies that used to be constants in code
  (`sources.priority` replaced `SOURCE_PRIORITY`, `categories` replaced the
  `CATEGORIES` set). Text columns stay next to the FK ids during the
  transition, so old queries keep working.
- `dedup_key` is a partial unique index: the same logical scraped event from
  two sources is merged into one row, and `event_sources` keeps every URL.
  Rows mirrored from booking-service have `dedup_key = NULL` and never join
  that merge — deleting a booking event must not remove its scraped twin.
- `booking_event_id` marks a row mirrored from `booking.catalog` (Kafka).
  Its value is the bookable id the assistant uses for availability/holds;
  Qdrant payloads carry it next to the UUID point id.
- `search_vector` is maintained by a trigger (title A, venue B, description C)
  and indexed with GIN — this is the lexical half of hybrid search. The same
  trigger bumps `updated_at`.
- `source_runs` is append-only and drives `/collect/health`, alerting and the
  Prometheus counters. `fetched` counts HTTP requests, `parsed` source items,
  `rows_inserted`/`rows_updated` rows; a failed fetch still writes a row with
  `status = error`.
- `api_quota` is consumed **per HTTP attempt** for billable providers and
  stops at `cap - reserve`, so the trial key never gets disabled mid-month.
- `collector_kv` caches small discovered values (the 2GIS region id).

---

## 4. `assistant_db` — dialogue observability and booking intents

```mermaid
erDiagram
    DIALOGUE_RUNS {
        bigserial id PK
        text session_id
        int turn
        text action "search | ask_clarification | ..."
        boolean needs_clarification
        int duration_ms
        timestamptz created_at
    }

    BOOKING_HOLDS {
        uuid id PK
        text session_id
        bigint event_id "booking-service event"
        text zone
        numeric price
        int party_size "1..20"
        text status "PENDING | CONFIRMED | EXPIRED"
        timestamptz created_at
        timestamptz expires_at "default now() + 10 min"
        timestamptz confirmed_at
    }

    DIALOGUE_RUNS ||..o{ BOOKING_HOLDS : "same session (soft link)"
```

Notes

- `dialogue_runs` is write-only telemetry; it is truncated by tests and read
  by `GET /metrics`.
- `booking_holds` stores a **booking intent**, not real inventory:
  - one pending intent per `(session_id, event_id)` via the partial unique
    index `uq_booking_holds_pending`;
  - `CHECK` constraints keep `price >= 0` and `1 <= party_size <= 20`;
  - the expiry sweep flips stale `PENDING` rows to `EXPIRED`;
  - confirming a missing, taken or expired hold returns HTTP 410.
- Real ticket locking lives in booking-service and is deferred
  (`TODO(stage-3b)`, see [`docs/TODO.md`](TODO.md)).
- `event_id` is `BIGINT` to match the booking-service `Long` ids.

---

## 5. Cross-service interactions

```mermaid
flowchart LR
    FE[Next.js frontend] -->|/users/*, /booking/*, /assistant/*| GW[Gateway]
    GW --> US[user-service]
    GW --> BS[booking-service]
    GW --> AS[assistant-service]
    BS -.->|Kafka: notification.booking| NS[notification-service-go]
    US -.->|Kafka: user.mass-mail| BS
    AS -->|lexical search| CS[collector-service]
    AS -->|embeddings| LL[llama.cpp server]
    AS -->|vectors| QD[(Qdrant)]
    AS -->|availability / event read| BS
    AS -->|forecast cache| RD[(Redis)]
    CS -->|events / venues vectors| QD
    CS -->|billable places API| TG[2GIS]
    BS -.->|Kafka: booking.catalog (compacted)| CS
```

The data model is intentionally split per service: there are no cross-database
foreign keys, only ids exchanged in DTOs. `event_id` in `booking_holds` is a
booking-service id (integer); collected events use UUIDs and therefore never
get a live availability check.

---

## 6. UML class view (PlantUML sources)

Full class diagrams with attributes, methods and multiplicities:

| File | Scope |
| --- | --- |
| [`uml/user-service.puml`](uml/user-service.puml) | identity entities and repositories |
| [`uml/booking-service.puml`](uml/booking-service.puml) | catalog, tickets, services |
| [`uml/collector-service.puml`](uml/collector-service.puml) | adapters, services, repositories |
| [`uml/assistant-service.puml`](uml/assistant-service.puml) | dialogue, search engine, filters, holds |

Render them with any PlantUML jar or IDE plugin, for example:

```bash
# PNG is the committed format (git diff stays readable).
plantuml docs/uml/*.puml
```
