-- PostgreSQL Database Initialization Script (On-Premise Simulation)
-- Database: iot_db
-- Run these scripts on the PostgreSQL instance.

-- 1. Verify Logical Replication configuration (requires reboot if changed)
-- These settings must be in postgresql.conf:
-- wal_level = logical
-- max_replication_slots = 4
-- max_wal_senders = 4
SELECT name, setting, unit, context FROM pg_settings WHERE name IN ('wal_level', 'max_replication_slots', 'max_wal_senders');

-- 2. Create replication user for Debezium CDC
CREATE USER replication_user WITH REPLICATION PASSWORD 'YourSecurePasswordHere!';

-- 3. Create the IoT Telemetry table
CREATE TABLE IF NOT EXISTS public.iot_events (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    aqi INT,
    temperature NUMERIC(5,2),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Grant Permissions to replication user
GRANT ALL PRIVILEGES ON DATABASE iot_db TO replication_user;
GRANT USAGE ON SCHEMA public TO replication_user;
GRANT ALL PRIVILEGES ON TABLE public.iot_events TO replication_user;
GRANT USAGE, SELECT ON SEQUENCE iot_events_id_seq TO replication_user;

-- 5. Set Replica Identity for Debezium (determines what details are included in DELETE/UPDATE events)
-- DEFAULT records old values of primary key columns only. FULL records all old column values.
ALTER TABLE public.iot_events REPLICA IDENTITY DEFAULT;

-- 6. Verify table creation
\d public.iot_events;
