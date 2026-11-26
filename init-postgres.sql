CREATE DATABASE user_service;
CREATE DATABASE booking_service;
CREATE DATABASE collector_db;
CREATE DATABASE assistant_db;

\connect user_service
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
\connect booking_service
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
\connect collector_db
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
\connect assistant_db
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
