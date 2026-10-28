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
        serial id PK
        varchar name UK
    }

    VENUES {
        serial id PK
        int town_id FK
        varchar place
        int capacity "CHECK > 0"
    }

    EVENTS {
        serial id PK
        varchar title
        timestamp starts_at "CHECK future"
        timestamp ends_at "CHECK > starts_at"
        int venue_id FK
        varchar admission_mode "SEATABLE | GENERAL"
    }

    SEATS {
        serial id PK
        varchar sector
        varchar row_label
        varchar seat_number
        int venue_id FK
    }

    TICKETS {
        serial id PK
        int event_id FK
        varchar zone "VIP | FAN_ZONE | BASIC"
        decimal price "CHECK > 0"
        boolean active
        int user_id "auth user, nullable"
    }

    SEATABLE_TICKETS {
        int ticket_id PK, FK
        int seat_id FK
    }

    VENUE_FULLNESS {
        int venue_id PK, FK
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

---

## 3. `collector_db` — scraped playbill, dedup and search

```mermaid
erDiagram
    COLLECTED_EVENTS ||--o{ SCREENINGS : "cinema showings"
    COLLECTED_EVENTS ||--o{ EVENT_SOURCES : "also published as"

    COLLECTED_EVENTS {
        uuid id PK
        text source
        text source_id "UNIQUE(source, source_id)"
        text source_url
        text title
        text category "concert | theatre | ..."
        timestamptz start_at
        timestamptz end_at
        text venue_name
        text city "default from settings"
        numeric lat
        numeric lon
        numeric price_min
        numeric price_max
        char currency "default from settings"
        text dedup_key UK "nullable"
        timestamptz embedded_at "Qdrant backfill marker"
        tsvector search_vector "russian, weighted A/B/C"
        jsonb raw
    }

    SCREENINGS {
        uuid id PK
        uuid event_id FK
        text cinema
        timestamptz start_at
        numeric price
    }

    EVENT_SOURCES {
        uuid event_id PK, FK
        text source PK
        text source_url PK
    }

    COLLECTED_VENUES {
        uuid id PK
        text source "twogis"
        text source_id "UNIQUE(source, source_id)"
        text name
        text rubric
        text address
        text city
        numeric lat
        numeric lon
        jsonb schedule
        numeric rating
        int review_count
        timestamptz embedded_at
        tsvector search_vector
        jsonb raw
    }

    SOURCE_RUNS {
        bigserial id PK
        text source
        text status "ok | error"
        timestamptz started_at
        int fetched
        int parsed
        int parse_errors
        int duplicates
        int new_events
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
```

Notes

- `dedup_key` is a partial unique index: the same logical event coming from
  two sources is merged into one row, and `event_sources` keeps both URLs.
- `search_vector` is maintained by a trigger (title A, venue B, description C)
  and indexed with GIN — this is the lexical half of hybrid search.
- `source_runs` is append-only and drives `/collect/health`, alerting and the
  Prometheus counters. A failed fetch still writes a row.
- `api_quota` is consumed **per HTTP attempt** for billable providers and
  stops at `cap - reserve`, so the trial key never gets disabled mid-month.
- `collector_kv` (not drawn) caches the discovered 2GIS region id.

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
        int event_id "booking-service event"
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
plantuml -tsvg docs/uml/*.puml
```
