import os
import boto3
import logging
from datetime import datetime, timezone
import snowflake.connector

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS Timestream Client
timestream_client = boto3.client('timestream-write')

def handler(event, context):
    """
    Lambda Handler: Fetches new sensor records from Snowflake and writes to AWS Timestream.
    """
    # 1. Load Configurations from environment variables
    sf_account = os.environ.get("SNOWFLAKE_ACCOUNT")
    sf_user = os.environ.get("SNOWFLAKE_USER")
    sf_password = os.environ.get("SNOWFLAKE_PASSWORD")
    sf_database = os.environ.get("SNOWFLAKE_DATABASE", "HACKATHON_IOT")
    sf_schema = os.environ.get("SNOWFLAKE_SCHEMA", "CLEAN")
    
    timestream_db = os.environ.get("TIMESTREAM_DATABASE", "IoTDatabase")
    timestream_table = os.environ.get("TIMESTREAM_TABLE", "Telemetry")
    
    # 2. Connect to Snowflake
    logger.info("Connecting to Snowflake...")
    try:
        conn = snowflake.connector.connect(
            account=sf_account,
            user=sf_user,
            password=sf_password,
            database=sf_database,
            schema=sf_schema
        )
        cursor = conn.cursor()
    except Exception as e:
        logger.error(f"Error connecting to Snowflake: {e}")
        raise e

    # 3. Query the latest 5 minutes of data from Silver layer
    query = """
    SELECT DEVICE_ID, LATITUDE, LONGITUDE, AQI, TEMPERATURE, EVENT_TIMESTAMP
    FROM HACKATHON_IOT.CLEAN.CLEAN_IOT_EVENTS
    WHERE EVENT_TIMESTAMP >= DATEADD('minute', -5, CURRENT_TIMESTAMP())
    ORDER BY EVENT_TIMESTAMP ASC;
    """
    
    try:
        logger.info("Querying Snowflake Silver layer...")
        cursor.execute(query)
        rows = cursor.fetchall()
        logger.info(f"Retrieved {len(rows)} new records.")
    except Exception as e:
        logger.error(f"Error querying Snowflake: {e}")
        conn.close()
        raise e
    finally:
        cursor.close()
        conn.close()

    if not rows:
        logger.info("No new telemetry records to sync.")
        return {"statusCode": 200, "body": "No data to sync."}

    # 4. Format and write to AWS Timestream
    records = []
    for row in rows:
        device_id = row[0]
        lat = row[1]
        lon = row[2]
        aqi = row[3]
        temp = float(row[4])
        # Convert datetime to epoch milliseconds
        dt_obj = row[5]
        epoch_ms = str(int(dt_obj.replace(tzinfo=timezone.utc).timestamp() * 1000))
        
        # Prepare multi-measure record
        record = {
            'Dimensions': [
                {'Name': 'device_id', 'Value': device_id}
            ],
            'MeasureName': 'telemetry',
            'MeasureValues': [
                {'Name': 'latitude', 'Value': str(lat), 'Type': 'DOUBLE'},
                {'Name': 'longitude', 'Value': str(lon), 'Type': 'DOUBLE'},
                {'Name': 'aqi', 'Value': str(aqi), 'Type': 'BIGINT'},
                {'Name': 'temperature', 'Value': str(temp), 'Type': 'DOUBLE'}
            ],
            'MeasureValueType': 'MULTI',
            'Time': epoch_ms,
            'TimeUnit': 'MILLISECONDS'
        }
        records.append(record)
        
    # Write to Timestream in batches of 100 (boto3 limit)
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            logger.info(f"Writing batch of {len(batch)} records to Timestream...")
            response = timestream_client.write_records(
                DatabaseName=timestream_db,
                TableName=timestream_table,
                Records=batch
            )
            logger.info(f"Timestream Write Response: {response['ResponseMetadata']['HTTPStatusCode']}")
        except Exception as e:
            logger.error(f"Failed to write records to Timestream: {e}")
            raise e

    return {
        "statusCode": 200,
        "body": f"Successfully synchronized {len(records)} records to Timestream."
    }
