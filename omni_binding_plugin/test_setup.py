"""
Test script to verify your AirConditioners_Test.usda configuration
"""

import json
import time
import threading
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
import uuid

class USDBindingTest:
    def __init__(self):
        # Match your USD file configuration
        self.broker_host = "broker.hivemq.com"
        self.broker_port = 1883
        self.topic = "cloudevents/temperature"
    
    def test_mqtt_publish(self):
        """Test publishing Cloud Events to your topic"""
        print("🔬 Testing USD Binding Configuration")
        print("=" * 50)
        print(f"Broker: {self.broker_host}:{self.broker_port}")
        print(f"Topic: {self.topic}")
        print(f"JSONPath: $.data.temperature")
        print("=" * 50)
        
        client = mqtt.Client()
        
        try:
            print(f"🔌 Connecting to {self.broker_host}...")
            client.connect(self.broker_host, self.broker_port, 60)
            
            # Publish test Cloud Events
            for i in range(5):
                temperature = round(20 + i * 2.5, 1)  # 20.0, 22.5, 25.0, 27.5, 30.0
                
                cloud_event = {
                    "specversion": "1.0",
                    "id": str(uuid.uuid4()),
                    "source": "urn:hvac:device:aircon3245",
                    "type": "com.example.hvac.temperature.reading",
                    "time": datetime.now(timezone.utc).isoformat(),
                    "datacontenttype": "application/json",
                    "data": {
                        "temperature": temperature,
                        "unit": "celsius",
                        "status": "normal"
                    }
                }
                
                message = json.dumps(cloud_event)
                result = client.publish(self.topic, message)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"✅ Published: Temperature {temperature}°C")
                    print(f"   JSONPath $.data.temperature will extract: {temperature}")
                else:
                    print(f"❌ Publish failed for {temperature}°C")
                
                time.sleep(2)
                
            print("\n🎉 Test complete!")
            print("\nNext steps:")
            print("1. Install the Omniverse extension: python install.ps1")
            print("2. Open AirConditioners_Test.usda in Omniverse")
            print("3. Enable 'USD Binding Protocol' extension")
            print("4. Watch the temperature attribute update!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            client.disconnect()

if __name__ == "__main__":
    test = USDBindingTest()
    test.test_mqtt_publish()