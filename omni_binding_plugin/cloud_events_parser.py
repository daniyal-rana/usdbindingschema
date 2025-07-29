#!/usr/bin/env python3
"""
Cloud Events parser utility for USD Binding System
Handles parsing and extracting data from Cloud Events formatted messages
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime

class CloudEventsParser:
    """Parser for Cloud Events formatted messages"""
    
    REQUIRED_ATTRIBUTES = ["specversion", "id", "source", "type"]
    OPTIONAL_ATTRIBUTES = ["datacontenttype", "dataschema", "subject", "time"]
    
    def __init__(self):
        pass
    
    def is_cloud_event(self, message: Any) -> bool:
        """Check if a message is a valid Cloud Event"""
        if not isinstance(message, dict):
            return False
            
        # Check for required attributes
        for attr in self.REQUIRED_ATTRIBUTES:
            if attr not in message:
                return False
                
        # Check spec version
        if message.get("specversion") not in ["1.0"]:
            return False
            
        return True
    
    def parse_cloud_event(self, message: Any) -> Optional[Dict[str, Any]]:
        """Parse a Cloud Event message and extract data"""
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except json.JSONDecodeError:
                return None
                
        if not self.is_cloud_event(message):
            return None
            
        parsed_event = {
            # Core CloudEvents attributes
            "specversion": message.get("specversion"),
            "id": message.get("id"),
            "source": message.get("source"),
            "type": message.get("type"),
            "time": message.get("time"),
            "datacontenttype": message.get("datacontenttype"),
            "subject": message.get("subject"),
            
            # Event data
            "data": message.get("data"),
            
            # Extension attributes (everything else)
            "extensions": {}
        }
        
        # Collect extension attributes
        for key, value in message.items():
            if key not in self.REQUIRED_ATTRIBUTES and key not in self.OPTIONAL_ATTRIBUTES and key != "data":
                parsed_event["extensions"][key] = value
        
        return parsed_event
    
    def extract_sensor_data(self, cloud_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract sensor data from a Cloud Event"""
        if not cloud_event or "data" not in cloud_event:
            return None
            
        data = cloud_event["data"]
        if not isinstance(data, dict):
            return None
            
        # Extract common sensor fields
        sensor_data = {}
        
        # Temperature data
        if "temperature" in data:
            sensor_data["temperature"] = data["temperature"]
            sensor_data["unit"] = data.get("unit", "celsius")
            
        # Timestamp
        if "timestamp" in data:
            sensor_data["timestamp"] = data["timestamp"]
        elif cloud_event.get("time"):
            sensor_data["timestamp"] = cloud_event["time"]
            
        # Sensor metadata
        sensor_data["sensor_id"] = data.get("sensor_id")
        sensor_data["device_id"] = cloud_event.get("extensions", {}).get("device")
        sensor_data["status"] = data.get("status", "unknown")
        sensor_data["accuracy"] = data.get("accuracy")
        
        # Cloud Event metadata
        sensor_data["event_id"] = cloud_event.get("id")
        sensor_data["event_type"] = cloud_event.get("type")
        sensor_data["event_source"] = cloud_event.get("source")
        
        return sensor_data
    
    def get_temperature_value(self, message: Any) -> Optional[float]:
        """Extract just the temperature value from a message"""
        cloud_event = self.parse_cloud_event(message)
        if not cloud_event:
            return None
            
        sensor_data = self.extract_sensor_data(cloud_event)
        if not sensor_data:
            return None
            
        return sensor_data.get("temperature")

# Example usage and testing
if __name__ == "__main__":
    parser = CloudEventsParser()
    
    # Test Cloud Event message
    test_message = {
        "specversion": "1.0",
        "id": "12345",
        "source": "urn:hvac:device:aircon3245",
        "type": "com.example.hvac.temperature.reading",
        "time": "2025-07-29T10:30:00Z",
        "datacontenttype": "application/json",
        "device": "aircon3245",
        "data": {
            "temperature": 23.5,
            "unit": "celsius",
            "timestamp": "2025-07-29T10:30:00Z",
            "sensor_id": "aircon3245-temp-01",
            "status": "normal"
        }
    }
    
    print("🧪 Testing Cloud Events Parser")
    print("=" * 40)
    
    # Test parsing
    parsed = parser.parse_cloud_event(test_message)
    print(f"✅ Parsed Cloud Event: {parsed['id']}")
    
    # Test sensor data extraction
    sensor_data = parser.extract_sensor_data(parsed)
    print(f"🌡️  Temperature: {sensor_data['temperature']}°{sensor_data['unit']}")
    
    # Test simple temperature extraction
    temp = parser.get_temperature_value(test_message)
    print(f"🔥 Simple temp extraction: {temp}°C")
