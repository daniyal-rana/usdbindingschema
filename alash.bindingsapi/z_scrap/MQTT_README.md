# Generic MQTT Data Monitor Extension

This Kit extension automatically discovers and monitors MQTT data streams based on binding schemas defined in USD files. It's completely generic and configurable through USD metadata - no hardcoding required!

## Features

- **Automatic Discovery**: Scans USD files for MQTT binding configurations
- **Generic Data Support**: Works with any JSON data structure and JSONPath expressions
- **Multiple Topics**: Can monitor multiple MQTT topics simultaneously
- **Dynamic UI**: UI adapts based on discovered bindings
- **Real-time Updates**: Displays live data as it arrives via MQTT
- **Schema Compliant**: Follows the BindingAPI schema defined in USD files

## How It Works

1. **USD Scanning**: On startup, scans all USD files in the extension directory
2. **Binding Discovery**: Finds attributes with `binding_protocol = "mqtt"` metadata
3. **MQTT Subscription**: Automatically subscribes to all discovered topics
4. **Data Parsing**: Uses JSONPath expressions to extract values from messages
5. **UI Generation**: Creates UI elements for each discovered binding

## Setup

### 1. Install Dependencies

```bash
pip install paho-mqtt
# Optional for advanced JSONPath support:
pip install jsonpath-ng
```

### 2. Start MQTT Broker

You need an MQTT broker running. For testing, you can use Mosquitto:

**Windows:**
- Download and install Mosquitto from https://mosquitto.org/download/
- Start broker: `mosquitto -v`

**Linux/Mac:**
```bash
# Install mosquitto
sudo apt-get install mosquitto mosquitto-clients  # Ubuntu/Debian
brew install mosquitto  # macOS

# Start broker
mosquitto -v
```

### 3. Test with Sample Data

Use the included test publisher to simulate various sensor data:

```bash
python mqtt_test_publisher.py
```

This publishes data to multiple topics that match the sample USD configurations.

## Usage

1. Enable the extension in Omniverse Kit
2. The "MQTT Data Monitor" window will appear showing all discovered bindings
3. Click "Connect to MQTT" to start monitoring
4. Data will be displayed in real-time as it arrives
5. Use "Refresh USD" to reload configurations after USD file changes

## USD Configuration

Define MQTT bindings in any USD file using the BindingAPI schema:

```usd
#usda 1.0

def Scope "MyDevice" (
    prepend apiSchemas = ["BindingAPI"]
)
{
    def Cube "Sensor_001"
    {
        # Any attribute can be bound to MQTT data
        double temperature = 0.0 (
            customData = {
                token binding_protocol = "mqtt"
                token binding_operation = "stream"
                string binding_uri = "mqtt://localhost:1883"
                string binding_topic = "your/topic/here"
                string binding_jsonPath = "$.path.to.value"
            }
        )
        
        string status = "" (
            customData = {
                token binding_protocol = "mqtt"
                token binding_operation = "stream"
                string binding_uri = "mqtt://localhost:1883"
                string binding_topic = "status/topic"
                string binding_jsonPath = "$.status"
            }
        )
    }
}
```

## Supported JSONPath

The extension supports basic JSONPath expressions:
- `$.data.temperature` - Navigate nested objects
- `$.measurements.humidity` - Multiple levels
- `$.pressure` - Direct property access

For advanced JSONPath features, install `jsonpath-ng`.

## Example Configurations

The extension includes sample USD files:

1. **AirConditioners_Test.usda** - Temperature monitoring with CloudEvents format
2. **MultiSensor_Test.usda** - Multiple sensors with different data structures

## Message Formats

The extension works with any JSON format. Examples:

**CloudEvents format:**
```json
{
  "data": {
    "temperature": 23.5
  }
}
```

**Simple sensor format:**
```json
{
  "measurements": {
    "humidity": 65.2
  }
}
```

**Direct values:**
```json
{
  "pressure": 1013.25,
  "location": "room_a"
}
```
