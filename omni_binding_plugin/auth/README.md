# Authentication Configuration for USD Binding Protocol Extension

This directory contains authentication profiles that can be referenced by USD binding metadata.

## Structure

```
auth/
├── profiles.json           # Main auth profile registry
├── oauth2/                 # OAuth2 tokens and configs
│   ├── weather-api.json
│   ├── azure-fabric.json
│   └── building-mgmt.json
├── apikeys/                # API key configurations
│   ├── weather-service.json
│   └── iot-platform.json
├── certificates/           # mTLS certificates
│   ├── mqtt-broker/
│   │   ├── client-cert.pem
│   │   ├── client-key.pem
│   │   └── ca-cert.pem
│   └── production/
└── sql/                    # Database connection strings
    ├── fabric-warehouse.json
    └── timeseries-db.json
```

## Usage in USD

Reference auth profiles in your USD binding metadata:

```usd
# Weather API with OAuth2
double temperature = 0.0 (
    custom token binding:protocol = "rest"
    custom string binding:uri = "https://api.weather.com/v1/current"
    custom token binding:authMethod = "oauth2"
    custom string binding:authProfile = "weather-api-prod"
)

# MQTT with client certificates
double sensorValue = 0.0 (
    custom token binding:protocol = "mqtt"
    custom string binding:uri = "mqtts://iot.company.com:8883"
    custom token binding:authMethod = "mtls"
    custom string binding:authProfile = "mqtt-production"
)
```

## Security Notes

- Store sensitive credentials outside version control
- Use environment variables for production deployments
- Rotate tokens and certificates regularly
- Implement proper access controls on auth files
