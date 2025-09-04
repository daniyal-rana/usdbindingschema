# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import omni.ext
import omni.ui as ui
import omni.usd
import asyncio
import json
import threading
import time
import re
import sys
import os
from pxr import Usd, UsdGeom
import omni.kit.pipapi

# Install required packages at runtime
def install_pip_packages():
    """Install required pip packages using omni.kit.pipapi"""
    # Install paho-mqtt (essential for MQTT functionality)
    try:
        print("[alash.bindingsapi] Installing paho-mqtt...")
        omni.kit.pipapi.install("paho-mqtt")
        print("[alash.bindingsapi] paho-mqtt installed successfully")
    except Exception as e:
        print(f"[alash.bindingsapi] Error installing paho-mqtt: {e}")
    
    # Install jsonpath-ng (optional for advanced JSONPath support)
    try:
        print("[alash.bindingsapi] Installing jsonpath-ng...")
        omni.kit.pipapi.install("jsonpath-ng")
        print("[alash.bindingsapi] jsonpath-ng installed successfully")
    except Exception as e:
        print(f"[alash.bindingsapi] Error installing jsonpath-ng: {e}")
        print("[alash.bindingsapi] jsonpath-ng is optional - basic JSONPath will still work")
    
    # Install requests for HTTP bindings
    try:
        print("[alash.bindingsapi] Installing requests...")
        omni.kit.pipapi.install("requests")
        print("[alash.bindingsapi] requests installed successfully")
    except Exception as e:
        print(f"[alash.bindingsapi] Error installing requests: {e}")
    
    # Install tomli for TOML parsing
    try:
        print("[alash.bindingsapi] Installing tomli...")
        omni.kit.pipapi.install("tomli")
        print("[alash.bindingsapi] tomli installed successfully")
    except Exception as e:
        print(f"[alash.bindingsapi] Error installing tomli: {e}")
        print("[alash.bindingsapi] TOML config files may not work without tomli")

# Try to install packages (but don't fail if it doesn't work)
try:
    install_pip_packages()
except Exception as e:
    print(f"[alash.bindingsapi] Package installation failed: {e}")

# Import packages after installation
mqtt = None
jsonpath_parse = None
requests = None

try:
    import paho.mqtt.client as mqtt
    print("[alash.bindingsapi] ✓ paho-mqtt imported successfully")
except ImportError as e:
    mqtt = None
    print(f"[alash.bindingsapi] ✗ paho-mqtt not available: {e}")

try:
    import jsonpath_ng.parse as jsonpath_parse
    print("[alash.bindingsapi] ✓ jsonpath-ng imported successfully")
except ImportError as e:
    jsonpath_parse = None
    print(f"[alash.bindingsapi] ✗ jsonpath-ng not available: {e}")
    print("[alash.bindingsapi] Note: Extension will work with basic JSONPath support")

try:
    import requests
    print("[alash.bindingsapi] ✓ requests imported successfully")
except ImportError as e:
    requests = None
    print(f"[alash.bindingsapi] ✗ requests not available: {e}")

# Import our config manager
from .config_manager import ConfigManager, EventBindingConfiguration


# Functions and vars are available to other extensions as usual in python:
# `alash.bindingsapi.some_public_function(x)`
def some_public_function(x: int):
    """This is a public function that can be called from other extensions."""
    print(f"[alash.bindingsapi] some_public_function was called with {x}")
    return x ** x


class BindingConfiguration:
    """Represents a simple MQTT binding configuration from USD metadata."""
    
    def __init__(self, prim_path, attr_name, config):
        self.prim_path = prim_path
        self.attr_name = attr_name
        
        # USD references for live updates
        self.usd_stage = None
        self.usd_attribute = None
        
        # Check for new simplified MQTT schema format
        if 'mqtt' in config and isinstance(config['mqtt'], dict):
            mqtt_dict = config['mqtt']
            self.protocol = 'mqtt'
            self.operation = 'stream'
            self.broker = self._get_value(mqtt_dict, ['broker'], 'localhost:1883')
            self.topic = self._get_value(mqtt_dict, ['topic'], '')
            self.json_path = self._get_value(mqtt_dict, ['jsonPath'], '')
            self.description = self._get_value(mqtt_dict, ['description'], '')
            self.qos = self._get_int_value(mqtt_dict, ['qos'], 0)
            self.enabled = self._get_bool_value(mqtt_dict, ['enabled'], True)
            self.refresh_interval = self._get_int_value(mqtt_dict, ['refreshInterval'], 1000)
        # Check for legacy IoT binding format  
        elif 'binding' in config and isinstance(config['binding'], dict):
            binding_dict = config['binding']
            self.protocol = self._get_value(binding_dict, ['protocol'], '')
            self.operation = self._get_value(binding_dict, ['operation'], '')
            self.broker = self._parse_mqtt_uri(self._get_value(binding_dict, ['uri'], ''))
            self.topic = self._get_value(binding_dict, ['topic'], '')
            self.json_path = self._get_value(binding_dict, ['jsonPath'], '')
            self.description = self._get_value(binding_dict, ['description'], '')
            self.qos = self._get_int_value(binding_dict, ['qos'], 0)
            self.enabled = self._get_bool_value(binding_dict, ['enabled'], True)
            self.refresh_interval = self._get_int_value(binding_dict, ['refreshInterval'], 5000)
        else:
            # Fallback to original legacy format for backward compatibility
            self.protocol = self._get_value(config, ['binding_protocol', 'bindingProtocol', 'protocol'])
            self.operation = self._get_value(config, ['binding_operation', 'bindingOperation', 'operation'])
            self.broker = self._parse_mqtt_uri(self._get_value(config, ['binding_uri', 'bindingUri', 'uri']))
            self.topic = self._get_value(config, ['binding_topic', 'bindingTopic', 'topic'])
            self.json_path = self._get_value(config, ['binding_jsonPath', 'bindingJsonPath', 'jsonPath'])
            self.description = ''
            self.qos = 0
            self.enabled = True
            self.refresh_interval = 5000
    
    def set_usd_references(self, stage, attribute):
        """Store USD stage and attribute references for live updates."""
        self.usd_stage = stage
        self.usd_attribute = attribute
        
    def update_usd_value(self, value):
        """Update the USD attribute with new value."""
        if self.usd_attribute and self.usd_stage:
            try:
                # Convert value to appropriate type based on attribute type
                attr_type = self.usd_attribute.GetTypeName()
                
                if attr_type.type.pythonClass == float:
                    converted_value = float(value)
                elif attr_type.type.pythonClass == int:
                    converted_value = int(float(value))  # Convert through float to handle decimals
                elif attr_type.type.pythonClass == str:
                    converted_value = str(value)
                else:
                    converted_value = value
                
                # Set the value at the default time code (current frame)
                from pxr import Usd
                self.usd_attribute.Set(converted_value, Usd.TimeCode.Default())
                
                print(f"[alash.bindingsapi] Updated USD attribute {self.display_name} = {converted_value}")
                return True
                
            except Exception as e:
                print(f"[alash.bindingsapi] Error updating USD attribute {self.display_name}: {e}")
                return False
        return False
            
    def _parse_mqtt_uri(self, uri):
        """Extract broker address from MQTT URI."""
        if not uri:
            return 'localhost:1883'
        # Handle mqtt://broker:port format
        if uri.startswith('mqtt://'):
            return uri[7:]  # Remove mqtt:// prefix
        return uri
        
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
        
    def is_mqtt_stream(self):
        return self.protocol == 'mqtt' and self.enabled
        
    @property
    def display_name(self):
        return f"{self.prim_path}.{self.attr_name}"
    
    @property 
    def broker_host_port(self):
        """Get broker host and port as tuple."""
        if ':' in self.broker:
            host, port = self.broker.split(':', 1)
            try:
                return host, int(port)
            except ValueError:
                return host, 1883
        return self.broker, 1883


class GenericHTTPPoller:
    """Generic HTTP client to poll REST APIs based on request binding configurations."""
    
    def __init__(self):
        self.bindings = []
        self.values = {}    # binding_id -> current value
        self.last_updates = {}  # binding_id -> timestamp
        self.callbacks = []
        self.polling_threads = {}  # binding_id -> thread
        self.stop_polling = {}     # binding_id -> stop flag
        
    def add_callback(self, callback):
        """Add a callback function to be called when values update."""
        self.callbacks.append(callback)
        
    def add_binding(self, binding_config):
        """Add a request binding configuration to monitor."""
        if not binding_config.is_http_request():
            return False
            
        self.bindings.append(binding_config)
        
        binding_id = binding_config.display_name
        self.values[binding_id] = None
        self.last_updates[binding_id] = "Never"
        self.stop_polling[binding_id] = False
        
        # Start polling thread for this binding
        self._start_polling_thread(binding_config)
        
        return True
        
    def _start_polling_thread(self, binding_config):
        """Start a polling thread for a specific binding."""
        if requests is None:
            print("[alash.bindingsapi] requests library not available for HTTP polling")
            return
            
        def poll_loop():
            binding_id = binding_config.display_name
            poll_interval = binding_config.poll_interval_seconds
            
            print(f"[alash.bindingsapi] Starting HTTP polling for {binding_id} every {poll_interval}s")
            
            while not self.stop_polling.get(binding_id, True):
                try:
                    # Build the full URL
                    base_url = binding_config.get_host()
                    endpoint = binding_config.endpoint_target
                    full_url = f"{base_url}{endpoint}"
                    
                    # Get auth info
                    auth_info = binding_config.get_auth_info()
                    headers = {}
                    auth = None
                    
                    # Set up authentication
                    if auth_info.get('auth_method') == 'api_key' and auth_info.get('api_key'):
                        headers['Authorization'] = f"Bearer {auth_info['api_key']}"
                    elif auth_info.get('username') and auth_info.get('password'):
                        auth = (auth_info['username'], auth_info['password'])
                    
                    # Make the HTTP request
                    timeout = binding_config.connection_config.get('timeout', 30) if binding_config.connection_config else 30
                    
                    print(f"[alash.bindingsapi] Polling {full_url}")
                    response = requests.get(full_url, headers=headers, auth=auth, timeout=timeout)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extract value using filter expression
                        value = self._extract_value(data, binding_config.filter_expression)
                        
                        if value is not None:
                            # Store value for UI updates
                            self.values[binding_id] = value
                            self.last_updates[binding_id] = time.strftime("%H:%M:%S")
                            
                            print(f"[alash.bindingsapi] HTTP Response {binding_id}: {value}")
                            
                            # Update USD attribute
                            binding_config.update_usd_value(value)
                            
                            # Notify callbacks
                            for callback in self.callbacks:
                                try:
                                    callback(binding_id, value, self.last_updates[binding_id])
                                except Exception as e:
                                    print(f"[alash.bindingsapi] Error in HTTP callback: {e}")
                        else:
                            print(f"[alash.bindingsapi] Could not extract value from response using {binding_config.filter_expression}")
                    else:
                        print(f"[alash.bindingsapi] HTTP request failed: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    print(f"[alash.bindingsapi] Error polling {binding_id}: {e}")
                
                # Wait for next poll interval
                time.sleep(poll_interval)
                
        # Start the polling thread
        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()
        self.polling_threads[binding_config.display_name] = thread
        
    def _extract_value(self, data, json_path):
        """Extract value from JSON data using JSONPath."""
        if not json_path:
            return data
            
        try:
            # Try advanced JSONPath first
            if jsonpath_parse:
                parsed_path = jsonpath_parse(json_path)
                matches = parsed_path.find(data)
                if matches:
                    return matches[0].value
            else:
                # Fallback to basic JSONPath for simple cases
                if json_path.startswith('$.'):
                    path_parts = json_path[2:].split('.')
                    current = data
                    for part in path_parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            return None
                    return current
        except Exception as e:
            print(f"[alash.bindingsapi] Error extracting value with JSONPath {json_path}: {e}")
            
        return None
        
    def stop_all_polling(self):
        """Stop all polling threads."""
        for binding_id in self.stop_polling:
            self.stop_polling[binding_id] = True
        
        # Wait for threads to finish
        for thread in self.polling_threads.values():
            if thread.is_alive():
                thread.join(timeout=1)


class GenericMQTTReader:
    """Generic MQTT client to read data based on binding configurations."""
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.bindings = {}  # topic -> list of bindings
        self.values = {}    # binding_id -> current value
        self.last_updates = {}  # binding_id -> timestamp
        self.callbacks = []
        
    def add_callback(self, callback):
        """Add a callback function to be called when values update."""
        self.callbacks.append(callback)
        
    def add_binding(self, binding_config):
        """Add a binding configuration to monitor."""
        if not binding_config.is_mqtt_event():
            return False
            
        topic = binding_config.topic
        if topic not in self.bindings:
            self.bindings[topic] = []
        self.bindings[topic].append(binding_config)
        
        binding_id = binding_config.display_name
        self.values[binding_id] = None
        self.last_updates[binding_id] = "Never"
        
        # Connect to MQTT if not already connected
        self._ensure_connected(binding_config)
        
        return True
        
    def _ensure_connected(self, binding_config):
        """Ensure MQTT client is connected for this binding."""
        if self.client is None or not self.connected:
            if mqtt is None:
                print("[alash.bindingsapi] paho-mqtt not available")
                return
                
            try:
                host, port = binding_config.get_broker_host_port()
                auth_info = binding_config.get_auth_info()
                
                self.client = mqtt.Client()
                self.client.on_connect = self.on_connect
                self.client.on_message = self.on_message
                
                # Set authentication if provided
                if auth_info.get('username') and auth_info.get('password'):
                    self.client.username_pw_set(auth_info['username'], auth_info['password'])
                
                print(f"[alash.bindingsapi] Connecting to MQTT broker: {host}:{port}")
                self.client.connect(host, port, 60)
                self.client.loop_start()
                
            except Exception as e:
                print(f"[alash.bindingsapi] Error connecting to MQTT broker: {e}")
        
    def on_connect(self, client, userdata, flags, rc):
        """Called when MQTT client connects."""
        if rc == 0:
            self.connected = True
            print("[alash.bindingsapi] Connected to MQTT broker")
            
            # Subscribe to all topics
            for topic in self.bindings.keys():
                client.subscribe(topic)
                print(f"[alash.bindingsapi] Subscribed to topic: {topic}")
        else:
            print(f"[alash.bindingsapi] Failed to connect to MQTT broker: {rc}")
            
    def on_message(self, client, userdata, msg):
        """Called when a message is received."""
        try:
            topic = msg.topic
            if topic not in self.bindings:
                return
                
            # Parse the JSON message
            data = json.loads(msg.payload.decode())
            
            # Process each binding for this topic
            for binding in self.bindings[topic]:
                binding_id = binding.display_name
                
                try:
                    # With topic-based routing, no device matching needed
                    value = self._extract_value(data, binding.filter_expression)
                    if value is not None:
                        # Store value for UI updates
                        self.values[binding_id] = value
                        self.last_updates[binding_id] = time.strftime("%H:%M:%S")
                        
                        print(f"[alash.bindingsapi] Received {binding_id}: {value}")
                        
                        # Update USD attribute
                        binding.update_usd_value(value)
                        
                        # Notify callbacks
                        for callback in self.callbacks:
                            try:
                                callback(binding_id, value, self.last_updates[binding_id])
                            except Exception as e:
                                print(f"[alash.bindingsapi] Error in callback: {e}")
                except Exception as e:
                    print(f"[alash.bindingsapi] Error processing binding {binding_id}: {e}")
                    
        except Exception as e:
            print(f"[alash.bindingsapi] Error parsing MQTT message: {e}")
            
    def _extract_value(self, data, json_path):
        """Extract value from JSON data using JSONPath."""
        if not json_path:
            return data
            
        # Simple JSONPath implementation for basic cases
        if json_path.startswith('$.'):
            path_parts = json_path[2:].split('.')
            current = data
            
            for part in path_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current
        else:
            # Fallback for complex JSONPath (requires jsonpath-ng)
            if jsonpath_parse:
                parser = jsonpath_parse(json_path)
                matches = parser.find(data)
                return matches[0].value if matches else None
            
        return None
            
    def connect(self, broker_override=None):
        """Connect to MQTT broker using configuration from bindings."""
        if mqtt is None:
            print("[alash.bindingsapi] MQTT not available")
            return False
            
        if not self.bindings:
            print("[alash.bindingsapi] No MQTT bindings to monitor")
            return False
            
        # Use broker from first binding or override
        if broker_override:
            broker_host, broker_port = broker_override.split(':') if ':' in broker_override else (broker_override, 1883)
            broker_port = int(broker_port) if isinstance(broker_port, str) else broker_port
        else:
            # Get broker from first binding
            first_binding = list(self.bindings.values())[0][0]
            broker_host, broker_port = first_binding.broker_host_port
            
        print(f"[alash.bindingsapi] Attempting to connect to MQTT broker {broker_host}:{broker_port}")
        print(f"[alash.bindingsapi] Will monitor {len(self.bindings)} topics: {list(self.bindings.keys())}")
            
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            print(f"[alash.bindingsapi] Connecting to {broker_host}:{broker_port}...")
            self.client.connect(broker_host, broker_port, 60)
            self.client.loop_start()
            print(f"[alash.bindingsapi] MQTT client started")
            return True
        except Exception as e:
            print(f"[alash.bindingsapi] Failed to connect to MQTT: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False


class USDBindingParser:
    """Parser to extract binding configurations from USD files."""
    
    @staticmethod
    def parse_usd_file(file_path):
        """Parse USD file and extract binding configurations."""
        bindings = []
        try:
            print(f"[alash.bindingsapi] Attempting to parse USD file: {file_path}")
            stage = Usd.Stage.Open(file_path)
            if not stage:
                print(f"[alash.bindingsapi] Could not open USD file: {file_path}")
                return bindings
                
            print(f"[alash.bindingsapi] Successfully opened USD stage")
            for prim in stage.Traverse():
                prim_path = str(prim.GetPath())
                
                # Check all attributes for binding metadata
                for attr in prim.GetAttributes():
                    attr_name = attr.GetName()
                    metadata = attr.GetAllMetadata()
                    
                    # Look for MQTT binding configurations in customData
                    custom_data = metadata.get('customData', {})
                    
                    # Check for new simplified MQTT schema format
                    has_mqtt_binding = 'mqtt' in custom_data and isinstance(custom_data['mqtt'], dict)
                    
                    # Check for legacy IoT binding format
                    has_iot_binding = 'binding' in custom_data and isinstance(custom_data['binding'], dict)
                    
                    # Check for original legacy format
                    binding_keys = [k for k in custom_data.keys() if 'binding' in str(k).lower()]
                    has_legacy_binding = binding_keys or any(key.startswith('binding_') for key in custom_data.keys())
                    
                    if has_mqtt_binding or has_iot_binding or has_legacy_binding:
                        print(f"[alash.bindingsapi] Found binding metadata for {prim_path}.{attr_name}")
                        
                        if has_mqtt_binding:
                            print(f"[alash.bindingsapi] Using simplified MQTT schema format")
                            mqtt_dict = custom_data['mqtt']
                            print(f"[alash.bindingsapi] MQTT config: {mqtt_dict}")
                        elif has_iot_binding:
                            print(f"[alash.bindingsapi] Using IoT binding schema format")
                            binding_dict = custom_data['binding']
                            print(f"[alash.bindingsapi] Binding config: {binding_dict}")
                        else:
                            print(f"[alash.bindingsapi] Using legacy format with direct keys: {list(custom_data.keys())}")
                            
                        binding_config = BindingConfiguration(prim_path, attr_name, custom_data)
                        
                        # Store USD references for live updates
                        binding_config.set_usd_references(stage, attr)
                        
                        print(f"[alash.bindingsapi] Binding: protocol={binding_config.protocol}, broker={binding_config.broker}, topic={binding_config.topic}")
                        
                        if binding_config.is_mqtt_stream():
                            bindings.append(binding_config)
                            print(f"[alash.bindingsapi] ✓ Added MQTT binding: {binding_config.display_name}")
                            if binding_config.description:
                                print(f"[alash.bindingsapi]   Description: {binding_config.description}")
                        else:
                            print(f"[alash.bindingsapi] ✗ Not enabled MQTT binding: {binding_config.protocol} (enabled: {binding_config.enabled})")
                            
        except Exception as e:
            print(f"[alash.bindingsapi] Error parsing USD file {file_path}: {e}")
            print(f"[alash.bindingsapi] Skipping this file and continuing with others...")
            # Don't print full traceback for USD syntax errors - they're often schema files
            
        print(f"[alash.bindingsapi] Found {len(bindings)} bindings in {file_path}")
        return bindings
    
    @staticmethod
    def parse_usd_file_new(file_path, config_manager):
        """Parse USD file and extract new event/request binding configurations."""
        bindings = []
        try:
            print(f"[alash.bindingsapi] Attempting to parse USD file: {file_path}")
            stage = Usd.Stage.Open(file_path)
            if not stage:
                print(f"[alash.bindingsapi] Could not open USD file: {file_path}")
                return bindings
                
            print(f"[alash.bindingsapi] Successfully opened USD stage")
            for prim in stage.Traverse():
                prim_path = str(prim.GetPath())
                
                # Check all attributes for binding metadata
                for attr in prim.GetAttributes():
                    attr_name = attr.GetName()
                    metadata = attr.GetAllMetadata()
                    
                    # Look for event/request binding configurations in customData
                    custom_data = metadata.get('customData', {})
                    
                    # Check for new event or request binding format
                    has_event_binding = 'event' in custom_data and isinstance(custom_data['event'], dict)
                    has_request_binding = 'request' in custom_data and isinstance(custom_data['request'], dict)
                    
                    # Also support legacy mqtt binding for backward compatibility
                    has_mqtt_binding = 'mqtt' in custom_data and isinstance(custom_data['mqtt'], dict)
                    
                    if has_event_binding or has_request_binding or has_mqtt_binding:
                        print(f"[alash.bindingsapi] Found binding metadata for {prim_path}.{attr_name}")
                        
                        try:
                            binding_config = EventBindingConfiguration(prim_path, attr_name, custom_data, config_manager)
                            
                            # Store USD references for live updates
                            binding_config.set_usd_references(stage, attr)
                            
                            print(f"[alash.bindingsapi] Binding: type={binding_config.binding_type}, protocol={binding_config.get_protocol()}, endpoint={binding_config.topic}")
                            
                            bindings.append(binding_config)
                            
                        except Exception as e:
                            print(f"[alash.bindingsapi] Error creating binding config for {prim_path}.{attr_name}: {e}")
                            
        except Exception as e:
            print(f"[alash.bindingsapi] Error parsing USD file {file_path}: {e}")
            
        return bindings
    
    @staticmethod
    def find_usd_files(directory):
        """Find all USD files in directory."""
        import os
        usd_files = []
        for file in os.listdir(directory):
            if file.endswith(('.usda', '.usdc', '.usd')):
                # Skip schema files that might have parsing issues
                if not file.startswith('BindingAPI'):
                    usd_files.append(os.path.join(directory, file))
                else:
                    print(f"[alash.bindingsapi] Skipping schema file: {file}")
        return usd_files


# Any class derived from `omni.ext.IExt` in the top level module (defined in
# `python.modules` of `extension.toml`) will be instantiated when the extension
# gets enabled, and `on_startup(ext_id)` will be called. Later when the
# extension gets disabled on_shutdown() is called.
class MyExtension(omni.ext.IExt):
    """This extension manages generic MQTT data monitoring based on USD binding schemas."""
    
    def on_startup(self, _ext_id):
        """This is called every time the extension is activated."""
        print("[alash.bindingsapi] Extension startup")

        # Calculate extension root directory first
        current_file = os.path.abspath(__file__)
        config_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        self.extension_root = os.path.dirname(config_dir)
        print(f"[alash.bindingsapi] Extension root: {self.extension_root}")

        # Initialize config manager, MQTT reader, and HTTP poller
        self.config_manager = ConfigManager(self.extension_root)
        self.mqtt_reader = GenericMQTTReader()
        self.http_poller = GenericHTTPPoller()
        self.bindings = []
        
        print("[alash.bindingsapi] About to load bindings...")
        # Parse USD files for binding configurations
        self._load_bindings()
        print(f"[alash.bindingsapi] Finished loading bindings. Total: {len(self.bindings)}")
        
        print("[alash.bindingsapi] About to create UI...")
        # Create UI
        self._create_ui()
        print("[alash.bindingsapi] UI created")
        
        # Add callbacks to update UI when values change
        self.mqtt_reader.add_callback(self._on_value_update)
        self.http_poller.add_callback(self._on_value_update)
        print("[alash.bindingsapi] Extension startup complete")

    def _load_bindings(self):
        """Load binding configurations from USD files."""
        print(f"[alash.bindingsapi] Extension directory: {self.extension_root}")
        
        # Find and parse USD files
        usd_files = USDBindingParser.find_usd_files(self.extension_root)
        print(f"[alash.bindingsapi] Found USD files: {usd_files}")
        
        for usd_file in usd_files:
            print(f"[alash.bindingsapi] Processing USD file: {usd_file}")
            bindings = USDBindingParser.parse_usd_file_new(usd_file, self.config_manager)
            print(f"[alash.bindingsapi] Found {len(bindings)} bindings in {usd_file}")
            for binding in bindings:
                self.bindings.append(binding)
                if binding.is_mqtt_event():
                    success = self.mqtt_reader.add_binding(binding)
                    print(f"[alash.bindingsapi] Added MQTT binding: {binding.display_name} -> {binding.topic} (success: {success})")
                elif binding.is_http_request():
                    success = self.http_poller.add_binding(binding)
                    print(f"[alash.bindingsapi] Added HTTP request binding: {binding.display_name} -> {binding.get_host()}{binding.topic} (success: {success})")
                print(f"[alash.bindingsapi] Binding details: type={binding.binding_type}, protocol={binding.get_protocol()}")
                print(f"[alash.bindingsapi] USD refs: stage={binding.usd_stage is not None}, attr={binding.usd_attribute is not None}")
        
        print(f"[alash.bindingsapi] Total bindings loaded: {len(self.bindings)}")
        if not self.bindings:
            print("[alash.bindingsapi] No event or request bindings found in USD files")

    def _create_ui(self):
        """Create the UI based on discovered bindings."""
        self._window = ui.Window(
            "Event & Request Data Monitor", width=600, height=500
        )
        
        with self._window.frame:
            with ui.VStack(spacing=10):
                ui.Label("Event & Request Data Monitor", style={"font_size": 18})
                ui.Separator()
                
                # Connection status
                self.status_label = ui.Label("Status: Disconnected", style={"color": 0xFF0000})
                
                # Bindings display
                if self.bindings:
                    with ui.ScrollingFrame():
                        with ui.VStack(spacing=5):
                            self.value_labels = {}
                            self.update_labels = {}
                            self.usd_buttons = {}
                            
                            for binding in self.bindings:
                                with ui.Frame():
                                    with ui.VStack(spacing=3):
                                        ui.Label(f"Binding: {binding.display_name}", style={"font_size": 14, "color": 0x00FFAA})
                                        ui.Label(f"Topic: {binding.topic}", style={"font_size": 12})
                                        ui.Label(f"JSONPath: {binding.json_path}", style={"font_size": 12})
                                        ui.Label(f"Broker: {binding.broker}", style={"font_size": 12})
                                        if binding.description:
                                            ui.Label(f"Description: {binding.description}", style={"font_size": 11, "color": 0xAAAAAAA})
                                        ui.Separator()
                                        
                                        # Value display
                                        self.value_labels[binding.display_name] = ui.Label(
                                            "Value: --", style={"font_size": 14, "color": 0x00AAFF}
                                        )
                                        self.update_labels[binding.display_name] = ui.Label(
                                            "Last Update: Never", style={"font_size": 10}
                                        )
                                        
                                        # Update USD button
                                        self.usd_buttons[binding.display_name] = ui.Button(
                                            "Update USD",
                                            clicked_fn=lambda b=binding: self._update_usd_for_binding(b),
                                            enabled=False,
                                            style={"margin": 5}
                                        )
                                        
                                        ui.Spacer(height=10)
                else:
                    ui.Label("No MQTT bindings found in USD files", style={"color": 0xFFAA00})
                
                ui.Separator()
                
                # Connect/Disconnect buttons
                with ui.HStack():
                    self.connect_btn = ui.Button("Connect MQTT", clicked_fn=self._connect_mqtt)
                    self.disconnect_btn = ui.Button("Disconnect MQTT", clicked_fn=self._disconnect_mqtt, enabled=False)
                    ui.Button("Poll All HTTP", clicked_fn=self._poll_all_http)
                    ui.Button("Refresh Bindings", clicked_fn=self._refresh_bindings)

    def _connect_mqtt(self):
        """Connect to MQTT broker."""
        print(f"[alash.bindingsapi] Connect button clicked! Bindings count: {len(self.bindings)}")
        
        if not self.bindings:
            print("[alash.bindingsapi] No bindings found - cannot connect")
            self.status_label.text = "Status: No bindings to connect"
            self.status_label.style = {"color": 0xFFAA00}
            return
            
        print(f"[alash.bindingsapi] Attempting MQTT connection with {len(self.bindings)} bindings")
        success = self.mqtt_reader.connect()
        print(f"[alash.bindingsapi] MQTT connect result: {success}")
        
        if success:
            self.status_label.text = "Status: Connecting..."
            self.status_label.style = {"color": 0xFFFF00}
            self.connect_btn.enabled = False
            self.disconnect_btn.enabled = True
            
            # Check connection status after a short delay
            def check_connection():
                time.sleep(2)
                if self.mqtt_reader.connected:
                    self.status_label.text = f"Status: Connected ({len(self.bindings)} bindings)"
                    self.status_label.style = {"color": 0x00FF00}
                else:
                    self.status_label.text = "Status: Connection Failed"
                    self.status_label.style = {"color": 0xFF0000}
                    self.connect_btn.enabled = True
                    self.disconnect_btn.enabled = False
                    
            threading.Thread(target=check_connection, daemon=True).start()
        else:
            self.status_label.text = "Status: Failed to Connect"
            self.status_label.style = {"color": 0xFF0000}
    
    def _disconnect_mqtt(self):
        """Disconnect from MQTT broker."""
        self.mqtt_reader.disconnect()
        self.status_label.text = "Status: Disconnected"
        self.status_label.style = {"color": 0xFF0000}
        self.connect_btn.enabled = True
        self.disconnect_btn.enabled = False
        
    def _refresh_bindings(self):
        """Refresh bindings from USD files."""
        self.mqtt_reader.disconnect()
        self.bindings.clear()
        self.mqtt_reader = GenericMQTTReader()
        self._load_bindings()
        self._create_ui()
        self.mqtt_reader.add_callback(self._on_value_update)
        
    def _update_usd_for_binding(self, binding):
        """Update USD attribute for a specific binding using its last known value."""
        binding_id = binding.display_name
        if binding_id in self.mqtt_reader.values and self.mqtt_reader.values[binding_id] is not None:
            value = self.mqtt_reader.values[binding_id]
            success = binding.update_usd_value(value)
            if success:
                print(f"[alash.bindingsapi] ✓ Manually updated USD attribute {binding_id} = {value}")
                # Update button text temporarily to show success
                if hasattr(self, 'usd_buttons') and binding_id in self.usd_buttons:
                    original_text = "Update USD"
                    self.usd_buttons[binding_id].text = "✓ Updated!"
                    
                    # Reset button text after 2 seconds
                    def reset_button():
                        time.sleep(2)
                        if hasattr(self, 'usd_buttons') and binding_id in self.usd_buttons:
                            self.usd_buttons[binding_id].text = original_text
                    threading.Thread(target=reset_button, daemon=True).start()
            else:
                print(f"[alash.bindingsapi] ✗ Failed to update USD attribute {binding_id}")
        else:
            print(f"[alash.bindingsapi] No value available for {binding_id}")
        
    def _on_value_update(self, binding_id, value, last_update):
        """Called when a binding value is updated from MQTT."""
        if hasattr(self, 'value_labels') and binding_id in self.value_labels:
            self.value_labels[binding_id].text = f"Value: {value}"
            self.update_labels[binding_id].text = f"Last Update: {last_update}"
            
            # Enable the Update USD button when we have a value
            if hasattr(self, 'usd_buttons') and binding_id in self.usd_buttons:
                self.usd_buttons[binding_id].enabled = True

    def on_shutdown(self):
        """This is called every time the extension is deactivated. It is used
        to clean up the extension state."""
        print("[alash.bindingsapi] Extension shutdown")
        if hasattr(self, 'mqtt_reader'):
            self.mqtt_reader.disconnect()
        if hasattr(self, 'http_poller'):
            self.http_poller.stop_all_polling()
        if hasattr(self, '_window') and self._window:
            self._window.destroy()
            self._window = None
    
    def _poll_all_http(self):
        """Manually trigger polling for all HTTP bindings."""
        http_bindings = [b for b in self.bindings if b.is_http_request()]
        if not http_bindings:
            print("[alash.bindingsapi] No HTTP bindings found")
            return
        
        print(f"[alash.bindingsapi] Manually polling {len(http_bindings)} HTTP bindings")
        
        for binding in http_bindings:
            self._poll_http_binding(binding)
    
    def _poll_http_binding(self, binding):
        """Manually poll a specific HTTP binding."""
        if requests is None:
            print("[alash.bindingsapi] requests library not available")
            return
        
        try:
            # Build the full URL
            base_url = binding.get_host()
            endpoint = binding.endpoint_target
            full_url = f"{base_url}{endpoint}"
            
            # Get auth info
            auth_info = binding.get_auth_info()
            headers = {}
            auth = None
            
            # Set up authentication
            if auth_info.get('auth_method') == 'api_key' and auth_info.get('api_key'):
                headers['Authorization'] = f"Bearer {auth_info['api_key']}"
            elif auth_info.get('username') and auth_info.get('password'):
                auth = (auth_info['username'], auth_info['password'])
            
            # Make the HTTP request
            timeout = binding.connection_config.get('timeout', 30) if binding.connection_config else 30
            
            print(f"[alash.bindingsapi] Manual poll: {full_url}")
            response = requests.get(full_url, headers=headers, auth=auth, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract value using filter expression
                value = self._extract_value_from_json(data, binding.filter_expression)
                
                if value is not None:
                    print(f"[alash.bindingsapi] Manual HTTP poll result {binding.display_name}: {value}")
                    
                    # Update USD attribute
                    binding.update_usd_value(value)
                    
                    # Update UI
                    self._on_value_update(binding.display_name, value, time.strftime("%H:%M:%S"))
                else:
                    print(f"[alash.bindingsapi] Could not extract value using {binding.filter_expression}")
            else:
                print(f"[alash.bindingsapi] HTTP request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"[alash.bindingsapi] Error in manual HTTP poll for {binding.display_name}: {e}")
    
    def _extract_value_from_json(self, data, json_path):
        """Extract value from JSON data using JSONPath."""
        if not json_path:
            return data
            
        try:
            # Try advanced JSONPath first
            if jsonpath_parse:
                parsed_path = jsonpath_parse(json_path)
                matches = parsed_path.find(data)
                if matches:
                    return matches[0].value
            else:
                # Fallback to basic JSONPath for simple cases
                if json_path.startswith('$.'):
                    path_parts = json_path[2:].split('.')
                    current = data
                    for part in path_parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            return None
                    return current
        except Exception as e:
            print(f"[alash.bindingsapi] Error extracting value with JSONPath {json_path}: {e}")
            
        return None
    
    def _update_all_usd(self):
        """Update all USD attributes with current values."""
        updated_count = 0
        for binding in self.bindings:
            # Get current value from either MQTT or HTTP storage
            binding_id = binding.display_name
            current_value = None
            
            if binding.is_mqtt_event() and hasattr(self.mqtt_reader, 'values'):
                current_value = self.mqtt_reader.values.get(binding_id)
            elif binding.is_http_request() and hasattr(self.http_poller, 'values'):
                current_value = self.http_poller.values.get(binding_id)
            
            if current_value is not None:
                success = binding.update_usd_value(current_value)
                if success:
                    updated_count += 1
        
        print(f"[alash.bindingsapi] Updated {updated_count} USD attributes")
    
    def _stop_http_polling(self):
        """Stop all HTTP polling threads."""
        if hasattr(self, 'http_poller'):
            self.http_poller.stop_all_polling()
            print("[alash.bindingsapi] Stopped all HTTP polling threads")
