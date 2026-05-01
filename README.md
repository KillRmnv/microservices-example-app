# Microservices Example App - Event Ticket Sales System

A fully functional microservices-based event ticketing platform built with Java 25, Spring Boot 4.0.5, and Vanilla JavaScript. This project demonstrates modern microservice architecture patterns including event-driven communication, JWT authentication, role-based access control, and containerized deployment with Docker Compose.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Overview](#api-overview)
- [Frontend](#frontend)
- [Key Features](#key-features)
- [Kafka Event Flow](#kafka-event-flow)
- [Local Development](#local-development)
- [Possible Improvements](#possible-improvements)

## Architecture Overview

The system follows a microservice architecture with 4 core services behind an API Gateway, supported by PostgreSQL, Redis, and Kafka infrastructure.

### Core Services

| Service | Port | Description | Technology Stack |
|---------|------|-------------|------------------|
| **Gateway** | 8080 | Single entry point for all client requests, request routing, JWT validation, static frontend serving | Spring Cloud Gateway, WebFlux, Spring Security, Resilience4j |
| **User Service** | 8081 | User management, authentication, authorization, role management | Spring Boot, Spring Security, JWT (JJWT), PostgreSQL, Redis, Kafka |
| **Booking Service** | 8082 | Event, ticket, venue, and town management; ticket booking operations | Spring Boot, Spring Data JPA, PostgreSQL, Redis (Redisson), Kafka |
| **Notification Service** | 8083 | Asynchronous email notifications for authentication and booking events | Spring Boot, Spring Mail, Kafka Consumer |

### Infrastructure Components
- **PostgreSQL 16**: Two separate databases (`user_service`, `booking_service`) with Flyway migrations (see `user-service/src/main/resources/db/migration/` and `booking-service/src/main/resources/db/migration/`)
- **Redis 7**: Caching (booking-service) and rate limiting (user-service)
- **Apache Kafka 7.5 + Zookeeper**: Event-driven communication between services (cp-kafka:7.5.0 in Docker, apache/kafka-native:latest in tests)
- **Docker Compose**: Orchestration of all services and infrastructure

## Tech Stack

### Backend
- **Java 25** (uncommon version—requires verification before building)
- **Spring Boot 4.0.5**: Core framework
- **Spring Cloud Gateway**: API gateway (gateway service, uses WebFlux)
- **Spring Security**: Authentication and authorization (JWT via JJWT 0.12.3)
- **Spring Data JPA**: Database access (PostgreSQL)
- **Spring Kafka**: Kafka integration for event-driven communication
- **Flyway**: Database migrations (auto-runs on service startup)
- **Redisson 4.3.0**: Redis client with Spring integration (booking-service)
- **Lombok 1.18.42**: Boilerplate code reduction
- **Password4j 1.8.2**: Password hashing (bcrypt)


### Testing
- **JUnit 5**: Unit and integration testing
- **Mockito**: Mocking
- **Testcontainers**: Integration tests with real infrastructure (PostgreSQL, Kafka, Redis)
- **Awaitility**: Asynchronous operation testing

### DevOps
- **Docker + Docker Compose**: Containerization
- **Multi-stage Docker Builds**: JDK for build, JRE for runtime
- **Gradle 8+**: Build tool (wrapper included per service)

## Project Structure

```
microservices-example-app/
├── gateway/                          # API Gateway service
│   ├── src/main/java/.../gateway/   # Java source code
│   ├── src/main/resources/static/    # Frontend assets (JS, CSS, HTML)
│   ├── Dockerfile                    # Multi-stage build
│   └── build.gradle                  # Dependencies
├── user-service/                     # User management service
├── booking-service/                  # Booking management service
├── notification-service/             # Email notification service
├── gradle/                           # Shared Gradle configuration
│   └── version.gradle                # Centralized version management
├── docker-compose.yml                # Infrastructure orchestration
├── init-postgres.sql                 # Database initialization
└── .env.example                      # Example environment variables
```

## Prerequisites

- Java 25 JDK (for local development)
- Docker & Docker Compose
- Gradle 8+ (or use included wrappers `./gradlew`)
- (Optional) PostgreSQL 16, Redis 7, Kafka 7.5 for local development without Docker

## Quick Start

### 1. Clone the repository
```bash
git clone <repository-url>
cd microservices-example-app
```

### 2. Configure environment variables
Copy the example environment file to create your own `.env` files:
```bash
cp .env.example .env
cp user-service/.env.example user-service/.env
cp booking-service/.env.example booking-service/.env
cp notification-service/.env.example notification-service/.env
cp gateway/.env.example gateway/.env
```

Edit the `.env` files as needed (especially `JWT_SECRET` and email configuration for notification service).

### 3. Start all services with Docker Compose
```bash
docker compose up -d --build
```

This will start all infrastructure components and microservices. The gateway will be available at:
- **Frontend**: http://localhost:8080
- **API Base URL**: http://localhost:8080

### 4. Verify the setup
Check running services:
```bash
docker compose ps
```

## API Overview

All API endpoints are accessed through the Gateway at `http://localhost:8080`.

### User Service Endpoints
| Endpoint | Method | Description | Access |
|----------|--------|-------------|--------|
| `/users/auth/register` | POST | Register new user | Public |
| `/users/auth/login` | POST | User login (returns JWT) | Public |
| `/users/auth/forget-password` | GET | Request password reset | Public |
| `/users/auth/reset-password` | POST | Reset password with token | Public |
| `/users` | GET/PUT/DELETE | User CRUD operations | ADMIN only |
| `/users/search` | GET | Search users by filter | ADMIN only |

### Booking Service Endpoints
| Endpoint | Method | Description | Access |
|----------|--------|-------------|--------|
| `/booking/events` | GET/POST/PUT/DELETE | Event management | CUSTOMER (read), EVENT_MANAGER+ (write) |
| `/booking/tickets` | GET/POST/PUT/DELETE | Ticket management | CUSTOMER (own tickets), EVENT_MANAGER+ (all) |
| `/booking/venues` | GET/POST/PUT/DELETE | Venue management | EVENT_MANAGER+ |
| `/booking/towns` | GET/POST/DELETE | Town management | ADMIN only |
| `/booking/seats` | GET/POST/PUT/DELETE | Seat management | EVENT_MANAGER+ |

### Role Hierarchy
- **CUSTOMER**: Can view events, book/cancel own tickets
- **EVENT_MANAGER**: CUSTOMER permissions + manage events, venues, seats
- **ADMIN**: Full system access including user management and town management


## Key Features

1. **JWT Authentication**: Stateless authentication with JWT tokens containing user roles
2. **Event-Driven Architecture**: Kafka-based async communication for decoupled services
3. **Role-Based Access Control**: Three-tier role system (CUSTOMER → EVENT_MANAGER → ADMIN) with permission mapping
4. **Caching**: Redis caching for frequently accessed data (booking-service)
5. **Database Migrations**: Flyway for versioned database schema management per service
6. **Global Error Handling**: Consistent error responses across services
7. **Containerized Deployment**: Multi-stage Docker builds (JDK for build, JRE for runtime)

## Kafka Event Flow

Services communicate asynchronously via Kafka topics. All events are consumed by the notification-service for email notifications.

| Topic | Producer | Event | Purpose |
|-------|----------|-------|---------|
| `notification.authentication` | user-service | `SuccessfulRegistrationEmailEvent` | Welcome email on registration |
| `notification.forget-password` | user-service | `ForgetPasswordEvent` | Password reset link email |
| `notification.user-lifecycle` | user-service | `UserDeletedEvent`, `UserUpdatedEvent` | Notify on account changes |
| `notification.booking` | booking-service | `SuccessfulBookingEvent` | Booking confirmation email |
| `notification.refund` | booking-service | `SuccessfulTicketRefundEvent` | Refund confirmation email |
| `notification.mass-mailing` | user-service | `MassDeleteEventMailingEvent`, `MassUpdateEventMailingEvent` | Bulk email notifications |
| `user.mass-mail` | booking-service | `DeleteEventEvent`, `UpdateEventEvent` | Trigger mass mailing on event changes |

**Configuration**: Topic names are configurable via properties in each service's `application.properties` / `application.yml`.

## Local Development

Each service has its own `./gradlew` — there is no root Gradle build.

```bash
# Start infrastructure only (required for local service runs and tests)
docker compose up -d postgres redis zookeeper kafka

# Run individual services locally
cd user-service && ./gradlew bootRun
cd booking-service && ./gradlew bootRun
cd gateway && ./gradlew bootRun   # serves frontend at http://localhost:8080

# Run all tests in a service (requires Docker for Testcontainers)
cd <service> && ./gradlew test

# Run a single test class
cd <service> && ./gradlew test --tests "*.TestClassName"
```
