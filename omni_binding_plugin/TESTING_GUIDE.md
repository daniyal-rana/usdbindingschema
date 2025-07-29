# USD Binding System Testing Guide

This guide walks you through testing the complete USD binding system with Cloud Events MQTT integration.

## 🎯 Overview

The USD Binding System allows 3D scenes to receive real-time data from external systems. This test demonstrates:
- Publishing Cloud Events to MQTT broker
- USD file configured to subscribe to the topic  
- Omniverse plugin extracting temperature data and updating scene attributes

## 🚀 Complete Testing Workflow

### Step 1: Test MQTT Publishing

Navigate to the plugin directory and run the test publisher:

```powershell
cd omni_binding_plugin
python test_setup.py
```

**Expected Output:**
```
🔬 Testing USD Binding Configuration
==================================================
Broker: broker.hivemq.com:1883
Topic: cloudevents/temperature
JSONPath: $.data.temperature
==================================================
🔌 Connecting to broker.hivemq.com...
✅ Published: Temperature 20.0°C
   JSONPath $.data.temperature will extract: 20.0
✅ Published: Temperature 22.5°C
   JSONPath $.data.temperature will extract: 22.5
✅ Published: Temperature 25.0°C
   JSONPath $.data.temperature will extract: 25.0
✅ Published: Temperature 27.5°C
   JSONPath $.data.temperature will extract: 27.5
✅ Published: Temperature 30.0°C
   JSONPath $.data.temperature will extract: 30.0

🎉 Test complete!
```

This publishes 5 temperature values (20.0°C, 22.5°C, 25.0°C, 27.5°C, 30.0°C) to the `cloudevents/temperature` topic in Cloud Events format.

### Step 2: Verify Messages with MQTT Subscriber

In **another terminal**, subscribe to verify the messages:

```powershell
mosquitto_sub -h broker.hivemq.com -p 1883 -t "cloudevents/temperature" -v
```

**Expected Messages:**
```json
cloudevents/temperature {
  "specversion": "1.0",
  "id": "abc123-def456-789",
  "source": "urn:hvac:device:aircon3245",
  "type": "com.example.hvac.temperature.reading",
  "time": "2025-07-29T15:30:00Z",
  "datacontenttype": "application/json",
  "data": {
    "temperature": 25.0,
    "unit": "celsius",
    "status": "normal"
  }
}
```

### Step 3: Install Omniverse Extension

Install the USD Binding Protocol extension:

```powershell
python install.ps1
```

**Expected Output:**
```
Installing USD Binding Protocol Extension...
✅ Extension installed successfully
📋 Extension path: ~/.local/share/ov/pkg/create-2023.2.0/exts/omni.binding.protocol
```

### Step 4: Test in Omniverse

#### 4.1 Open Omniverse
Launch any Omniverse application:
- **USD Composer** (recommended)
- **Create** 
- **Code**

#### 4.2 Load Your USD File
1. **File** → **Open**
2. Navigate to: `AirConditioners_Test.usda`
3. Click **Open**

#### 4.3 Enable the Extension
1. **Window** → **Extensions**
2. Search: `"USD Binding Protocol"`
3. **Enable** the extension
4. ✅ You should see: `"USD Binding Protocol extension enabled"`

#### 4.4 Watch the Magic! 🎉
The `temperature` attribute should now update in real-time as you publish MQTT data!

### Step 5: Monitor the Binding System

#### 5.1 Property Panel Monitoring
1. **Select** `HelloWorldAirCon/AirConditioner_001` in stage hierarchy
2. **Property Panel** → Look for `temperature` attribute
3. **Watch** the value change from `0.0` to live values like `25.3`

#### 5.2 Console Output
Look for extension logs in the Omniverse console:
```
[omni.binding.protocol] Starting USD Binding Protocol Extension
[MQTTClient] Connected to broker.hivemq.com:1883  
[MQTTClient] Subscribed to topic: cloudevents/temperature
[ProtocolManager] Updated HelloWorldAirCon/AirConditioner_001.temperature = 20.0
[ProtocolManager] Updated HelloWorldAirCon/AirConditioner_001.temperature = 22.5
[ProtocolManager] Updated HelloWorldAirCon/AirConditioner_001.temperature = 25.0
```

#### 5.3 Attribute Timeline
1. **Window** → **Timeline** 
2. **Look for** temperature values updating over time
3. **Scrub timeline** to see historical values

## 🧪 Real-Time Testing

### Manual Testing
Publish individual Cloud Events manually:

```powershell
# Publish hot temperature
mosquitto_pub -h broker.hivemq.com -p 1883 -t "cloudevents/temperature" -m '{"specversion":"1.0","id":"test-hot","source":"urn:hvac:device:aircon3245","type":"com.example.hvac.temperature.reading","time":"2025-07-29T15:30:00Z","datacontenttype":"application/json","data":{"temperature":35.7,"unit":"celsius","status":"warning"}}'

# Publish cold temperature  
mosquitto_pub -h broker.hivemq.com -p 1883 -t "cloudevents/temperature" -m '{"specversion":"1.0","id":"test-cold","source":"urn:hvac:device:aircon3245","type":"com.example.hvac.temperature.reading","time":"2025-07-29T15:30:00Z","datacontenttype":"application/json","data":{"temperature":15.2,"unit":"celsius","status":"normal"}}'
```

### Expected USD Updates
When you publish this Cloud Event:
```json
{"data": {"temperature": 25.3}}
```

Your USD attribute should update to:
```usd
double temperature = 25.3  # Updates automatically!
```

## 🔍 Troubleshooting

### Extension Not Working?
1. **Check Extension Status**: Window → Extensions → Verify "USD Binding Protocol" is enabled
2. **Restart Omniverse**: Sometimes extensions need a restart to activate
3. **Check Console**: Look for error messages in Omniverse console

### No MQTT Connection?
1. **Test Network**: `ping broker.hivemq.com` 
2. **Check Firewall**: Ensure port 1883 is open
3. **Verify Topic**: Make sure you're using `cloudevents/temperature`

### USD Attributes Not Updating?
1. **Check USD File**: Verify `AirConditioners_Test.usda` has correct broker and topic
2. **Check JSONPath**: Ensure `$.data.temperature` matches your Cloud Event structure
3. **Check Selection**: Make sure `AirConditioner_001` is selected in stage

### Console Errors?
```
[ERROR] Failed to connect to MQTT broker
```
**Solution**: Check network connectivity and broker address

```
[ERROR] JSONPath extraction failed  
```
**Solution**: Verify your Cloud Event has `data.temperature` field

## 🎉 Success Indicators

✅ **MQTT Test**: `python test_setup.py` publishes 5 temperatures successfully  
✅ **Message Verification**: `mosquitto_sub` shows Cloud Events messages  
✅ **Extension Install**: `python install.ps1` completes without errors  
✅ **Omniverse Loading**: `AirConditioners_Test.usda` opens without errors  
✅ **Extension Enabled**: "USD Binding Protocol" shows as enabled  
✅ **Live Updates**: Temperature attribute changes in Property Panel  
✅ **Console Logs**: MQTT connection and update messages appear  

## 🚀 Next Steps After Successful Testing

1. **Add Authentication**: Configure real certificates in `auth/` directory
2. **Connect Real Systems**: Replace test endpoints with actual IoT systems  
3. **Scale Up**: Add more devices and attributes to your USD file
4. **Visualize**: Create materials that change color based on temperature
5. **Automate**: Set up refresh policies and automated testing
6. **Production**: Deploy to real digital twin scenarios

## 📋 Cloud Events Benefits Demonstrated

- ✅ **Standardized Format**: Industry-standard event messaging
- ✅ **Rich Metadata**: Event tracing with ID, timestamp, source  
- ✅ **Interoperability**: Works with cloud-native event systems
- ✅ **Schema Evolution**: Extensible format for future enhancements
- ✅ **Real-time Streaming**: Live data updates in 3D scenes

Your USD Binding System is now successfully connecting Cloud Events to 3D digital twins! 🎯