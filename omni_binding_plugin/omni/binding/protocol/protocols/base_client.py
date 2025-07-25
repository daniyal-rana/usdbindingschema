"""
Base protocol client interface
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional


class BaseProtocolClient(ABC):
    """Base class for all protocol clients"""
    
    def __init__(self):
        self._connected = False
        self._config: Optional[Dict[str, Any]] = None
    
    @property
    def connected(self) -> bool:
        """Check if client is connected"""
        return self._connected
    
    @abstractmethod
    async def connect(self, config: Dict[str, Any]):
        """Connect to the protocol endpoint"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the protocol endpoint"""
        pass
    
    @abstractmethod
    async def read(self, config: Dict[str, Any]) -> Any:
        """Perform a one-time read operation"""
        pass
    
    async def write(self, config: Dict[str, Any], value: Any) -> bool:
        """Perform a write operation (optional)"""
        raise NotImplementedError("Write operation not supported")
    
    async def start_stream(self, config: Dict[str, Any], callback: Callable[[Any], None]):
        """Start streaming data (optional)"""
        raise NotImplementedError("Streaming not supported")
    
    async def stop_stream(self):
        """Stop streaming data (optional)"""
        raise NotImplementedError("Streaming not supported")
    
    def _validate_config(self, config: Dict[str, Any], required_fields: list):
        """Validate that required configuration fields are present"""
        missing_fields = []
        for field in required_fields:
            if field not in config:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {missing_fields}")
    
    def _get_auth_headers(self, config: Dict[str, Any]) -> Dict[str, str]:
        """Generate authentication headers based on config"""
        headers = {}
        auth_method = config.get("authMethod", "none")
        auth_profile = config.get("authProfile")
        
        if auth_method == "none" or not auth_profile:
            return headers
        
        try:
            from ..auth_manager import AuthenticationManager
            auth_manager = AuthenticationManager()
            headers = auth_manager.get_auth_headers(auth_profile, auth_method)
        except Exception as e:
            carb.log_error(f"[BaseClient] Error getting auth headers: {e}")
            # Fallback to simple implementation for backwards compatibility
            if auth_method == "apikey":
                headers["Authorization"] = f"ApiKey {auth_profile}"
            elif auth_method == "oauth2":
                headers["Authorization"] = f"Bearer {auth_profile}"
        
        return headers
