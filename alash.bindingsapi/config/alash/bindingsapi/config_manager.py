import os
from typing import Dict, Any, Optional

# Try to import tomllib (Python 3.11+) or fallback to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None
        print("[alash.bindingsapi] Warning: No TOML library available. Install tomli: pip install tomli")

class ConfigManager:
    """Manages connection configurations from TOML files."""
    
    def __init__(self, extension_root_dir: str = None):
        self._connections_cache = {}
        # Store extension root directory for resolving relative paths
        if extension_root_dir:
            self.extension_root = extension_root_dir
        else:
            # Calculate extension root from current module location
            current_file = os.path.abspath(__file__)
            config_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            self.extension_root = os.path.dirname(config_dir)
        
        print(f"[alash.bindingsapi] ConfigManager extension root: {self.extension_root}")
        
    def load_connections(self, config_file_path: str) -> Dict[str, Any]:
        """Load connections from TOML config file."""
        # Resolve relative paths relative to extension root
        if not os.path.isabs(config_file_path):
            config_file_path = os.path.join(self.extension_root, config_file_path)
            
        if config_file_path in self._connections_cache:
            return self._connections_cache[config_file_path]
            
        if not tomllib:
            print("[alash.bindingsapi] TOML library not available")
            return {}
            
        try:
            if not os.path.exists(config_file_path):
                print(f"[alash.bindingsapi] Config file not found: {config_file_path}")
                return {}
                
            with open(config_file_path, 'rb') as f:
                config = tomllib.load(f)
                
            connections = config.get('connections', {})
            self._connections_cache[config_file_path] = connections
            
            print(f"[alash.bindingsapi] Loaded {len(connections)} connections from {config_file_path}")
            return connections
            
        except Exception as e:
            print(f"[alash.bindingsapi] Error loading config file {config_file_path}: {e}")
            return {}
            
    def get_connection(self, config_file_path: str, connection_ref: str) -> Optional[Dict[str, Any]]:
        """Get specific connection configuration."""
        connections = self.load_connections(config_file_path)
        return connections.get(connection_ref)
        
    def clear_cache(self):
        """Clear the connections cache."""
        self._connections_cache.clear()


class EventBindingConfiguration:
    """Represents an event binding configuration with external connection config."""
    
    def __init__(self, prim_path, attr_name, config, config_manager: ConfigManager):
        self.prim_path = prim_path
        self.attr_name = attr_name
        self.config_manager = config_manager
        
        # USD references for live updates
        self.usd_stage = None
        self.usd_attribute = None
        
        # Parse event or request binding
        self.binding_type = None  # 'event' or 'request'
        self.binding_config = None
        
        if 'event' in config:
            self.binding_type = 'event'
            self.binding_config = config['event']
        elif 'request' in config:
            self.binding_type = 'request'
            self.binding_config = config['request']
        else:
            # Legacy support for mqtt binding
            if 'mqtt' in config:
                self.binding_type = 'event'
                self.binding_config = config['mqtt']
                # Convert legacy mqtt config to new format
                self.binding_config['connectionRef'] = 'mqtt_local'
                self.binding_config['configFile'] = 'usd_config/event_connections.toml'
            else:
                raise ValueError(f"No valid binding configuration found in {config}")
        
        # Extract connection info
        self.connection_ref = self.binding_config.get('connectionRef', '')
        self.config_file = self.binding_config.get('configFile', '')
        
        # Load connection details
        self.connection_config = None
        if self.connection_ref and self.config_file:
            self.connection_config = self.config_manager.get_connection(
                self.config_file, self.connection_ref
            )
            
        # Extract binding-specific settings
        self.endpoint_target = self.binding_config.get('endpointTarget', '')
        self.filter_expression = self.binding_config.get('filterExpression', '')
        self.reliability = self.binding_config.get('reliability', 1)
        self.payload_format = self.binding_config.get('payloadFormat', 'JSON')
        self.schema = self.binding_config.get('schema', '')
        self.description = self.binding_config.get('description', '')
        self.enabled = self.binding_config.get('enabled', True)
        
        # Request-specific settings
        self.method = self.binding_config.get('method', 'GET')
        self.poll_interval_seconds = self.binding_config.get('pollIntervalSeconds', 30)
        
    def get_protocol(self) -> str:
        """Get the protocol from connection config."""
        if self.connection_config:
            return self.connection_config.get('protocol', 'unknown')
        return 'unknown'
        
    def get_host(self) -> str:
        """Get the host from connection config."""
        if self.connection_config:
            return self.connection_config.get('host', 'localhost')
        return 'localhost'
        
    def get_broker_host_port(self) -> tuple:
        """Get MQTT broker host and port."""
        host = self.get_host()
        if ':' in host:
            host_part, port_part = host.split(':', 1)
            try:
                return host_part, int(port_part)
            except ValueError:
                return host_part, 1883
        return host, 1883
        
    def get_auth_info(self) -> Dict[str, Any]:
        """Get authentication information from connection config."""
        if self.connection_config:
            return {
                'username': self.connection_config.get('username', ''),
                'password': self.connection_config.get('password', ''),
                'api_key': self.connection_config.get('api_key', ''),
                'auth_method': self.connection_config.get('auth_method', 'none')
            }
        return {}
        
    def is_mqtt_event(self) -> bool:
        """Check if this is an MQTT event binding."""
        return (self.binding_type == 'event' and 
                self.get_protocol().lower() == 'mqtt' and 
                self.enabled)
                
    def is_http_request(self) -> bool:
        """Check if this is an HTTP request binding."""
        return (self.binding_type == 'request' and 
                self.get_protocol().lower() == 'http' and 
                self.enabled)
        
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
                    converted_value = int(float(value))
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
        
    @property
    def display_name(self):
        return f"{self.prim_path}.{self.attr_name}"
        
    @property
    def topic(self):
        """Get the topic/endpoint for this binding."""
        return self.endpoint_target
    
    @property
    def json_path(self):
        """Get the JSONPath filter expression for compatibility."""
        return self.filter_expression
    
    @property
    def broker(self):
        """Get the broker/host for compatibility."""
        return self.get_host()
