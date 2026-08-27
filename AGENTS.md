# Agent Guide

## Project structure

Four independent Spring Boot services — **no root Gradle build**. Each service has its own `build.gradle`, `settings.gradle`, and `./gradlew`.

| Service | Port | DB | Extra infra |
|---------|------|----|-------------|
| gateway | 8080 | — | WebFlux (reactive), Resilience4j circuit breakers, serves frontend from `src/main/resources/static/` |
| user-service | 8081 | `user_service` | Redis (Bucket4j rate limiting), Kafka producer |
| booking-service | 8082 | `booking_service` | Redis (Redisson caching), Kafka producer |
| notification-service | 8083 | — | Kafka consumer, email (SMTP) |

Shared versions live in `gradle/version.gradle`. Each service's `build.gradle` applies it via `apply from: '../gradle/version.gradle'`.

**Gateway is reactive (WebFlux)** — all other services are Spring MVC (servlet). Don't use blocking calls in gateway code.

## Build & run

```bash
# Full stack (Docker)
docker compose up -d --build

# Infrastructure only (for local dev)
docker compose up -d postgres redis zookeeper kafka

# Single service locally
cd <service> && ./gradlew bootRun

# Build JAR (skip tests)
cd <service> && ./gradlew bootJar -x test --no-daemon
```

**Docker build context**: Dockerfiles run from the repo root (`context: .`), not from the service dir. They copy `gradle/version.gradle` from the root. Don't move or rename it without updating all four Dockerfiles.

**Dockerfiles are multi-stage**: `eclipse-temurin:21-jdk` for build, `eclipse-temurin:21-jre` for runtime. All run as non-root `appuser` with `-XX:MaxRAMPercentage=75.0`.

## Testing

**Docker required** — all services use Testcontainers (PostgreSQL, Kafka, Redis).

```bash
# All tests in a service
cd <service> && ./gradlew test

# Single test class
cd <service> && ./gradlew test --tests "*.EventServiceTest"
```

Testcontainers spin up via `TestcontainersConfiguration` in each service's test sources. Kafka images differ across services: user-service and notification-service use `apache/kafka-native:latest` (new `org.testcontainers.kafka.KafkaContainer` API), while booking-service uses `confluentinc/cp-kafka:7.5.0` (legacy `org.testcontainers.containers.KafkaContainer` API). Docker Compose uses `confluentinc/cp-kafka:7.5.0`.

**Known quirk**: `gateway/src/test/.../TestcontainersConfiguration.java` starts a Redis container even though the gateway doesn't use Redis — don't add Redis beans there. Same for `notification-service/src/test/.../TestcontainersConfiguration.java`.

## Java version

**Java 21** — set in `gradle/version.gradle` (`javaVersion = 21`). All Dockerfiles use `eclipse-temurin:21-jdk` / `21-jre`. Verify JDK 21 is available before building locally.

## Environment setup

Each service and the root need `.env` files. Copy from `*.env.example`:

```bash
cp .env.example .env
cp user-service/.env.example user-service/.env
cp booking-service/.env.example booking-service/.env
cp notification-service/.env.example notification-service/.env
cp gateway/.env.example gateway/.env
```

Critical vars: `JWT_SECRET` (root `.env`), DB credentials (per-service `.env`), `MAIL_*` (notification-service).

Docker Compose services consume both root `.env` and their own `.env` via `env_file`.

## Gateway routing

Gateway (`application.yml`) routes:
- `/users/**` → `http://user-service:8081`
- `/booking/**` → `http://booking-service:8082`

Public endpoints (skip JWT): `/users/auth/login`, `/users/auth/register`, `/users/auth/forget-password`, `/users/auth/reset-password`, `/users/auth/validate-reset-token`, `/actuator/health`.

Gateway injects `X-User-Name`, `X-User-Role`, `X-User-Email` headers into downstream requests after JWT validation. Downstream services trust these headers directly — no JWT validation in user-service or booking-service.

## Database

- `init-postgres.sql` creates both databases (`user_service`, `booking_service`).
- Flyway auto-runs on startup. Migrations: `src/main/resources/db/migration/V*.sql` per service.
- `spring.jpa.hibernate.ddl-auto=none` — schema managed entirely by Flyway.

## Kafka topics

Produced by user-service and booking-service, consumed by notification-service for email notifications. Topic names are configurable via properties files. See `application.properties` / `application.yml` for topic constants.

## Conventions

- Package structure: `com.microservices_example_app.<service>`
- Lombok everywhere (`@Builder`, `@Slf4j`, etc.)
- JPA Specifications for dynamic queries (`*Specification.java`)
- Role hierarchy: CUSTOMER → EVENT_MANAGER → ADMIN
- JWT contains `role` and `email` claims — downstream services trust `X-User-*` headers, not JWT directly
- Notification-service uses Jackson 3 (`tools.jackson.core`) — different from other services
