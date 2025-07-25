"""
Protocol manager for handling connections to various binding protocols
"""

import asyncio
import json
import weakref
from typing import Dict, Any, Optional, Set, Callable, List
from dataclasses import dataclass
from enum import Enum
import carb
import omni.usd
from pxr import Usd, Sdf

from .protocols.mqtt_client import MQTTClient
from .protocols.rest_client import RESTClient
from .protocols.sql_client import SQLClient
from .protocols.grpc_client import GRPCClient
from .protocols.websocket_client import WebSocketClient
from .protocols.file_client import FileClient


class ConnectionState(Enum):
    """Connection state enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class BindingInfo:
    """Information about a binding"""
    prim_path: str
    attr_name: str
    config: Dict[str, Any]
    protocol: str
    operation: str
    client: Optional[Any] = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    last_value: Any = None
    last_error: Optional[str] = None


class ProtocolManager:
    """Manages connections to various protocols for USD bindings"""
    
    def __init__(self):
        self._bindings: Dict[str, BindingInfo] = {}  # key: f"{prim_path}.{attr_name}"
        self._prim_contexts: Dict[str, Dict[str, str]] = {}
        self._prim_auth_defaults: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._streaming_bindings: Set[str] = set()
        self._clients: Dict[str, Any] = {}  # Reusable clients by connection key
        self._update_callbacks: List[Callable] = []
        self._usd_context = None
        
        # Initialize client classes
        self._client_classes = {
            "mqtt": MQTTClient,
            "rest": RESTClient,
            "sql": SQLClient,
            "grpc": GRPCClient,
            "websocket": WebSocketClient,
            "file": FileClient
        }
    
    def add_update_callback(self, callback: Callable):
        """Add a callback for when binding values are updated"""
        self._update_callbacks.append(callback)
    
    def remove_update_callback(self, callback: Callable):
        """Remove an update callback"""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
    
    def set_prim_context(self, prim_path: str, context: Dict[str, str], auth_defaults: Dict[str, Dict[str, Any]]):
        """Set context and auth defaults for a prim"""
        self._prim_contexts[prim_path] = context
        self._prim_auth_defaults[prim_path] = auth_defaults
    
    async def register_binding(self, prim_path: str, attr_name: str, config: Dict[str, Any]):
        """Register a new binding"""
        binding_key = f"{prim_path}.{attr_name}"
        
        try:
            protocol = config.get("protocol")
            operation = config.get("operation", "read")
            
            if protocol not in self._client_classes:
                carb.log_error(f"[ProtocolManager] Unsupported protocol: {protocol}")
                return
            
            # Create binding info
            binding_info = BindingInfo(
                prim_path=prim_path,
                attr_name=attr_name,
                config=config,
                protocol=protocol,
                operation=operation
            )
            
            self._bindings[binding_key] = binding_info
            
            # Track streaming bindings
            if operation == "stream":
                self._streaming_bindings.add(binding_key)
            
            carb.log_info(f"[ProtocolManager] Registered binding: {binding_key} ({protocol}:{operation})")
            
            # Auto-connect for read operations
            if operation == "read":
                await self._connect_binding(binding_key)
                
        except Exception as e:
            carb.log_error(f"[ProtocolManager] Error registering binding {binding_key}: {e}")
    
    async def start_streaming_connections(self):
        """Start all streaming connections"""
        carb.log_info(f"[ProtocolManager] Starting {len(self._streaming_bindings)} streaming connections")
        
        tasks = []
        for binding_key in self._streaming_bindings:
            tasks.append(self._connect_binding(binding_key))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_streaming_connections(self):
        """Stop all streaming connections"""
        carb.log_info(f"[ProtocolManager] Stopping streaming connections")
        
        tasks = []
        for binding_key in self._streaming_bindings:
            if binding_key in self._bindings:
                binding_info = self._bindings[binding_key]
                if binding_info.client:
                    tasks.append(self._disconnect_binding(binding_key))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all_connections(self):
        """Stop all active connections"""
        carb.log_info(f"[ProtocolManager] Stopping all connections")
        
        tasks = []
        for binding_key, binding_info in self._bindings.items():
            if binding_info.client and binding_info.state == ConnectionState.CONNECTED:
                tasks.append(self._disconnect_binding(binding_key))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def shutdown(self):
        """Shutdown the protocol manager"""
        await self.stop_all_connections()
        self._bindings.clear()
        self._streaming_bindings.clear()
        self._clients.clear()
        self._update_callbacks.clear()
    
    async def _connect_binding(self, binding_key: str):
        """Connect a specific binding"""
        if binding_key not in self._bindings:
            return
        
        binding_info = self._bindings[binding_key]
        
        try:
            binding_info.state = ConnectionState.CONNECTING
            
            # Get or create client
            client_key = self._get_client_key(binding_info.config)
            if client_key not in self._clients:
                client_class = self._client_classes[binding_info.protocol]
                client = client_class()
                self._clients[client_key] = client
            else:
                client = self._clients[client_key]
            
            binding_info.client = client
            
            # Connect client
            await client.connect(binding_info.config)
            binding_info.state = ConnectionState.CONNECTED
            
            # Start data retrieval based on operation
            if binding_info.operation == "read":
                await self._perform_read(binding_info)
            elif binding_info.operation == "stream":
                await self._start_streaming(binding_info)
            
            carb.log_info(f"[ProtocolManager] Connected binding: {binding_key}")
            
        except Exception as e:
            binding_info.state = ConnectionState.ERROR
            binding_info.last_error = str(e)
            carb.log_error(f"[ProtocolManager] Error connecting binding {binding_key}: {e}")
    
    async def _disconnect_binding(self, binding_key: str):
        """Disconnect a specific binding"""
        if binding_key not in self._bindings:
            return
        
        binding_info = self._bindings[binding_key]
        
        try:
            if binding_info.client:
                await binding_info.client.disconnect()
                binding_info.client = None
            
            binding_info.state = ConnectionState.DISCONNECTED
            carb.log_info(f"[ProtocolManager] Disconnected binding: {binding_key}")
            
        except Exception as e:
            carb.log_error(f"[ProtocolManager] Error disconnecting binding {binding_key}: {e}")
    
    async def _perform_read(self, binding_info: BindingInfo):
        """Perform a one-time read operation"""
        try:
            value = await binding_info.client.read(binding_info.config)
            await self._update_attribute_value(binding_info, value)
            
        except Exception as e:
            binding_info.last_error = str(e)
            carb.log_error(f"[ProtocolManager] Error reading from {binding_info.prim_path}.{binding_info.attr_name}: {e}")
    
    async def _start_streaming(self, binding_info: BindingInfo):
        """Start streaming data from a binding"""
        try:
            async def on_data(value):
                await self._update_attribute_value(binding_info, value)
            
            await binding_info.client.start_stream(binding_info.config, on_data)
            
        except Exception as e:
            binding_info.last_error = str(e)
            carb.log_error(f"[ProtocolManager] Error starting stream for {binding_info.prim_path}.{binding_info.attr_name}: {e}")
    
    async def _update_attribute_value(self, binding_info: BindingInfo, value: Any):
        """Update the USD attribute with a new value"""
        try:
            # Store the value
            binding_info.last_value = value
            
            # Update USD attribute
            if not self._usd_context:
                self._usd_context = omni.usd.get_context()
            
            stage = self._usd_context.get_stage()
            if not stage:
                return
            
            prim = stage.GetPrimAtPath(binding_info.prim_path)
            if not prim.IsValid():
                return
            
            attr = prim.GetAttribute(binding_info.attr_name)
            if not attr.IsValid():
                return
            
            # Convert value to appropriate USD type
            usd_value = self._convert_to_usd_type(value, binding_info.config.get("_attr_type"))
            
            # Set the attribute value
            attr.Set(usd_value)
            
            # Notify callbacks
            for callback in self._update_callbacks:
                try:
                    callback(binding_info.prim_path, binding_info.attr_name, value)
                except Exception as e:
                    carb.log_error(f"[ProtocolManager] Error in update callback: {e}")
            
        except Exception as e:
            carb.log_error(f"[ProtocolManager] Error updating attribute {binding_info.prim_path}.{binding_info.attr_name}: {e}")
    
    def _convert_to_usd_type(self, value: Any, usd_type: str) -> Any:
        """Convert a value to the appropriate USD type"""
        if not usd_type:
            return value
        
        try:
            if "double" in usd_type or "float" in usd_type:
                return float(value)
            elif "int" in usd_type:
                return int(value)
            elif "bool" in usd_type:
                return bool(value)
            elif "string" in usd_type:
                return str(value)
            else:
                return value
        except (ValueError, TypeError):
            carb.log_warn(f"[ProtocolManager] Could not convert value {value} to type {usd_type}")
            return value
    
    def _get_client_key(self, config: Dict[str, Any]) -> str:
        """Generate a key for client reuse"""
        protocol = config.get("protocol", "")
        uri = config.get("uri", "")
        auth_profile = config.get("authProfile", "")
        return f"{protocol}://{uri}#{auth_profile}"
    
    def get_bindings(self) -> Dict[str, BindingInfo]:
        """Get all registered bindings"""
        return self._bindings.copy()
    
    def get_binding_info(self, prim_path: str, attr_name: str) -> Optional[BindingInfo]:
        """Get binding info for a specific attribute"""
        binding_key = f"{prim_path}.{attr_name}"
        return self._bindings.get(binding_key)
