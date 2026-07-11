-- Snowflake Initialization Script for IoT Data Migration Pipeline
-- Database: HACKATHON_IOT
-- Execute this script as ACCOUNTADMIN or SECURITYADMIN in Snowflake.

-- 1. Create Database and Schemas
CREATE OR REPLACE DATABASE HACKATHON_IOT;

CREATE OR REPLACE SCHEMA HACKATHON_IOT.RAW;         -- Bronze (Raw CDC events)
CREATE OR REPLACE SCHEMA HACKATHON_IOT.CLEAN;       -- Silver (Validated & Casted telemetry)
CREATE OR REPLACE SCHEMA HACKATHON_IOT.ANALYTICS;   -- Gold (Aggregated reports & dashboards)

-- 2. Create Warehouse
CREATE OR REPLACE WAREHOUSE IOT_WH
  WITH WAREHOUSE_SIZE = 'XSMALL'
  WAREHOUSE_TYPE = 'STANDARD'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- 3. Create Security Roles
CREATE OR REPLACE ROLE IOT_PIPELINE_ROLE;
GRANT ALL PRIVILEGES ON DATABASE HACKATHON_IOT TO ROLE IOT_PIPELINE_ROLE;
GRANT ALL PRIVILEGES ON SCHEMA HACKATHON_IOT.RAW TO ROLE IOT_PIPELINE_ROLE;
GRANT ALL PRIVILEGES ON SCHEMA HACKATHON_IOT.CLEAN TO ROLE IOT_PIPELINE_ROLE;
GRANT ALL PRIVILEGES ON SCHEMA HACKATHON_IOT.ANALYTICS TO ROLE IOT_PIPELINE_ROLE;
GRANT USAGE, OPERATE ON WAREHOUSE IOT_WH TO ROLE IOT_PIPELINE_ROLE;

-- 4. Create raw table for Snowflake Kafka Connector
-- The Kafka connector writes to a table with columns RECORD_CONTENT and RECORD_METADATA.
CREATE OR REPLACE TABLE HACKATHON_IOT.RAW.IOT_EVENTS (
  RECORD_METADATA VARIANT,
  RECORD_CONTENT VARIANT
);

-- Grant write access to the raw table
GRANT ALL PRIVILEGES ON TABLE HACKATHON_IOT.RAW.IOT_EVENTS TO ROLE IOT_PIPELINE_ROLE;

-- 5. Create Dedicated Service User for Snowflake Kafka Connector
-- Generate public/private key-pair for secure connection (best practice)
-- openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
-- openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
CREATE OR REPLACE USER KAFKA_CONNECTOR_USER
  PASSWORD = 'SecureTempPassword123!'
  DEFAULT_ROLE = IOT_PIPELINE_ROLE
  DEFAULT_WAREHOUSE = IOT_WH
  MUST_CHANGE_PASSWORD = FALSE;

-- Set the public key for the user (replace with actual generated public key text)
-- ALTER USER KAFKA_CONNECTOR_USER SET RSA_PUBLIC_KEY='MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...';

-- Assign Role to the Connector User and Current Admin
GRANT ROLE IOT_PIPELINE_ROLE TO USER KAFKA_CONNECTOR_USER;
GRANT ROLE IOT_PIPELINE_ROLE TO ROLE SYSADMIN;

-- 6. Setup query examples for testing
-- Query raw events loaded by Kafka Connector:
SELECT * FROM HACKATHON_IOT.RAW.IOT_EVENTS LIMIT 10;
