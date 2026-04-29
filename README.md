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
- [Testing](#testing)
- [Key Features](#key-features)
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
- **PostgreSQL 16**: Two separate databases (`user_service`, `booking_service`) with Flyway migrations
- **Redis 7**: Caching and rate limiting
- **Apache Kafka 7.5 + Zookeeper**: Event-driven communication between services
- **Docker Compose**: Orchestration of all services and infrastructure

## Tech Stack

### Backend
- **Java 25** 
- **Spring Boot 4.0.5**: Core framework
- **Spring Cloud Gateway**: API gateway
- **Spring Security**: Authentication and authorization
- **Spring Data JPA**: Database access
- **Spring Kafka**: Kafka integration
- **JJWT 0.12.3**: JSON Web Token implementation
- **Flyway**: Database migrations
- **Redisson**: Redis client with Spring integration
- **Lombok**: Boilerplate code reduction
- **Password4j**: Password hashing (bcrypt)


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
├── .env.example                      # Example environment variables
└── AGENTS.md                         # Developer guidelines
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
3. **Role-Based Access Control**: Three-tier role system with permission mapping
4**Caching**: Redis caching for frequently accessed data
5**Database Migrations**: Flyway for versioned database schema management
6**Global Error Handling**: Consistent error responses across services
7**Containerized Deployment**: Multi-stage Docker builds for optimized images

## Local Development

To run individual services locally (requires infrastructure to be running):

```bash
# Start infrastructure only
docker compose up -d postgres redis zookeeper kafka

# Run user-service locally
cd user-service && ./gradlew bootRun

# Run booking-service locally
cd booking-service && ./gradlew bootRun

# Run gateway locally (serves frontend)
cd gateway && ./gradlew bootRun
```


