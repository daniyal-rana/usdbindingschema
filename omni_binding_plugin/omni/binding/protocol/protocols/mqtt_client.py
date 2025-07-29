"""
MQTT protocol client implementation
"""

import asyncio
import json
from typing import Dict, Any, Callable, Optional

# Handle carb import for testing outside Omniverse
try:
    import carb
except ImportError:
    # Use mock carb for testing
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
    try:
        import mock_carb as carb
    except ImportError:
        # Fallback if mock_carb isn't available
        class MockCarb:
            @staticmethod
            def log_info(msg): print(f"[INFO] {msg}")
            @staticmethod
            def log_warn(msg): print(f"[WARN] {msg}")
            @staticmethod
            def log_error(msg): print(f"[ERROR] {msg}")
        carb = MockCarb()

try:
    import aiomqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    carb.log_warn("[MQTTClient] aiomqtt not available, MQTT functionality disabled")

from .base_client import BaseProtocolClient


class MQTTClient(BaseProtocolClient):
    """MQTT protocol client"""
    
    def __init__(self):
        super().__init__()
        self._client: Optional[aiomqtt.Client] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._stream_callback: Optional[Callable] = None
    
    async def connect(self, config: Dict[str, Any]):
        """Connect to MQTT broker"""
        if not MQTT_AVAILABLE:
            raise RuntimeError("MQTT client not available - install aiomqtt package")
        
        self._validate_config(config, ["uri"])
        self._config = config
        
        try:
            # Parse URI
            uri = config["uri"]
            if uri.startswith("mqtt://"):
                host = uri[7:].split(":")[0]
                port = int(uri[7:].split(":")[1]) if ":" in uri[7:] else 1883
                use_tls = False
            elif uri.startswith("mqtts://"):
                host = uri[8:].split(":")[0]
                port = int(uri[8:].split(":")[1]) if ":" in uri[8:] else 8883
                use_tls = True
            else:
                raise ValueError(f"Invalid MQTT URI format: {uri}")
            
            # Handle mTLS authentication
            tls_context = None
            if use_tls:
                import ssl
                tls_context = ssl.create_default_context()
                
                auth_method = config.get("authMethod")
                auth_profile = config.get("authProfile")
                
                if auth_method == "mtls" and auth_profile:
                    try:
                        from ..auth_manager import AuthenticationManager
                        auth_manager = AuthenticationManager()
                        mtls_config = auth_manager.get_mtls_config(auth_profile)
                        
                        if mtls_config:
                            cert_path, key_path, ca_path = mtls_config
                            tls_context.load_cert_chain(cert_path, key_path)
                            if ca_path:
                                tls_context.load_verify_locations(ca_path)
                            carb.log_info(f"[MQTTClient] Loaded mTLS certificates for {auth_profile}")
                    except Exception as e:
                        carb.log_error(f"[MQTTClient] Error loading mTLS config: {e}")
            
            # Create client
            self._client = aiomqtt.Client(
                hostname=host,
                port=port,
                tls_context=tls_context
            )
            
            await self._client.__aenter__()
            self._connected = True
            
            carb.log_info(f"[MQTTClient] Connected to {host}:{port}")
            
        except Exception as e:
            self._connected = False
            raise RuntimeError(f"Failed to connect to MQTT broker: {e}")
    
    async def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            if self._stream_task:
                self._stream_task.cancel()
                self._stream_task = None
            
            if self._client:
                await self._client.__aexit__(None, None, None)
                self._client = None
            
            self._connected = False
            carb.log_info(f"[MQTTClient] Disconnected")
            
        except Exception as e:
            carb.log_error(f"[MQTTClient] Error during disconnect: {e}")
    
    async def read(self, config: Dict[str, Any]) -> Any:
        """Perform a one-time read from MQTT topic"""
        if not self._connected or not self._client:
            raise RuntimeError("MQTT client not connected")
        
        topic = config.get("topic")
        if not topic:
            raise ValueError("MQTT read operation requires 'topic' field")
        
        try:
            # Subscribe to topic
            await self._client.subscribe(topic)
            
            # Wait for one message with timeout
            async with asyncio.timeout(10):  # 10 second timeout
                async for message in self._client.messages:
                    if message.topic.matches(topic):
                        # Unsubscribe after getting message
                        await self._client.unsubscribe(topic)
                        
                        # Try to parse as JSON, fallback to string
                        try:
                            return json.loads(message.payload.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            return message.payload.decode("utf-8", errors="replace")
            
            raise TimeoutError("No message received within timeout period")
            
        except Exception as e:
            raise RuntimeError(f"Failed to read from MQTT topic {topic}: {e}")
    
    async def write(self, config: Dict[str, Any], value: Any) -> bool:
        """Publish a message to MQTT topic"""
        if not self._connected or not self._client:
            raise RuntimeError("MQTT client not connected")
        
        topic = config.get("topic")
        if not topic:
            raise ValueError("MQTT write operation requires 'topic' field")
        
        try:
            # Convert value to JSON if it's not a string
            if isinstance(value, str):
                payload = value
            else:
                payload = json.dumps(value)
            
            await self._client.publish(topic, payload)
            return True
            
        except Exception as e:
            carb.log_error(f"[MQTTClient] Failed to publish to topic {topic}: {e}")
            return False
    
    async def start_stream(self, config: Dict[str, Any], callback: Callable[[Any], None]):
        """Start streaming from MQTT topic"""
        if not self._connected or not self._client:
            raise RuntimeError("MQTT client not connected")
        
        topic = config.get("topic")
        if not topic:
            raise ValueError("MQTT streaming requires 'topic' field")
        
        self._stream_callback = callback
        
        try:
            # Subscribe to topic
            await self._client.subscribe(topic)
            
            # Start streaming task
            self._stream_task = asyncio.create_task(self._stream_messages(topic))
            
        except Exception as e:
            raise RuntimeError(f"Failed to start MQTT stream for topic {topic}: {e}")
    
    async def stop_stream(self):
        """Stop streaming from MQTT topic"""
        if self._stream_task:
            self._stream_task.cancel()
            self._stream_task = None
        
        self._stream_callback = None
    
    async def _stream_messages(self, topic: str):
        """Internal task to stream MQTT messages"""
        try:
            async for message in self._client.messages:
                if message.topic.matches(topic) and self._stream_callback:
                    try:
                        # Try to parse as JSON, fallback to string
                        try:
                            value = json.loads(message.payload.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            value = message.payload.decode("utf-8", errors="replace")
                        
                        await self._stream_callback(value)
                        
                    except Exception as e:
                        carb.log_error(f"[MQTTClient] Error processing message: {e}")
                        
        except asyncio.CancelledError:
            carb.log_info(f"[MQTTClient] Stream task cancelled for topic {topic}")
        except Exception as e:
            carb.log_error(f"[MQTTClient] Error in stream task: {e}")
