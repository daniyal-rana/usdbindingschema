"""
WebSocket protocol client implementation
"""

import asyncio
import json
from typing import Dict, Any, Callable, Optional
import carb

try:
    import websockets
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    carb.log_warn("[WebSocketClient] websockets not available, WebSocket functionality disabled")

from .base_client import BaseProtocolClient


class WebSocketClient(BaseProtocolClient):
    """WebSocket protocol client"""
    
    def __init__(self):
        super().__init__()
        self._websocket: Optional[Any] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._stream_callback: Optional[Callable] = None
    
    async def connect(self, config: Dict[str, Any]):
        """Connect to WebSocket server"""
        if not WEBSOCKET_AVAILABLE:
            raise RuntimeError("WebSocket client not available - install websockets package")
        
        self._validate_config(config, ["uri"])
        self._config = config
        
        try:
            uri = config["uri"]
            
            # Add authentication headers if needed
            extra_headers = self._get_auth_headers(config)
            
            # Connect to WebSocket
            self._websocket = await websockets.connect(uri, extra_headers=extra_headers)
            self._connected = True
            
            carb.log_info(f"[WebSocketClient] Connected to {uri}")
            
        except Exception as e:
            self._connected = False
            raise RuntimeError(f"Failed to connect to WebSocket server: {e}")
    
    async def disconnect(self):
        """Disconnect from WebSocket server"""
        try:
            if self._stream_task:
                self._stream_task.cancel()
                self._stream_task = None
            
            if self._websocket:
                await self._websocket.close()
                self._websocket = None
            
            self._connected = False
            carb.log_info(f"[WebSocketClient] Disconnected")
            
        except Exception as e:
            carb.log_error(f"[WebSocketClient] Error during disconnect: {e}")
    
    async def read(self, config: Dict[str, Any]) -> Any:
        """Receive one message from WebSocket"""
        if not self._connected or not self._websocket:
            raise RuntimeError("WebSocket client not connected")
        
        try:
            # Send request message if topic is specified
            topic = config.get("topic")
            if topic:
                request = {"action": "subscribe", "topic": topic}
                await self._websocket.send(json.dumps(request))
            
            # Wait for response with timeout
            message = await asyncio.wait_for(self._websocket.recv(), timeout=10)
            
            # Try to parse as JSON, fallback to string
            try:
                return json.loads(message)
            except json.JSONDecodeError:
                return message
                
        except asyncio.TimeoutError:
            raise TimeoutError("No message received within timeout period")
        except Exception as e:
            raise RuntimeError(f"Failed to read from WebSocket: {e}")
    
    async def write(self, config: Dict[str, Any], value: Any) -> bool:
        """Send message to WebSocket"""
        if not self._connected or not self._websocket:
            raise RuntimeError("WebSocket client not connected")
        
        try:
            # Prepare message
            topic = config.get("topic")
            if topic:
                message = {
                    "action": "publish",
                    "topic": topic,
                    "data": value
                }
                await self._websocket.send(json.dumps(message))
            else:
                # Send value directly
                if isinstance(value, str):
                    await self._websocket.send(value)
                else:
                    await self._websocket.send(json.dumps(value))
            
            return True
            
        except Exception as e:
            carb.log_error(f"[WebSocketClient] Failed to send message: {e}")
            return False
    
    async def start_stream(self, config: Dict[str, Any], callback: Callable[[Any], None]):
        """Start streaming from WebSocket"""
        if not self._connected or not self._websocket:
            raise RuntimeError("WebSocket client not connected")
        
        self._stream_callback = callback
        
        try:
            # Send subscription message if topic is specified
            topic = config.get("topic")
            if topic:
                request = {"action": "subscribe", "topic": topic}
                await self._websocket.send(json.dumps(request))
            
            # Start streaming task
            self._stream_task = asyncio.create_task(self._stream_messages())
            
        except Exception as e:
            raise RuntimeError(f"Failed to start WebSocket stream: {e}")
    
    async def stop_stream(self):
        """Stop streaming from WebSocket"""
        if self._stream_task:
            self._stream_task.cancel()
            self._stream_task = None
        
        self._stream_callback = None
    
    async def _stream_messages(self):
        """Internal task to stream WebSocket messages"""
        try:
            async for message in self._websocket:
                if self._stream_callback:
                    try:
                        # Try to parse as JSON, fallback to string
                        try:
                            value = json.loads(message)
                        except json.JSONDecodeError:
                            value = message
                        
                        await self._stream_callback(value)
                        
                    except Exception as e:
                        carb.log_error(f"[WebSocketClient] Error processing message: {e}")
                        
        except asyncio.CancelledError:
            carb.log_info(f"[WebSocketClient] Stream task cancelled")
        except Exception as e:
            carb.log_error(f"[WebSocketClient] Error in stream task: {e}")
