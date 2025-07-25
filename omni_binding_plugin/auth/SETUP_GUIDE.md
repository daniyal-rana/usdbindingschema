# Authentication Setup Guide

## Setting Up Weather API Authentication

For the weather API example, here's how you structure the auth files:

### 1. Weather API with OAuth2

**File**: `auth/oauth2/weather-api.json`
```json
{
  "auth_type": "oauth2",
  "client_id": "${WEATHER_API_CLIENT_ID}",
  "client_secret": "${WEATHER_API_CLIENT_SECRET}",
  "token_endpoint": "https://auth.weatherapi.com/oauth/token",
  "scope": "weather.read forecast.read",
  "grant_type": "client_credentials"
}
```

**Environment Variables** (set in system environment or .env file):
```bash
WEATHER_API_CLIENT_ID=your_actual_client_id
WEATHER_API_CLIENT_SECRET=your_actual_client_secret
```

**USD Usage**:
```usd
double temperature = 0.0 (
    custom token binding:protocol = "rest"
    custom string binding:uri = "https://api.weather.com/v1/current"
    custom token binding:authMethod = "oauth2"
    custom string binding:authProfile = "weather-api-prod"
)
```

### 2. Weather API with API Key

**File**: `auth/apikeys/weather-service.json`
```json
{
  "auth_type": "apikey",
  "api_key": "${WEATHER_SERVICE_API_KEY}",
  "key_location": "header",
  "key_name": "X-API-Key"
}
```

**Environment Variables**:
```bash
WEATHER_SERVICE_API_KEY=your_actual_api_key
```

**USD Usage**:
```usd
string weatherCondition = "clear" (
    custom token binding:protocol = "rest"
    custom string binding:uri = "https://api.weather.com/v1/current"
    custom token binding:authMethod = "apikey"
    custom string binding:authProfile = "weather-api-dev"
)
```

### 3. Register Profiles

**File**: `auth/profiles.json`
```json
{
  "profiles": {
    "weather-api-prod": {
      "type": "oauth2",
      "description": "Production Weather API OAuth2 credentials",
      "config_file": "oauth2/weather-api.json"
    },
    "weather-api-dev": {
      "type": "apikey", 
      "description": "Development Weather API key",
      "config_file": "apikeys/weather-service.json"
    }
  }
}
```

## Real-World Weather API Examples

### OpenWeatherMap
```json
{
  "auth_type": "apikey",
  "api_key": "${OPENWEATHER_API_KEY}",
  "key_location": "query_param",
  "key_name": "appid"
}
```

### WeatherAPI.com
```json
{
  "auth_type": "apikey",
  "api_key": "${WEATHERAPI_KEY}",
  "key_location": "query_param", 
  "key_name": "key"
}
```

### AccuWeather (with OAuth2)
```json
{
  "auth_type": "oauth2",
  "client_id": "${ACCUWEATHER_CLIENT_ID}",
  "client_secret": "${ACCUWEATHER_CLIENT_SECRET}",
  "token_endpoint": "https://api.accuweather.com/oauth/token",
  "scope": "weather"
}
```

## Security Best Practices

1. **Never commit credentials to version control**
2. **Use environment variables for all secrets**
3. **Rotate API keys and tokens regularly**
4. **Use least-privilege scopes**
5. **Monitor API usage and rate limits**
6. **Use production vs development profiles**

## Testing Your Setup

1. Copy `.env.template` to `.env`
2. Fill in your actual credentials
3. Load the example USD file: `examples/SmartBuilding_WeatherAPI.usda`
4. Check the USD Binding Protocols window for connection status
5. Verify data is being retrieved from your weather API
