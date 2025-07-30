# IoT Binding API Schema

This extension provides a comprehensive IoT binding schema for Universal Scene Description (USD) that allows you to connect USD attributes to external IoT data sources like MQTT brokers, REST APIs, databases, and more.

## Schema Overview

The `IoTBindingAPI` is a non-applied API schema that provides standardized attributes for binding USD properties to external data sources. It uses USD's `customData` mechanism to store binding configurations in a clean, structured way.

## Basic Usage

To use the IoT binding schema, add binding configuration to any USD attribute's `customData`:

```usd
def Cube "MySensor" (
    prepend apiSchemas = ["IoTBindingAPI"]
)
{
    double temperature = 22.5 (
        customData = {
            dictionary binding = {
                string protocol = "mqtt"
                string operation = "stream"
                string uri = "mqtt://localhost:1883"
                string topic = "sensors/temperature"
                string jsonPath = "$.data.temperature"
                string unit = "celsius"
                string description = "Room temperature sensor"
                int refreshInterval = 5000
                double minValue = -40.0
                double maxValue = 80.0
                bool enabled = true
            }
        }
    )
}
```

## Schema Structure

The binding configuration is stored in a `binding` dictionary within `customData`. This dictionary can contain the following properties:

### Core Properties

- **`protocol`** (string): The protocol used for data binding
  - Supported: `mqtt`, `rest`, `sql`, `grpc`, `websocket`, `file`, `modbus`, `opcua`
  
- **`operation`** (string): The operation mode for the binding
  - Supported: `read`, `write`, `stream`, `subscribe`, `poll`
  
- **`uri`** (string): Connection URI for the data source
  - Examples: `mqtt://broker:1883`, `https://api.example.com`, `file:///path/to/data.json`
  
- **`topic`** (string): Topic, endpoint, or identifier for the specific data
  - MQTT: `sensors/temperature/room1`
  - REST: `/devices/sensor123/temperature`
  - SQL: `SELECT value FROM sensors WHERE id='temp1'`

### Data Extraction

- **`jsonPath`** (string): JSONPath expression for extracting data from JSON responses
  - Examples: `$.data.temperature`, `$.sensors[0].value`, `$.measurements.humidity`
  
- **`xpath`** (string): XPath expression for extracting data from XML responses

- **`transform`** (string): Data transformation expression or function name

### Timing and Refresh

- **`refreshInterval`** (int): Refresh interval in milliseconds (default: 5000)
- **`refreshPolicy`** (string): When to refresh the binding
  - `interval`, `onchange`, `manual`, `oncreate`

### Authentication

- **`authMethod`** (string): Authentication method
  - Supported: `none`, `basic`, `bearer`, `apikey`, `oauth2`, `mtls`, `cert`
  
- **`authProfile`** (string): Named authentication profile for credentials
- **`authScope`** (string): Authentication scope for OAuth2/similar

### HTTP-Specific

- **`httpMethod`** (string): HTTP method for REST API calls (default: GET)
- **`httpHeaders`** (dictionary): Custom HTTP headers

### Quality of Service

- **`qos`** (int): Quality of Service level (protocol-specific)
  - For MQTT: 0 (at most once), 1 (at least once), 2 (exactly once)
  
- **`retain`** (bool): Whether to retain messages (MQTT-specific)
- **`timeout`** (int): Connection timeout in milliseconds (default: 30000)
- **`retryCount`** (int): Number of retry attempts on failure (default: 3)

### Validation and Metadata

- **`minValue`** (double): Minimum valid value for numeric data
- **`maxValue`** (double): Maximum valid value for numeric data
- **`unit`** (string): Unit of measurement (e.g., 'celsius', 'meters', 'percent')
- **`enabled`** (bool): Whether this binding is currently enabled (default: true)
- **`description`** (string): Human-readable description of this binding
- **`metadata`** (dictionary): Additional metadata for the binding

## Protocol Examples

### MQTT Stream

```usd
double temperature = 22.5 (
    customData = {
        dictionary binding = {
            string protocol = "mqtt"
            string operation = "stream"
            string uri = "mqtt://broker.local:1883"
            string topic = "sensors/temperature"
            string jsonPath = "$.data.temperature"
            string unit = "celsius"
            int qos = 1
            bool retain = false
        }
    }
)
```

### REST API Polling

```usd
double powerConsumption = 2500.0 (
    customData = {
        dictionary binding = {
            string protocol = "rest"
            string operation = "poll"
            string uri = "https://api.example.com/v1"
            string topic = "/devices/sensor123/power"
            string httpMethod = "GET"
            string jsonPath = "$.current_watts"
            string unit = "watts"
            int refreshInterval = 60000
            string authMethod = "bearer"
            string authProfile = "energy_api"
        }
    }
)
```

### Database Query

```usd
double dailyMaxTemp = 25.8 (
    customData = {
        dictionary binding = {
            string protocol = "sql"
            string operation = "poll"
            string uri = "postgresql://user:pass@db.local:5432/weather"
            string topic = "SELECT MAX(temperature) FROM daily_readings WHERE date = CURRENT_DATE"
            string unit = "celsius"
            int refreshInterval = 3600000
            string description = "Today's maximum temperature"
        }
    }
)
```

### OPC UA Industrial Protocol

```usd
float brightness = 0.75 (
    customData = {
        dictionary binding = {
            string protocol = "opcua"
            string operation = "stream"
            string uri = "opc.tcp://controller.local:4840"
            string topic = "ns=2;s=Light001.Brightness"
            string unit = "percent"
            double minValue = 0.0
            double maxValue = 1.0
            int refreshInterval = 2000
        }
    }
)
```

## Backward Compatibility

The extension maintains backward compatibility with the legacy format using direct keys in `customData`:

```usd
# Legacy format (still supported)
double temperature = 0.0 (
    customData = {
        string binding_protocol = "mqtt"
        string binding_operation = "stream"
        string binding_uri = "mqtt://localhost:1883"
        string binding_topic = "sensors/temperature"
        string binding_jsonPath = "$.data.temperature"
    }
)
```

## Extension Integration

This schema is designed to work with the `alash.bindingsapi` extension, which:

1. Automatically discovers USD files with binding configurations
2. Parses the binding metadata using the schema
3. Establishes connections to external data sources
4. Updates USD attribute values in real-time
5. Provides a monitoring UI in Omniverse

## Best Practices

1. **Use descriptive topics**: Make MQTT topics and REST endpoints descriptive and hierarchical
2. **Set appropriate refresh intervals**: Balance real-time updates with system performance
3. **Include units and descriptions**: Make bindings self-documenting
4. **Set validation ranges**: Use `minValue` and `maxValue` for data quality
5. **Enable/disable as needed**: Use the `enabled` flag to temporarily disable bindings
6. **Use authentication profiles**: Don't store credentials directly in USD files

## Files in this Extension

- **`IoTBindingAPI.usda`**: The main schema definition
- **`IoTBindingAPI_Examples.usda`**: Comprehensive usage examples
- **`AirConditioners_Test.usda`**: Simple MQTT temperature example
- **`MultiSensor_Test.usda`**: Multi-sensor example with different data types
- **`schema/plugInfo.json`**: USD plugin registration for the schema

This schema provides a foundation for connecting the digital twin capabilities of USD with real-world IoT data, enabling dynamic, data-driven 3D scenes in Omniverse.
