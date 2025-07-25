"""
Example configuration for testing the USD Binding Protocol Extension
"""

import json

# Example configuration files for testing

MQTT_CONFIG = {
    "broker_url": "mqtts://test.mosquitto.org:8883",
    "topics": {
        "temperature": "/hvac/room1/temperature",
        "humidity": "/hvac/room1/humidity",
        "status": "/hvac/room1/status"
    }
}

REST_CONFIG = {
    "base_url": "https://jsonplaceholder.typicode.com",
    "endpoints": {
        "user_info": "/users/1",
        "posts": "/posts?userId=1",
        "comments": "/comments?postId=1"
    }
}

FILE_CONFIG = {
    "paths": {
        "config": "./test_data/config.json",
        "sensor_data": "./test_data/sensor.txt",
        "status": "./test_data/status.json"
    }
}

# Sample test data files
TEST_CONFIG_JSON = {
    "threshold": 25.5,
    "enabled": True,
    "device_name": "TestDevice001"
}

TEST_SENSOR_DATA = "23.7"

TEST_STATUS_JSON = {
    "status": "active",
    "last_update": "2024-01-15T10:30:00Z",
    "error_count": 0
}

def create_test_files():
    """Create test files for file protocol testing"""
    import os
    
    # Create test data directory
    os.makedirs("./test_data", exist_ok=True)
    
    # Write test files
    with open("./test_data/config.json", "w") as f:
        json.dump(TEST_CONFIG_JSON, f, indent=2)
    
    with open("./test_data/sensor.txt", "w") as f:
        f.write(TEST_SENSOR_DATA)
    
    with open("./test_data/status.json", "w") as f:
        json.dump(TEST_STATUS_JSON, f, indent=2)

if __name__ == "__main__":
    create_test_files()
    print("Test files created successfully!")
