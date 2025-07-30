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

# Try to install packages (but don't fail if it doesn't work)
try:
    install_pip_packages()
except Exception as e:
    print(f"[alash.bindingsapi] Package installation failed: {e}")

# Import packages after installation
mqtt = None
jsonpath_parse = None

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
            self.unit = self._get_value(mqtt_dict, ['unit'], '')
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
            self.unit = self._get_value(binding_dict, ['unit'], '')
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
            self.unit = ''
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
        if not binding_config.is_mqtt_stream():
            return False
            
        topic = binding_config.topic
        if topic not in self.bindings:
            self.bindings[topic] = []
        self.bindings[topic].append(binding_config)
        
        binding_id = binding_config.display_name
        self.values[binding_id] = None
        self.last_updates[binding_id] = "Never"
        return True
        
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
                    value = self._extract_value(data, binding.json_path)
                    if value is not None:
                        # Store value for UI updates
                        self.values[binding_id] = value
                        self.last_updates[binding_id] = time.strftime("%H:%M:%S")
                        
                        print(f"[alash.bindingsapi] Received {binding_id}: {value}")
                        
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
                            if binding_config.unit:
                                print(f"[alash.bindingsapi]   Unit: {binding_config.unit}")
                        else:
                            print(f"[alash.bindingsapi] ✗ Not enabled MQTT binding: {binding_config.protocol} (enabled: {binding_config.enabled})")
                            
        except Exception as e:
            print(f"[alash.bindingsapi] Error parsing USD file {file_path}: {e}")
            print(f"[alash.bindingsapi] Skipping this file and continuing with others...")
            # Don't print full traceback for USD syntax errors - they're often schema files
            
        print(f"[alash.bindingsapi] Found {len(bindings)} bindings in {file_path}")
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

        # Initialize MQTT reader
        self.mqtt_reader = GenericMQTTReader()
        self.bindings = []
        
        print("[alash.bindingsapi] About to load bindings...")
        # Parse USD files for binding configurations
        self._load_bindings()
        print(f"[alash.bindingsapi] Finished loading bindings. Total: {len(self.bindings)}")
        
        print("[alash.bindingsapi] About to create UI...")
        # Create UI
        self._create_ui()
        print("[alash.bindingsapi] UI created")
        
        # Add callback to update UI when values change
        self.mqtt_reader.add_callback(self._on_value_update)
        print("[alash.bindingsapi] Extension startup complete")

    def _load_bindings(self):
        """Load binding configurations from USD files."""
        import os
        
        # Get extension directory
        ext_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        print(f"[alash.bindingsapi] Extension directory: {ext_dir}")
        
        # Find and parse USD files
        usd_files = USDBindingParser.find_usd_files(ext_dir)
        print(f"[alash.bindingsapi] Found USD files: {usd_files}")
        
        for usd_file in usd_files:
            print(f"[alash.bindingsapi] Processing USD file: {usd_file}")
            bindings = USDBindingParser.parse_usd_file(usd_file)
            print(f"[alash.bindingsapi] Found {len(bindings)} bindings in {usd_file}")
            for binding in bindings:
                self.bindings.append(binding)
                success = self.mqtt_reader.add_binding(binding)
                print(f"[alash.bindingsapi] Added binding: {binding.display_name} -> {binding.topic} (success: {success})")
                print(f"[alash.bindingsapi] Binding details: protocol={binding.protocol}, broker={binding.broker}, topic={binding.topic}, json_path={binding.json_path}")
                print(f"[alash.bindingsapi] USD refs: stage={binding.usd_stage is not None}, attr={binding.usd_attribute is not None}")
        
        print(f"[alash.bindingsapi] Total bindings loaded: {len(self.bindings)}")
        if not self.bindings:
            print("[alash.bindingsapi] No MQTT bindings found in USD files")

    def _create_ui(self):
        """Create the UI based on discovered bindings."""
        self._window = ui.Window(
            "MQTT Data Monitor", width=500, height=300
        )
        
        with self._window.frame:
            with ui.VStack(spacing=10):
                ui.Label("MQTT Data Monitor", style={"font_size": 18})
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
                                        if binding.unit:
                                            ui.Label(f"Unit: {binding.unit}", style={"font_size": 12})
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
                    self.connect_btn = ui.Button("Connect to MQTT", clicked_fn=self._connect_mqtt)
                    self.disconnect_btn = ui.Button("Disconnect", clicked_fn=self._disconnect_mqtt, enabled=False)
                    ui.Button("Refresh USD", clicked_fn=self._refresh_bindings)

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
