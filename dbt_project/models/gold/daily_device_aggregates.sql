-- Gold Layer Model: Aggregates IoT sensor data daily per device.
-- Materialized as a table in the ANALYTICS schema.

WITH silver_events AS (
    SELECT * FROM {{ ref('clean_iot_events') }}
)

SELECT
    device_id,
    event_date,
    COUNT(event_id) AS total_readings,
    
    -- AQI Metrics
    ROUND(AVG(aqi), 1) AS avg_aqi,
    MAX(aqi) AS max_aqi,
    MIN(aqi) AS min_aqi,
    
    -- Temperature Metrics
    ROUND(AVG(temperature), 2) AS avg_temperature,
    MAX(temperature) AS max_temperature,
    MIN(temperature) AS min_temperature,
    
    -- Coordinates (averaging is a safe fallback if device is slightly moving or stationary)
    ROUND(AVG(latitude), 6) AS center_latitude,
    ROUND(AVG(longitude), 6) AS center_longitude,
    
    -- Metadata
    CURRENT_TIMESTAMP() AS last_aggregated_at
FROM silver_events
GROUP BY 
    device_id, 
    event_date
