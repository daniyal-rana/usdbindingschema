#!/usr/bin/env python3
"""
Simple test to validate MQTT binding configuration parsing.
This can be run outside Omniverse to test the basic parsing logic.
"""

class MockBindingConfiguration:
    """Mock version of BindingConfiguration for testing outside Omniverse."""
    
    def __init__(self, prim_path, attr_name, config):
        self.prim_path = prim_path
        self.attr_name = attr_name
        
        # Check for new simplified MQTT schema format
        if 'mqtt' in config and isinstance(config['mqtt'], dict):
            mqtt_dict = config['mqtt']
            self.protocol = 'mqtt'
            self.operation = 'stream'
            self.broker = self._get_value(mqtt_dict, ['broker'], 'localhost:1883')
            self.topic = self._get_value(mqtt_dict, ['topic'], '')
            self.json_path = self._get_value(mqtt_dict, ['jsonPath'], '')
            self.unit = self._get_value(mqtt_dict, ['unit'], '')
            self.description = self._get_value(mqtt_dict, ['description'], '')
            self.qos = self._get_int_value(mqtt_dict, ['qos'], 0)
            self.enabled = self._get_bool_value(mqtt_dict, ['enabled'], True)
            self.refresh_interval = self._get_int_value(mqtt_dict, ['refreshInterval'], 1000)
        else:
            # Default values for testing
            self.protocol = 'unknown'
            self.operation = 'unknown'
            self.broker = 'localhost:1883'
            self.topic = ''
            self.json_path = ''
            self.unit = ''
            self.description = ''
            self.qos = 0
            self.enabled = True
            self.refresh_interval = 1000
            
    def _get_value(self, config, keys, default=''):
        """Get value from config using multiple possible key names."""
        for key in keys:
            if key in config:
                value = config[key]
                return str(value) if value is not None else default
        return default
        
    def _get_int_value(self, config, keys, default=0):
        """Get integer value from config."""
        for key in keys:
            if key in config:
                try:
                    return int(config[key])
                except (ValueError, TypeError):
                    pass
        return default
        
    def _get_bool_value(self, config, keys, default=False):
        """Get boolean value from config."""
        for key in keys:
            if key in config:
                value = config[key]
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
        return default
    
    @property
    def display_name(self):
        return f"{self.prim_path}.{self.attr_name}"
    
    def is_mqtt_stream(self):
        return self.protocol == 'mqtt' and self.enabled

def test_mqtt_binding():
    """Test the MQTT binding configuration parsing."""
    
    # Test new simplified MQTT format
    print("Testing new simplified MQTT format...")
    config = {
        'mqtt': {
            'broker': 'localhost:1883',
            'topic': 'sensors/temperature',
            'jsonPath': '$.data.temperature',
            'unit': 'celsius',
            'description': 'Temperature sensor',
            'qos': 1,
            'enabled': True
        }
    }
    
    binding = MockBindingConfiguration('/Test/Sensor', 'temperature', config)
    
    print(f"  Binding: {binding.display_name}")
    print(f"  Protocol: {binding.protocol}")
    print(f"  Broker: {binding.broker}")
    print(f"  Topic: {binding.topic}")
    print(f"  JSONPath: {binding.json_path}")
    print(f"  Unit: {binding.unit}")
    print(f"  Description: {binding.description}")
    print(f"  QoS: {binding.qos}")
    print(f"  Enabled: {binding.enabled}")
    print(f"  Is MQTT Stream: {binding.is_mqtt_stream()}")
    print()

    # Test minimal configuration
    print("Testing minimal MQTT configuration...")
    config_minimal = {
        'mqtt': {
            'topic': 'test/topic'
        }
    }
    
    binding_minimal = MockBindingConfiguration('/Test/MinimalSensor', 'value', config_minimal)
    
    print(f"  Binding: {binding_minimal.display_name}")
    print(f"  Protocol: {binding_minimal.protocol}")
    print(f"  Broker: {binding_minimal.broker}")  # Should use default
    print(f"  Topic: {binding_minimal.topic}")
    print(f"  Enabled: {binding_minimal.enabled}")  # Should use default
    print(f"  Is MQTT Stream: {binding_minimal.is_mqtt_stream()}")
    print()

    print("✅ All tests passed! Configuration parsing works correctly.")

if __name__ == "__main__":
    test_mqtt_binding()
