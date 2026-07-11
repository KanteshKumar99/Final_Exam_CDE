import time
import json
import random
import argparse
from datetime import datetime, timezone
import math

# Center of London O2 Arena
CENTER_LAT = 51.5030
CENTER_LON = 0.0032

# Sample devices list
DEVICES = [
    "device_london_001",
    "device_london_002",
    "device_london_003",
    "device_london_004",
    "device_london_005"
]

def generate_telemetry(device_id):
    """
    Generates random geolocation and telemetry data around the O2 Arena, London.
    """
    # Small random offset within ~500m (1 degree lat is ~111km, 1 degree lon is ~70km at this latitude)
    lat_offset = random.uniform(-0.004, 0.004)
    lon_offset = random.uniform(-0.006, 0.006)
    
    # Telemetry
    aqi = random.randint(15, 175) # Air Quality Index
    temperature = round(random.uniform(14.5, 29.0), 2) # Celsius
    
    return {
        "device_id": device_id,
        "latitude": round(CENTER_LAT + lat_offset, 6),
        "longitude": round(CENTER_LON + lon_offset, 6),
        "aqi": aqi,
        "temperature": temperature,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def run_local_simulation(interval, duration):
    """Prints events to stdout."""
    print("Starting local IoT simulation. Press Ctrl+C to stop.")
    start_time = time.time()
    try:
        while True:
            for device in DEVICES:
                payload = generate_telemetry(device)
                print(json.dumps(payload))
            
            time.sleep(interval)
            if duration and (time.time() - start_time) > duration:
                print("Simulation duration reached.")
                break
    except KeyboardInterrupt:
        print("Simulation stopped by user.")

def run_postgres_simulation(connection_string, interval, duration):
    """Writes directly to PostgreSQL to simulate ingestion endpoint for local validation."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 is not installed. Install it using: pip install psycopg2-binary")
        return
    
    print(f"Connecting to PostgreSQL: {connection_string}")
    try:
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        print("Connected to PostgreSQL successfully. Starting ingestion simulation...")
        
        start_time = time.time()
        while True:
            for device in DEVICES:
                payload = generate_telemetry(device)
                cursor.execute(
                    """
                    INSERT INTO public.iot_events (device_id, latitude, longitude, aqi, temperature, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (payload["device_id"], payload["latitude"], payload["longitude"], 
                     payload["aqi"], payload["temperature"], payload["timestamp"])
                )
            conn.commit()
            print(f"Inserted batch of {len(DEVICES)} device readings.")
            
            time.sleep(interval)
            if duration and (time.time() - start_time) > duration:
                break
    except KeyboardInterrupt:
        print("Simulation stopped.")
    except Exception as e:
        print(f"Error in PostgreSQL simulation: {e}")
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()
            print("PostgreSQL connection closed.")

def run_aws_iot_simulation(endpoint, cert_path, key_path, root_ca, interval, duration):
    """Publishes to AWS IoT Core using MQTT."""
    try:
        from AWSIoTPythonSDK.MQTTLib import AWSIotMqttClient
    except ImportError:
        print("AWS IoT Device SDK is not installed. Install it using: pip install AWSIoTPythonSDK")
        return

    print(f"Initializing AWS IoT MQTT client for endpoint: {endpoint}")
    my_mqtt_client = AWSIotMqttClient("iot-device-simulator")
    my_mqtt_client.configureEndpoint(endpoint, 8883)
    my_mqtt_client.configureCredentials(root_ca, key_path, cert_path)
    
    my_mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
    my_mqtt_client.configureOfflinePublishQueueing(-1)
    my_mqtt_client.configureDrainingInterval(2)
    my_mqtt_client.configureConnectDisconnectTimeout(10)
    my_mqtt_client.configureMqttKeepAliveInterval(30)
    
    print("Connecting to AWS IoT Core...")
    my_mqtt_client.connect()
    print("Connected! Commencing MQTT telemetry publish...")
    
    topic = "iot/events"
    start_time = time.time()
    try:
        while True:
            for device in DEVICES:
                payload = generate_telemetry(device)
                message_json = json.dumps(payload)
                my_mqtt_client.publish(topic, message_json, 1)
                print(f"Published to topic {topic}: {message_json}")
            
            time.sleep(interval)
            if duration and (time.time() - start_time) > duration:
                break
    except KeyboardInterrupt:
        print("Simulation stopped.")
    finally:
        my_mqtt_client.disconnect()
        print("Disconnected from AWS IoT.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IoT Geolocation & Telemetry Simulator")
    parser.add_argument("--mode", choices=["local", "postgres", "aws"], default="local",
                        help="Simulation mode: 'local' prints to stdout, 'postgres' writes directly to DB, 'aws' publishes to IoT Core MQTT.")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval in seconds between telemetry batches.")
    parser.add_argument("--duration", type=int, default=0, help="Duration of simulation in seconds (0 for infinite).")
    
    # Postgres configuration
    parser.add_argument("--db-url", type=str, default="dbname=iot_db user=postgres password=postgres host=localhost port=5432",
                        help="Connection string for PostgreSQL (required in postgres mode).")
    
    # AWS IoT configurations
    parser.add_argument("--endpoint", type=str, help="AWS IoT Core endpoint (required in aws mode).")
    parser.add_argument("--cert", type=str, help="Path to client certificate (required in aws mode).")
    parser.add_argument("--key", type=str, help="Path to private key (required in aws mode).")
    parser.add_argument("--ca", type=str, default="AmazonRootCA1.pem", help="Path to Root CA (aws mode).")
    
    args = parser.parse_args()
    
    if args.mode == "local":
        run_local_simulation(args.interval, args.duration)
    elif args.mode == "postgres":
        run_postgres_simulation(args.db_url, args.interval, args.duration)
    elif args.mode == "aws":
        if not args.endpoint or not args.cert or not args.key:
            print("Error: AWS IoT mode requires --endpoint, --cert, and --key arguments.")
        else:
            run_aws_iot_simulation(args.endpoint, args.cert, args.key, args.ca, args.interval, args.duration)
