#!/usr/bin/env python3
"""
Schema generator for MQTTBindingAPI
This creates a proper USD schema file that Kit can understand.
"""

def generate_mqtt_schema():
    """Generate the MQTT Binding API schema."""
    
    schema_content = '''#usda 1.0
(
    doc = """MQTTBindingAPI Schema - Simple MQTT-only binding for USD attributes
    
    This schema provides a lightweight way to bind USD attributes to MQTT data streams.
    Perfect for proof-of-concept IoT integrations with Omniverse.
    """
)

class "MQTTBindingAPI" (
    doc = """MQTTBindingAPI provides simple MQTT data binding for USD attributes.
    
    This API schema can be applied to any prim to enable its attributes to receive
    real-time data from MQTT brokers.
    
    Example usage:
    ```
    def Cube "Sensor" (
        prepend apiSchemas = ["MQTTBindingAPI"]
    )
    {
        double temperature = 22.0 (
            customData = {
                dictionary mqtt = {
                    string broker = "localhost:1883"
                    string topic = "sensors/temperature"
                    string jsonPath = "$.value"
                }
            }
        )
    }
    ```
    """
    customData = {
        string className = "MQTTBindingAPI"
        string libraryName = "mqttBinding"
        dictionary schemaKind = {
            string value = "nonAppliedAPI"
        }
    }
)
{
    # MQTT connection details
    uniform string mqtt:broker = "localhost:1883" (
        doc = """MQTT broker address and port.
        
        Examples:
        - localhost:1883
        - mqtt.example.com:1883
        - broker.hivemq.com:1883"""
    )
    
    uniform string mqtt:topic = "" (
        doc = """MQTT topic to subscribe to.
        
        Examples:
        - sensors/temperature
        - devices/sensor123/data
        - building/floor1/room5/humidity"""
    )
    
    # Data extraction
    uniform string mqtt:jsonPath = "" (
        doc = """JSONPath expression for extracting data from MQTT message.
        
        Examples:
        - $.value (simple value)
        - $.data.temperature (nested object)
        - $.sensors[0].reading (array access)"""
    )
    
    # Basic metadata
    uniform string mqtt:unit = "" (
        doc = """Unit of measurement (e.g., 'celsius', 'percent', 'meters')."""
    )
    
    uniform string mqtt:description = "" (
        doc = """Human-readable description of this MQTT binding."""
    )
    
    # Quality of Service
    uniform int mqtt:qos = 0 (
        doc = """MQTT Quality of Service level.
        
        - 0: At most once delivery
        - 1: At least once delivery  
        - 2: Exactly once delivery"""
    )
    
    # Control
    uniform bool mqtt:enabled = true (
        doc = """Whether this MQTT binding is currently enabled."""
    )
    
    uniform int mqtt:refreshInterval = 1000 (
        doc = """How often to process MQTT messages in milliseconds."""
    )
}
'''
    
    return schema_content

if __name__ == "__main__":
    print("Generating MQTT Binding API schema...")
    schema = generate_mqtt_schema()
    
    with open("MQTTBindingAPI.usda", "w") as f:
        f.write(schema)
    
    print("✅ MQTTBindingAPI.usda generated successfully!")
    print("This schema can now be used in Omniverse Kit extensions.")
