"""
REST/HTTP protocol client implementation
"""

import asyncio
import json
from typing import Dict, Any, Callable, Optional
import carb

try:
    import aiohttp
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False
    carb.log_warn("[RESTClient] aiohttp not available, REST functionality disabled")

from .base_client import BaseProtocolClient


class RESTClient(BaseProtocolClient):
    """REST/HTTP protocol client"""
    
    def __init__(self):
        super().__init__()
        self._session: Optional[aiohttp.ClientSession] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._poll_callback: Optional[Callable] = None
    
    async def connect(self, config: Dict[str, Any]):
        """Initialize HTTP session"""
        if not HTTP_AVAILABLE:
            raise RuntimeError("HTTP client not available - install aiohttp package")
        
        self._validate_config(config, ["uri"])
        self._config = config
        
        try:
            # Create session with auth headers
            headers = self._get_auth_headers(config)
            timeout = aiohttp.ClientTimeout(total=30)
            
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout
            )
            
            self._connected = True
            carb.log_info(f"[RESTClient] Session initialized for {config['uri']}")
            
        except Exception as e:
            self._connected = False
            raise RuntimeError(f"Failed to initialize REST session: {e}")
    
    async def disconnect(self):
        """Close HTTP session"""
        try:
            if self._poll_task:
                self._poll_task.cancel()
                self._poll_task = None
            
            if self._session:
                await self._session.close()
                self._session = None
            
            self._connected = False
            carb.log_info(f"[RESTClient] Session closed")
            
        except Exception as e:
            carb.log_error(f"[RESTClient] Error during disconnect: {e}")
    
    async def read(self, config: Dict[str, Any]) -> Any:
        """Perform HTTP request"""
        if not self._connected or not self._session:
            raise RuntimeError("REST client not connected")
        
        uri = config["uri"]
        method = config.get("method", "GET").upper()
        
        try:
            async with self._session.request(method, uri) as response:
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}: {response.reason}")
                
                # Try to get JSON response
                try:
                    data = await response.json()
                except (aiohttp.ContentTypeError, json.JSONDecodeError):
                    data = await response.text()
                
                # Apply JSONPath if specified
                json_path = config.get("jsonPath")
                if json_path and isinstance(data, dict):
                    data = self._apply_json_path(data, json_path)
                
                return data
                
        except Exception as e:
            raise RuntimeError(f"Failed to perform REST request to {uri}: {e}")
    
    async def write(self, config: Dict[str, Any], value: Any) -> bool:
        """Perform HTTP write request (POST/PUT/PATCH)"""
        if not self._connected or not self._session:
            raise RuntimeError("REST client not connected")
        
        uri = config["uri"]
        method = config.get("method", "POST").upper()
        
        if method not in ["POST", "PUT", "PATCH"]:
            raise ValueError(f"Write operation requires POST, PUT, or PATCH method, got {method}")
        
        try:
            # Prepare payload
            if isinstance(value, (dict, list)):
                data = json.dumps(value)
                headers = {"Content-Type": "application/json"}
            else:
                data = str(value)
                headers = {"Content-Type": "text/plain"}
            
            async with self._session.request(method, uri, data=data, headers=headers) as response:
                return response.status < 400
                
        except Exception as e:
            carb.log_error(f"[RESTClient] Failed to write to {uri}: {e}")
            return False
    
    async def start_stream(self, config: Dict[str, Any], callback: Callable[[Any], None]):
        """Start polling REST endpoint"""
        if not self._connected:
            raise RuntimeError("REST client not connected")
        
        self._poll_callback = callback
        
        # Get refresh policy (default to 30 seconds)
        refresh_policy = config.get("refreshPolicy", "interval:30s")
        interval = self._parse_refresh_interval(refresh_policy)
        
        # Start polling task
        self._poll_task = asyncio.create_task(self._poll_endpoint(config, interval))
    
    async def stop_stream(self):
        """Stop polling REST endpoint"""
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        
        self._poll_callback = None
    
    async def _poll_endpoint(self, config: Dict[str, Any], interval: float):
        """Internal task to poll REST endpoint"""
        try:
            while True:
                try:
                    value = await self.read(config)
                    if self._poll_callback:
                        await self._poll_callback(value)
                except Exception as e:
                    carb.log_error(f"[RESTClient] Error polling endpoint: {e}")
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            carb.log_info(f"[RESTClient] Polling task cancelled")
        except Exception as e:
            carb.log_error(f"[RESTClient] Error in polling task: {e}")
    
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
    
    def _apply_json_path(self, data: dict, json_path: str) -> Any:
        """Apply JSONPath expression to extract data"""
        try:
            # Simple JSONPath implementation for basic paths like $.field or $.field.subfield
            if json_path.startswith("$."):
                path_parts = json_path[2:].split(".")
                result = data
                
                for part in path_parts:
                    if isinstance(result, dict) and part in result:
                        result = result[part]
                    else:
                        return None
                
                return result
            else:
                carb.log_warn(f"[RESTClient] Unsupported JSONPath expression: {json_path}")
                return data
                
        except Exception as e:
            carb.log_error(f"[RESTClient] Error applying JSONPath {json_path}: {e}")
            return data
