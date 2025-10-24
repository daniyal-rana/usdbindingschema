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
    
    # Create MQTT client with callback API version 2
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    
    # Track connection status
    connected = [False]  # Use list to allow modification in nested function
    
    def on_connect(client, userdata, flags, rc, properties):
        rc_code = rc if isinstance(rc, int) else rc.value
        if rc_code == 0:
            connected[0] = True
            print("Connected to MQTT broker")
        else:
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = error_messages.get(rc_code, f"Unknown error code: {rc_code}")
            print(f"Connection failed: {error_msg}")
    
    def on_disconnect(client, userdata, flags, rc, properties):
        rc_code = rc if isinstance(rc, int) else rc.value
        if rc_code != 0:
            error_messages = {
                7: "Connection lost - likely broker is not running or not accessible"
            }
            error_msg = error_messages.get(rc_code, f"Unexpected disconnect with code: {rc_code}")
            print(error_msg)
        connected[0] = False
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    
    try:
        # Connect to broker
        try:
            client.connect(broker, port, 60)
        except ConnectionRefusedError:
            print(f"\n❌ ERROR: Could not connect to MQTT broker at {broker}:{port}")
            print("The broker appears to be offline or not accepting connections.\n")
            print("To fix this:")
            print("  1. Check if mosquitto is running: sudo systemctl status mosquitto")
            print("  2. Start mosquitto: sudo systemctl start mosquitto")
            print("  3. Or run mosquitto manually: mosquitto -v")
            return
        except Exception as e:
            print(f"\n❌ ERROR: Connection failed: {e}")
            return
            
        client.loop_start()
        
        # Wait for connection to be established
        print("Connecting to MQTT broker...")
        timeout = 10
        start_time = time.time()
        while not connected[0] and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if not connected[0]:
            print("\n❌ Failed to connect to broker within timeout")
            print(f"Make sure the MQTT broker is running on {broker}:{port}")
            print("\nTo check/start mosquitto:")
            print("  sudo systemctl status mosquitto")
            print("  sudo systemctl start mosquitto")
            return
        
        while True:
            # Publish to each topic
            for topic, message_creator, value_generator in topics_and_generators:
                if not connected[0]:
                    print("Not connected to broker, skipping publish")
                    break
                    
                value = round(value_generator(), 1)
                message = message_creator(value)
                message_json = json.dumps(message)
                
                # Publish message
                result = client.publish(topic, message_json)
                
                # Wait for publish to complete (with timeout)
                result.wait_for_publish(timeout=1.0)
                
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
