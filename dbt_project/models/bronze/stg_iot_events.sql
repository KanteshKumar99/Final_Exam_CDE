-- Bronze Layer Model: Parses JSON payloads from Kafka Connect CDC.
-- Materialized as a view for low latency.

WITH raw_source AS (
    SELECT * FROM {{ source('snowflake_raw', 'iot_events') }}
)

SELECT
    -- Extract event data from the Debezium JSON payload ('after' state or fallback to 'before' on delete)
    COALESCE(
        RECORD_CONTENT:after:id::INT,
        RECORD_CONTENT:before:id::INT
    ) AS event_id,
    
    COALESCE(
        RECORD_CONTENT:after:device_id::VARCHAR,
        RECORD_CONTENT:before:device_id::VARCHAR
    ) AS device_id,
    
    COALESCE(
        RECORD_CONTENT:after:latitude::DOUBLE,
        RECORD_CONTENT:before:latitude::DOUBLE
    ) AS latitude,
    
    COALESCE(
        RECORD_CONTENT:after:longitude::DOUBLE,
        RECORD_CONTENT:before:longitude::DOUBLE
    ) AS longitude,
    
    COALESCE(
        RECORD_CONTENT:after:aqi::INT,
        RECORD_CONTENT:before:aqi::INT
    ) AS aqi,
    
    COALESCE(
        RECORD_CONTENT:after:temperature::DOUBLE,
        RECORD_CONTENT:before:temperature::DOUBLE
    ) AS temperature,
    
    COALESCE(
        RECORD_CONTENT:after:timestamp::VARCHAR,
        RECORD_CONTENT:before:timestamp::VARCHAR
    ) AS event_timestamp_raw,
    
    -- Extract CDC change metadata
    RECORD_CONTENT:op::VARCHAR AS op_type, -- 'c' = insert, 'u' = update, 'd' = delete
    RECORD_CONTENT:ts_ms::BIGINT AS cdc_timestamp_ms,
    
    -- Extract Kafka partition and offset metadata
    RECORD_METADATA:partition::INT AS kafka_partition,
    RECORD_METADATA:offset::BIGINT AS kafka_offset,
    RECORD_METADATA:CreateTime::BIGINT AS kafka_ingest_timestamp_ms
FROM raw_source
