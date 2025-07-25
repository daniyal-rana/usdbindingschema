"""
gRPC protocol client implementation
"""

import asyncio
import json
from typing import Dict, Any, Callable, Optional
import carb

try:
    import grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    carb.log_warn("[GRPCClient] grpcio not available, gRPC functionality disabled")

from .base_client import BaseProtocolClient


class GRPCClient(BaseProtocolClient):
    """gRPC protocol client"""
    
    def __init__(self):
        super().__init__()
        self._channel: Optional[Any] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._poll_callback: Optional[Callable] = None
    
    async def connect(self, config: Dict[str, Any]):
        """Connect to gRPC server"""
        if not GRPC_AVAILABLE:
            raise RuntimeError("gRPC client not available - install grpcio package")
        
        self._validate_config(config, ["uri"])
        self._config = config
        
        try:
            # Parse gRPC URI
            uri = config["uri"]
            if uri.startswith("grpc://"):
                address = uri[7:]  # Remove "grpc://" prefix
                # Create insecure channel
                self._channel = grpc.aio.insecure_channel(address)
            elif uri.startswith("grpcs://"):
                address = uri[8:]  # Remove "grpcs://" prefix
                # Create secure channel
                credentials = grpc.ssl_channel_credentials()
                self._channel = grpc.aio.secure_channel(address, credentials)
            else:
                raise ValueError(f"Invalid gRPC URI format: {uri}")
            
            # Test connection
            await grpc.aio.channel_ready_future(self._channel).wait_for(timeout=10)
            
            self._connected = True
            carb.log_info(f"[GRPCClient] Connected to {address}")
            
        except Exception as e:
            self._connected = False
            raise RuntimeError(f"Failed to connect to gRPC server: {e}")
    
    async def disconnect(self):
        """Disconnect from gRPC server"""
        try:
            if self._poll_task:
                self._poll_task.cancel()
                self._poll_task = None
            
            if self._channel:
                await self._channel.close()
                self._channel = None
            
            self._connected = False
            carb.log_info(f"[GRPCClient] Disconnected")
            
        except Exception as e:
            carb.log_error(f"[GRPCClient] Error during disconnect: {e}")
    
    async def read(self, config: Dict[str, Any]) -> Any:
        """Make gRPC call"""
        if not self._connected or not self._channel:
            raise RuntimeError("gRPC client not connected")
        
        # Note: This is a simplified implementation
        # In practice, you'd need to generate gRPC stubs from .proto files
        # and use the appropriate service methods
        
        query = config.get("query")
        if not query:
            raise ValueError("gRPC operation requires 'query' field (request payload)")
        
        try:
            # This is a placeholder implementation
            # You would replace this with actual gRPC service calls
            carb.log_warn("[GRPCClient] gRPC read operation not fully implemented - requires service-specific stubs")
            
            # Parse query as JSON for request payload
            if isinstance(query, str):
                try:
                    request_data = json.loads(query)
                except json.JSONDecodeError:
                    request_data = {"data": query}
            else:
                request_data = query
            
            # Mock response for demonstration
            return {"status": "success", "data": request_data}
            
        except Exception as e:
            raise RuntimeError(f"Failed to make gRPC call: {e}")
    
    async def write(self, config: Dict[str, Any], value: Any) -> bool:
        """Make gRPC write call"""
        if not self._connected or not self._channel:
            raise RuntimeError("gRPC client not connected")
        
        try:
            # This is a placeholder implementation
            carb.log_warn("[GRPCClient] gRPC write operation not fully implemented - requires service-specific stubs")
            return True
            
        except Exception as e:
            carb.log_error(f"[GRPCClient] Failed to make gRPC write call: {e}")
            return False
    
    async def start_stream(self, config: Dict[str, Any], callback: Callable[[Any], None]):
        """Start gRPC streaming or polling"""
        if not self._connected:
            raise RuntimeError("gRPC client not connected")
        
        self._poll_callback = callback
        
        # For demonstration, we'll poll instead of using gRPC streaming
        refresh_policy = config.get("refreshPolicy", "interval:30s")
        interval = self._parse_refresh_interval(refresh_policy)
        
        self._poll_task = asyncio.create_task(self._poll_grpc(config, interval))
    
    async def stop_stream(self):
        """Stop gRPC streaming or polling"""
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        
        self._poll_callback = None
    
    async def _poll_grpc(self, config: Dict[str, Any], interval: float):
        """Internal task to poll gRPC service"""
        try:
            while True:
                try:
                    value = await self.read(config)
                    if self._poll_callback:
                        await self._poll_callback(value)
                except Exception as e:
                    carb.log_error(f"[GRPCClient] Error polling gRPC service: {e}")
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            carb.log_info(f"[GRPCClient] Polling task cancelled")
        except Exception as e:
            carb.log_error(f"[GRPCClient] Error in polling task: {e}")
    
    def _parse_refresh_interval(self, refresh_policy: str) -> float:
        """Parse refresh policy to get interval in seconds"""
        if refresh_policy.startswith("interval:"):
            interval_str = refresh_policy[9:]  # Remove "interval:" prefix
            
            # Parse time units
            if interval_str.endswith("s"):
                return float(interval_str[:-1])
            elif interval_str.endswith("m"):
                return float(interval_str[:-1]) * 60
            elif interval_str.endswith("h"):
                return float(interval_str[:-1]) * 3600
            else:
                return float(interval_str)  # Assume seconds
        
        return 30.0  # Default to 30 seconds
