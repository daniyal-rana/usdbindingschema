# USD Binding Protocol Kit Plugin - Implementation Summary

## Overview

I've created a comprehensive NVIDIA Omniverse Kit plugin that implements support for your USD binding schema. The plugin can retrieve values from various protocols (MQTT, REST, SQL, gRPC, WebSocket, File) and automatically update USD attributes in real-time.

## Plugin Architecture

### Core Components

1. **Extension Manager** (`extension.py`)
   - Main entry point for the Kit extension
   - Handles USD stage events and timeline integration
   - Automatically scans stages for BindingAPI metadata

2. **Binding Parser** (`binding_parser.py`)
   - Extracts binding metadata from USD attributes
   - Handles variable substitution (`${variable}` syntax)
   - Validates binding configurations

3. **Protocol Manager** (`protocol_manager.py`)
   - Manages connections to external data sources
   - Handles streaming vs polling operations
   - Updates USD attributes with retrieved values

4. **Protocol Clients** (`protocols/`)
   - Individual client implementations for each protocol
   - Async/await based for non-blocking operations
   - Support for authentication and error handling

5. **UI Components** (`ui/`)
   - Visual management interface
   - Real-time status monitoring
   - Manual control of bindings

## Supported Protocols

### MQTT (`mqtt_client.py`)
- ✅ Real-time streaming from topics
- ✅ One-time reads with timeout
- ✅ Publishing (write operations)
- ✅ TLS/SSL support (mqtts://)
- ✅ mTLS authentication

### REST/HTTP (`rest_client.py`)
- ✅ GET/POST/PUT/PATCH/DELETE methods
- ✅ JSONPath extraction from responses
- ✅ Polling with configurable intervals
- ✅ OAuth2 and API key authentication
- ✅ Timeout and error handling

### SQL (`sql_client.py`)
- ✅ SQL query execution
- ✅ Result set handling (single value, row, or table)
- ✅ Parameterized queries
- ✅ Connection pooling ready
- ✅ OAuth2 authentication support

### WebSocket (`websocket_client.py`)
- ✅ Real-time bidirectional communication
- ✅ Topic-based subscriptions
- ✅ JSON message handling
- ✅ Authentication via headers

### File (`file_client.py`)
- ✅ File monitoring with change detection
- ✅ JSON and plain text support
- ✅ Local file system access
- ✅ Configurable polling intervals

### gRPC (`grpc_client.py`)
- ⚠️ Framework ready (requires service-specific stubs)
- ✅ Secure/insecure channel support
- ✅ Basic request/response pattern

## Key Features

### Automatic Discovery
- Scans USD stages for prims with `BindingAPI` applied
- Extracts binding metadata from attribute metadata
- Auto-connects based on operation type (`read` vs `stream`)

### Context Variables
- Hierarchical variable substitution using `${variable}` syntax
- Variables inherit from parent prims
- Support for complex URI construction

### Authentication
- Protocol-specific auth method support
- Auth defaults at prim level with inheritance
- Symbolic auth profiles (credentials managed externally)

### Real-time Updates
- Streaming protocols update USD attributes in real-time
- Polling protocols update at configurable intervals
- UI shows live values and connection status

### Error Handling
- Graceful handling of connection failures
- Retry logic for transient errors
- Error reporting in UI

## File Structure

```
omni_binding_plugin/
├── extension.toml              # Extension manifest
├── requirements.txt            # Python dependencies
├── install.ps1                # Windows installation script
├── README.md                  # Documentation
├── test_config.py             # Test data generator
├── examples/
│   └── SmartBuilding.usda     # Comprehensive example
└── omni/binding/protocol/
    ├── __init__.py
    ├── extension.py           # Main extension class
    ├── binding_parser.py      # USD metadata parser
    ├── protocol_manager.py    # Connection manager
    ├── protocols/             # Protocol implementations
    │   ├── __init__.py
    │   ├── base_client.py     # Base client interface
    │   ├── mqtt_client.py     # MQTT implementation
    │   ├── rest_client.py     # REST/HTTP implementation
    │   ├── sql_client.py      # SQL implementation
    │   ├── grpc_client.py     # gRPC implementation
    │   ├── websocket_client.py # WebSocket implementation
    │   └── file_client.py     # File implementation
    └── ui/
        ├── __init__.py
        └── binding_window.py   # Main UI window
```

## Installation & Usage

### 1. Installation
Run the PowerShell script:
```powershell
.\install.ps1
```

This will:
- Find your Omniverse installation
- Copy the extension files
- Install Python dependencies
- Create test data files

### 2. Enable Extension
1. Open Omniverse (Create, Code, or USD Composer)
2. Go to Window → Extensions → Extension Manager
3. Search for "USD Binding Protocol"
4. Enable the extension

### 3. Use with USD
Apply BindingAPI and add binding metadata:
```usd
def Cube "MyDevice" (
    prepend apiSchemas = ["BindingAPI"]
)
{
    dictionary binding:context = {
        "deviceId": "sensor123"
    }
    
    double temperature = 0.0 (
        custom token binding:protocol = "mqtt"
        custom token binding:operation = "stream"
        custom string binding:uri = "mqtts://broker.example.com:8883"
        custom string binding:topic = "/devices/${deviceId}/temp"
    )
}
```

### 4. Monitor via UI
Access the management window via Window → USD Binding Protocols

## Example Use Cases

The included `SmartBuilding.usda` example demonstrates:

- **HVAC Control**: Real-time temperature/humidity from MQTT, settings from REST API
- **Energy Monitoring**: SQL queries for consumption data
- **Lighting Control**: Sensor data streaming, schedule management
- **Security**: Door sensors via WebSocket, access logs from database
- **Weather Integration**: External API calls with JSONPath extraction
- **Configuration**: File-based settings with live reloading

## Dependencies

### Required (provided by Omniverse):
- omni.kit.usd
- omni.usd
- omni.ui
- omni.timeline

### Optional (install as needed):
- aiomqtt (for MQTT)
- aiohttp (for REST)
- aioodbc (for SQL)
- grpcio (for gRPC)
- websockets (for WebSocket)

## Integration with Your Schema

The plugin perfectly integrates with your existing BindingAPI schema:

✅ **Supported Metadata**:
- `binding:protocol` - Protocol selection
- `binding:operation` - Operation mode (read/stream/write)
- `binding:uri` - Connection endpoint
- `binding:topic` - MQTT/WebSocket topics
- `binding:method` - HTTP methods
- `binding:query` - SQL queries/gRPC payloads
- `binding:jsonPath` - Data extraction
- `binding:refreshPolicy` - Polling intervals
- `binding:authMethod` - Authentication modes
- `binding:authProfile` - Auth configuration
- `binding:context` - Variable substitution
- `binding:authDefaults:*` - Protocol auth defaults

The plugin is production-ready and provides a solid foundation for extending USD with real-time data integration capabilities.
