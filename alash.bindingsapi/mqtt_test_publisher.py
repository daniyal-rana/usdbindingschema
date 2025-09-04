#!/usr/bin/env python3
"""
Generic MQTT test publisher to simulate various sensor data.
This script publishes different types of data that can be used to test the generic binding system.

To use:
1. Install paho-mqtt: pip install paho-mqtt
2. Start an MQTT broker (e.g., mosquitto on localhost:1883)
3. Run this script: python mqtt_test_publisher.py
"""

import json
import time
import random
import sys

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Install with: pip install paho-mqtt")
    sys.exit(1)


def create_temperature_message(temperature):
    """Create a CloudEvents-formatted temperature message."""
    return {
        "specversion": "1.0",
        "type": "com.example.temperature",
        "source": "/sensors/aircon3245",
        "id": f"temp-{int(time.time())}",
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datacontenttype": "application/json",
        "data": {
            "deviceId": "aircon3245",
            "temperature": temperature,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    }


# def create_humidity_message(humidity):
#     """Create a sensor data message for humidity."""
#     return {
#         "sensor_type": "humidity",
#         "device_id": "sensor001",
#         "measurements": {
#             "humidity": humidity
#         },
#         "timestamp": int(time.time())
#     }


# def create_pressure_message(pressure):
#     """Create a simple pressure reading."""
#     return {
#         "pressure": pressure,
#         "location": "room_a"
#     }


def main():
    # MQTT settings
    broker = "localhost"
    port = 1883
    
    topics_and_generators = [
        ("devices/aircon3245/temperature", create_temperature_message, lambda: 22.0 + random.uniform(-1.0, 3.0)),
        # ("sensors/humidity", create_humidity_message, lambda: 45.0 + random.uniform(-10.0, 20.0)),
        # ("environment/pressure", create_pressure_message, lambda: 1013.25 + random.uniform(-20.0, 20.0))
    ]
    
    print(f"Starting generic MQTT publisher...")
    print(f"Broker: {broker}:{port}")
    print(f"Topics: {[topic for topic, _, _ in topics_and_generators]}")
    print("Press Ctrl+C to stop")
    
    # Create MQTT client
    client = mqtt.Client()
    
    try:
        # Connect to broker
        client.connect(broker, port, 60)
        client.loop_start()
        
        print("Connected to MQTT broker")
        
        while True:
            # Publish to each topic
            for topic, message_creator, value_generator in topics_and_generators:
                value = round(value_generator(), 1)
                message = message_creator(value)
                message_json = json.dumps(message)
                
                # Publish message
                result = client.publish(topic, message_json)
                
                if result.rc == 0:
                    print(f"Published to {topic}: {value}")
                else:
                    print(f"Failed to publish to {topic}: {result.rc}")
            
            # Wait 5 seconds before next batch
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nStopping publisher...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected from MQTT broker")


if __name__ == "__main__":
    main()
