-- Silver Layer Model: Validates null values, casts types, and adds severity tags.
-- Materialized as a table in the CLEAN schema.

WITH bronze_events AS (
    SELECT * FROM {{ ref('stg_iot_events') }}
)

SELECT
    event_id,
    device_id,
    latitude,
    longitude,
    aqi,
    temperature,
    
    -- Parse timestamp safely (Snowflake functions)
    TRY_TO_TIMESTAMP_TZ(event_timestamp_raw) AS event_timestamp,
    CAST(TRY_TO_TIMESTAMP_TZ(event_timestamp_raw) AS DATE) AS event_date,
    
    -- Severity tagging based on AQI (Air Quality Index)
    CASE
        WHEN aqi IS NULL THEN 'Unknown'
        WHEN aqi <= 50 THEN 'Good'
        WHEN aqi <= 100 THEN 'Moderate'
        WHEN aqi <= 150 THEN 'Unhealthy for Sensitive Groups'
        WHEN aqi <= 200 THEN 'Unhealthy'
        ELSE 'Hazardous'
    END AS aqi_severity,
    
    -- Severity tagging based on Temperature (Celsius)
    CASE
        WHEN temperature IS NULL THEN 'Normal'
        WHEN temperature > 35.0 THEN 'Extreme Heat'
        WHEN temperature < 0.0 THEN 'Extreme Cold'
        ELSE 'Normal'
    END AS temp_severity,
    
    -- Auditing and metadata
    op_type,
    TO_TIMESTAMP_LNT(cdc_timestamp_ms / 1000) AS cdc_processed_at,
    TO_TIMESTAMP_LNT(kafka_ingest_timestamp_ms / 1000) AS kafka_ingest_at,
    CURRENT_TIMESTAMP() AS dbt_processed_at
FROM bronze_events
WHERE 
    -- Data Validation: filter out invalid entries
    device_id IS NOT NULL 
    AND latitude IS NOT NULL 
    AND longitude IS NOT NULL
    -- Filter out deleted records to represent active sensor logs
    AND (op_type IS NULL OR op_type != 'd')
