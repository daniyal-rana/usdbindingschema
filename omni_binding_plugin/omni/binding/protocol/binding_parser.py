"""
Binding parser for extracting and processing USD binding metadata
"""

import re
from typing import Dict, Any, Optional, List
from pxr import Usd, Sdf
import carb


class BindingParser:
    """Parser for USD binding metadata"""
    
    def __init__(self):
        self._variable_pattern = re.compile(r'\$\{([^}]+)\}')
    
    def parse_context(self, prim: Usd.Prim) -> Dict[str, str]:
        """Parse binding:context dictionary from a prim"""
        context = {}
        
        try:
            # Look for binding:context attribute
            if prim.HasAttribute("binding:context"):
                context_attr = prim.GetAttribute("binding:context")
                if context_attr.IsValid():
                    context_value = context_attr.Get()
                    if isinstance(context_value, dict):
                        context.update(context_value)
            
            # Inherit context from parent prims
            parent = prim.GetParent()
            while parent and parent.IsValid():
                if parent.HasAttribute("binding:context"):
                    parent_context_attr = parent.GetAttribute("binding:context")
                    if parent_context_attr.IsValid():
                        parent_context = parent_context_attr.Get()
                        if isinstance(parent_context, dict):
                            # Parent context has lower priority
                            for key, value in parent_context.items():
                                if key not in context:
                                    context[key] = value
                parent = parent.GetParent()
                
        except Exception as e:
            carb.log_error(f"[BindingParser] Error parsing context for {prim.GetPath()}: {e}")
        
        return context
    
    def parse_auth_defaults(self, prim: Usd.Prim) -> Dict[str, Dict[str, Any]]:
        """Parse auth defaults from a prim"""
        auth_defaults = {}
        
        try:
            protocols = ["mqtt", "rest", "sql", "grpc", "websocket", "file"]
            
            for protocol in protocols:
                attr_name = f"binding:authDefaults:{protocol}"
                if prim.HasAttribute(attr_name):
                    auth_attr = prim.GetAttribute(attr_name)
                    if auth_attr.IsValid():
                        auth_value = auth_attr.Get()
                        if isinstance(auth_value, dict):
                            auth_defaults[protocol] = auth_value
            
            # Inherit auth defaults from parents
            parent = prim.GetParent()
            while parent and parent.IsValid():
                for protocol in protocols:
                    if protocol in auth_defaults:
                        continue  # Child overrides parent
                        
                    attr_name = f"binding:authDefaults:{protocol}"
                    if parent.HasAttribute(attr_name):
                        auth_attr = parent.GetAttribute(attr_name)
                        if auth_attr.IsValid():
                            auth_value = auth_attr.Get()
                            if isinstance(auth_value, dict):
                                auth_defaults[protocol] = auth_value
                parent = parent.GetParent()
                
        except Exception as e:
            carb.log_error(f"[BindingParser] Error parsing auth defaults for {prim.GetPath()}: {e}")
        
        return auth_defaults
    
    def parse_attribute_binding(self, prim: Usd.Prim, attr: Usd.Attribute) -> Optional[Dict[str, Any]]:
        """Parse binding metadata from an attribute"""
        if not attr.IsValid():
            return None
        
        try:
            binding_config = {}
            metadata = attr.GetMetadata()
            
            # Extract all binding: metadata
            for key, value in metadata.items():
                if key.startswith("binding:"):
                    binding_key = key[8:]  # Remove "binding:" prefix
                    binding_config[binding_key] = value
            
            # Must have protocol to be valid
            if "protocol" not in binding_config:
                return None
            
            # Get context for variable substitution
            context = self.parse_context(prim)
            
            # Substitute variables in string values
            for key, value in binding_config.items():
                if isinstance(value, str):
                    binding_config[key] = self._substitute_variables(value, context)
            
            # Get auth defaults for the protocol
            auth_defaults = self.parse_auth_defaults(prim)
            protocol = binding_config.get("protocol")
            if protocol in auth_defaults:
                # Merge auth defaults (binding metadata takes precedence)
                for auth_key, auth_value in auth_defaults[protocol].items():
                    if auth_key not in binding_config:
                        binding_config[auth_key] = auth_value
            
            # Add attribute information
            binding_config["_attr_name"] = attr.GetName()
            binding_config["_attr_type"] = str(attr.GetTypeName())
            binding_config["_prim_path"] = str(prim.GetPath())
            
            return binding_config
            
        except Exception as e:
            carb.log_error(f"[BindingParser] Error parsing attribute binding {prim.GetPath()}.{attr.GetName()}: {e}")
            return None
    
    def _substitute_variables(self, text: str, context: Dict[str, str]) -> str:
        """Substitute ${variable} placeholders with context values"""
        if not isinstance(text, str):
            return text
        
        def replace_var(match):
            var_name = match.group(1)
            if var_name in context:
                return str(context[var_name])
            else:
                carb.log_warn(f"[BindingParser] Variable '{var_name}' not found in context")
                return match.group(0)  # Return unchanged if not found
        
        return self._variable_pattern.sub(replace_var, text)
    
    def validate_binding_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate a binding configuration and return list of errors"""
        errors = []
        
        # Required fields
        if "protocol" not in config:
            errors.append("Missing required field: protocol")
        
        protocol = config.get("protocol")
        operation = config.get("operation")
        
        # Protocol-specific validation
        if protocol == "mqtt":
            if "uri" not in config:
                errors.append("MQTT binding requires 'uri' field")
            if operation == "stream" and "topic" not in config:
                errors.append("MQTT streaming requires 'topic' field")
        
        elif protocol == "rest":
            if "uri" not in config:
                errors.append("REST binding requires 'uri' field")
            if "method" not in config:
                errors.append("REST binding requires 'method' field")
        
        elif protocol == "sql":
            if "uri" not in config:
                errors.append("SQL binding requires 'uri' field")
            if "query" not in config:
                errors.append("SQL binding requires 'query' field")
        
        elif protocol == "grpc":
            if "uri" not in config:
                errors.append("gRPC binding requires 'uri' field")
            if "query" not in config:
                errors.append("gRPC binding requires 'query' field (request payload)")
        
        elif protocol == "websocket":
            if "uri" not in config:
                errors.append("WebSocket binding requires 'uri' field")
        
        elif protocol == "file":
            if "uri" not in config:
                errors.append("File binding requires 'uri' field (file path)")
        
        # Operation validation
        valid_operations = ["read", "stream", "write", "connect", "disconnect"]
        if operation and operation not in valid_operations:
            errors.append(f"Invalid operation: {operation}. Must be one of {valid_operations}")
        
        # Auth validation
        auth_method = config.get("authMethod")
        if auth_method:
            valid_auth_methods = ["none", "oauth2", "apikey", "mtls"]
            if auth_method not in valid_auth_methods:
                errors.append(f"Invalid authMethod: {auth_method}. Must be one of {valid_auth_methods}")
        
        return errors
