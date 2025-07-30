# Simple MQTT Binding API - POC

This is a simplified, MQTT-only binding schema for connecting USD attributes to MQTT data streams. Perfect for proof-of-concept IoT integrations with Omniverse.

## Quick Start

### 1. Basic MQTT Binding

```usd
def Cube "MySensor" (
    prepend apiSchemas = ["MQTTBindingAPI"]
)
{
    double temperature = 22.0 (
        customData = {
            dictionary mqtt = {
                string broker = "localhost:1883"
                string topic = "sensors/temperature"
                string jsonPath = "$.value"
                string unit = "celsius"
                string description = "Room temperature"
            }
        }
    )
}
```

### 2. MQTT Configuration Options

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `broker` | string | `"localhost:1883"` | MQTT broker address and port |
| `topic` | string | `""` | MQTT topic to subscribe to |
| `jsonPath` | string | `""` | JSONPath to extract data from message |
| `unit` | string | `""` | Unit of measurement |
| `description` | string | `""` | Human-readable description |
| `qos` | int | `0` | MQTT Quality of Service (0, 1, or 2) |
| `enabled` | bool | `true` | Whether binding is active |
| `refreshInterval` | int | `1000` | Processing interval in milliseconds |

### 3. JSONPath Examples

- **Simple value**: `$.value`
- **Nested object**: `$.data.temperature`
- **CloudEvents format**: `$.data.temperature`
- **Array access**: `$.sensors[0].reading`
- **Complex path**: `$.measurements.humidity`

### 4. Example USD Files

- **`AirConditioners_Test.usda`**: Simple temperature sensor
- **`MultiSensor_Test.usda`**: Multiple sensor types
- **`IoTBindingAPI_Examples.usda`**: Various MQTT configurations

### 5. MQTT Message Formats

The extension supports various JSON message formats:

**Simple value:**
```json
{"value": 23.5}
```

**CloudEvents format:**
```json
{
  "specversion": "1.0",
  "type": "sensor.reading",
  "source": "temp-sensor-001",
  "data": {
    "temperature": 23.5,
    "timestamp": "2025-07-29T10:30:00Z"
  }
}
```

**Complex sensor data:**
```json
{
  "measurements": {
    "humidity": 45.2,
    "pressure": 1013.25
  },
  "location": "Room A",
  "timestamp": "2025-07-29T10:30:00Z"
}
```

### 6. Extension Usage

The extension automatically:

1. **Discovers** USD files with MQTT bindings
2. **Connects** to MQTT brokers specified in bindings
3. **Subscribes** to topics and updates USD attributes
4. **Displays** real-time values in Omniverse UI

### 7. Testing

Use the included `mqtt_test_publisher.py` to send test data:

```bash
python mqtt_test_publisher.py
```

This publishes sample data to the topics used in the test USD files.

### 8. Backward Compatibility

The extension supports multiple binding formats:

**New simplified format (recommended):**
```usd
customData = {
    dictionary mqtt = {
        string broker = "localhost:1883"
        string topic = "sensors/temp"
        string jsonPath = "$.value"
    }
}
```

**Legacy IoT format:**
```usd
customData = {
    dictionary binding = {
        string protocol = "mqtt"
        string uri = "mqtt://localhost:1883"
        string topic = "sensors/temp"
        string jsonPath = "$.value"
    }
}
```

**Original legacy format:**
```usd
customData = {
    string binding_protocol = "mqtt"
    string binding_uri = "mqtt://localhost:1883"
    string binding_topic = "sensors/temp"
    string binding_jsonPath = "$.value"
}
```

## Files

- **`MQTTBindingAPI.usda`**: Simplified MQTT-only schema
- **`extension.py`**: Updated extension with MQTT-only focus
- **Test files**: Examples using the simple schema format

This POC focuses purely on MQTT connectivity, making it easy to get started with real-time IoT data in Omniverse!
