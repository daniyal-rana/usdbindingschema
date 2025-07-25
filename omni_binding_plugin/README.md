# USD Binding Protocol Extension for NVIDIA Omniverse

This extension provides support for retrieving values from various protocols defined in the USD BindingAPI schema. It allows USD attributes to be bound to external data sources like MQTT brokers, REST APIs, SQL databases, gRPC services, WebSocket connections, and files.

## Features

- **Multi-Protocol Support**: MQTT, REST/HTTP, SQL, gRPC, WebSocket, and File protocols
- **Streaming and Polling**: Real-time data streaming for MQTT/WebSocket, polling for REST/SQL/File
- **Authentication**: Support for OAuth2, API keys, and mTLS authentication methods
- **Context Variables**: Hierarchical variable substitution using `${variable}` syntax
- **Visual Management**: UI window for monitoring and controlling bindings
- **Automatic Discovery**: Scans USD stages for BindingAPI metadata and auto-connects

## Installation

1. Copy the `omni_binding_plugin` folder to your Omniverse extensions directory
2. Install optional dependencies based on which protocols you need:

```bash
# For MQTT support
pip install aiomqtt>=2.0.0

# For HTTP/REST support  
pip install aiohttp>=3.8.0

# For SQL support
pip install aioodbc>=0.4.0

# For gRPC support
pip install grpcio>=1.50.0

# For WebSocket support
pip install websockets>=11.0.0
```

3. Enable the extension in Omniverse Extension Manager

## Usage

### Basic USD Schema Usage

Apply the BindingAPI to a prim and set binding metadata on attributes:

```usd
def Cube "MyDevice" (
    prepend apiSchemas = ["BindingAPI"]
)
{
    # Context variables for substitution
    dictionary binding:context = {
        "deviceId": "sensor123",
        "apiBase": "https://api.example.com"
    }
    
    # Temperature from MQTT
    double temperature = 0.0 (
        custom token binding:protocol = "mqtt"
        custom token binding:operation = "stream"
        custom string binding:uri = "mqtts://broker.example.com:8883"
        custom string binding:topic = "/devices/${deviceId}/temperature"
        custom token binding:authMethod = "mtls"
        custom string binding:authProfile = "production-certs"
    )
    
    # Device info from REST API
    string deviceName = "" (
        custom token binding:protocol = "rest"
        custom token binding:operation = "read"
        custom string binding:uri = "${apiBase}/devices/${deviceId}"
        custom token binding:method = "GET"
        custom string binding:jsonPath = "$.name"
        custom token binding:authMethod = "oauth2"
        custom string binding:authProfile = "api-token"
    )
}
```

### Protocol-Specific Examples

#### MQTT Streaming
```usd
double sensorValue = 0.0 (
    custom token binding:protocol = "mqtt"
    custom token binding:operation = "stream"
    custom string binding:uri = "mqtts://broker.hivemq.com:8883"
    custom string binding:topic = "/sensors/temperature"
)
```

#### REST API with JSONPath
```usd
string status = "" (
    custom token binding:protocol = "rest"
    custom token binding:operation = "read"
    custom string binding:uri = "https://api.example.com/device/status"
    custom token binding:method = "GET"
    custom string binding:jsonPath = "$.status"
    custom string binding:refreshPolicy = "interval:10s"
)
```

#### SQL Database Query
```usd
int recordCount = 0 (
    custom token binding:protocol = "sql"
    custom token binding:operation = "read"
    custom string binding:uri = "sql://server.example.com/database"
    custom string binding:query = "SELECT COUNT(*) FROM sensor_data WHERE device_id = 'device123'"
    custom string binding:refreshPolicy = "interval:300s"
)
```

#### File Monitoring
```usd
double configValue = 0.0 (
    custom token binding:protocol = "file"
    custom token binding:operation = "stream"
    custom string binding:uri = "file:///path/to/config.json"
    custom string binding:jsonPath = "$.threshold"
    custom string binding:refreshPolicy = "interval:5s"
)
```

### Authentication Configuration

Set auth defaults at the prim level:

```usd
def Scope "MySystem" (
    prepend apiSchemas = ["BindingAPI"]
)
{
    dictionary binding:authDefaults:mqtt = {
        "authMethod": "mtls",
        "authProfile": "mqtt-production-certs"
    }
    
    dictionary binding:authDefaults:rest = {
        "authMethod": "oauth2", 
        "authProfile": "api-bearer-token"
    }
}
```

## UI Interface

The extension provides a "USD Binding Protocols" window that shows:

- **Active Bindings**: List of all discovered bindings with status indicators
- **Real-time Values**: Current values retrieved from external sources
- **Connection Status**: Visual indicators for connection state
- **Manual Controls**: Start/stop streaming, trigger reads, view details

Access via: Window → Extensions → USD Binding Protocols

## Supported Operations

- **read**: One-time data retrieval
- **stream**: Continuous data streaming (MQTT, WebSocket) or polling (REST, SQL, File)
- **write**: Send data to external systems (where supported)
- **connect/disconnect**: Manual connection control

## Protocol Support Matrix

| Protocol  | Read | Stream | Write | Auth Support |
|-----------|------|--------|-------|--------------|
| MQTT      | ✓    | ✓      | ✓     | mTLS, OAuth2 |
| REST/HTTP | ✓    | ✓*     | ✓     | OAuth2, API Key |
| SQL       | ✓    | ✓*     | ✓     | OAuth2 |
| gRPC      | ✓**  | ✓*     | ✓**   | mTLS, OAuth2 |
| WebSocket | ✓    | ✓      | ✓     | OAuth2, API Key |
| File      | ✓    | ✓      | ✓     | None |

\* Via polling  
\** Requires service-specific implementation

## Configuration Options

### Refresh Policies
- `onLoad`: Read once when stage loads
- `interval:30s`: Poll every 30 seconds  
- `interval:5m`: Poll every 5 minutes
- `interval:1h`: Poll every hour

### Auth Methods
- `none`: No authentication
- `oauth2`: OAuth2 bearer tokens
- `apikey`: API key authentication
- `mtls`: Mutual TLS certificates

## Architecture

The extension consists of several key components:

- **BindingParser**: Extracts and validates binding metadata from USD
- **ProtocolManager**: Manages connections and data flow
- **Protocol Clients**: Individual clients for each protocol type
- **UI Components**: Visual management interface

## Limitations

- gRPC support requires service-specific stub generation
- Authentication profiles are symbolic - actual credential management must be implemented separately
- Some protocols require additional Python packages to be installed
- WebSocket topic support depends on server implementation

## Development

To extend support for additional protocols:

1. Inherit from `BaseProtocolClient`
2. Implement required methods: `connect()`, `disconnect()`, `read()`
3. Optionally implement `write()` and `start_stream()`
4. Register in `ProtocolManager._client_classes`

## Troubleshooting

**No bindings detected**: Ensure BindingAPI is applied to prims and binding metadata is set on attributes

**Connection failures**: Check network connectivity, authentication credentials, and protocol-specific URIs

**Missing protocol support**: Install required Python packages from requirements.txt

**Authentication errors**: Verify auth profiles and methods are correctly configured

## License

This extension is provided as-is for demonstration and development purposes.
