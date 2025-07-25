"""
File protocol client implementation
"""

import asyncio
import json
import os
from typing import Dict, Any, Callable, Optional
from pathlib import Path
import carb

from .base_client import BaseProtocolClient


class FileClient(BaseProtocolClient):
    """File protocol client"""
    
    def __init__(self):
        super().__init__()
        self._watch_task: Optional[asyncio.Task] = None
        self._watch_callback: Optional[Callable] = None
        self._last_modified: Optional[float] = None
    
    async def connect(self, config: Dict[str, Any]):
        """Initialize file client"""
        self._validate_config(config, ["uri"])
        self._config = config
        
        try:
            # Parse file URI
            uri = config["uri"]
            if uri.startswith("file://"):
                self._file_path = uri[7:]  # Remove "file://" prefix
            else:
                self._file_path = uri
            
            # Check if file exists and is readable
            if not os.path.exists(self._file_path):
                carb.log_warn(f"[FileClient] File does not exist: {self._file_path}")
            elif not os.access(self._file_path, os.R_OK):
                raise RuntimeError(f"File is not readable: {self._file_path}")
            
            self._connected = True
            carb.log_info(f"[FileClient] Connected to file: {self._file_path}")
            
        except Exception as e:
            self._connected = False
            raise RuntimeError(f"Failed to initialize file client: {e}")
    
    async def disconnect(self):
        """Stop file watching"""
        try:
            if self._watch_task:
                self._watch_task.cancel()
                self._watch_task = None
            
            self._connected = False
            self._last_modified = None
            carb.log_info(f"[FileClient] Disconnected")
            
        except Exception as e:
            carb.log_error(f"[FileClient] Error during disconnect: {e}")
    
    async def read(self, config: Dict[str, Any]) -> Any:
        """Read file contents"""
        if not self._connected:
            raise RuntimeError("File client not connected")
        
        try:
            if not os.path.exists(self._file_path):
                return None
            
            # Read file contents
            with open(self._file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
            
            # Try to parse as JSON if file has .json extension
            if self._file_path.lower().endswith('.json'):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    carb.log_warn(f"[FileClient] Failed to parse JSON from {self._file_path}")
                    return content
            
            # Try to parse as number if it looks like one
            try:
                if '.' in content:
                    return float(content)
                else:
                    return int(content)
            except ValueError:
                return content
                
        except Exception as e:
            raise RuntimeError(f"Failed to read file {self._file_path}: {e}")
    
    async def write(self, config: Dict[str, Any], value: Any) -> bool:
        """Write to file"""
        if not self._connected:
            raise RuntimeError("File client not connected")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
            
            # Prepare content
            if self._file_path.lower().endswith('.json'):
                content = json.dumps(value, indent=2)
            else:
                content = str(value)
            
            # Write to file
            with open(self._file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            
            return True
            
        except Exception as e:
            carb.log_error(f"[FileClient] Failed to write to file {self._file_path}: {e}")
            return False
    
    async def start_stream(self, config: Dict[str, Any], callback: Callable[[Any], None]):
        """Start watching file for changes"""
        if not self._connected:
            raise RuntimeError("File client not connected")
        
        self._watch_callback = callback
        
        # Get refresh policy (default to 5 seconds for files)
        refresh_policy = config.get("refreshPolicy", "interval:5s")
        interval = self._parse_refresh_interval(refresh_policy)
        
        # Get initial modification time
        if os.path.exists(self._file_path):
            self._last_modified = os.path.getmtime(self._file_path)
        
        # Start watching task
        self._watch_task = asyncio.create_task(self._watch_file(config, interval))
    
    async def stop_stream(self):
        """Stop watching file"""
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None
        
        self._watch_callback = None
        self._last_modified = None
    
    async def _watch_file(self, config: Dict[str, Any], interval: float):
        """Internal task to watch file for changes"""
        try:
            while True:
                try:
                    if os.path.exists(self._file_path):
                        current_modified = os.path.getmtime(self._file_path)
                        
                        # Check if file was modified
                        if self._last_modified is None or current_modified > self._last_modified:
                            self._last_modified = current_modified
                            
                            # Read file and notify callback
                            value = await self.read(config)
                            if self._watch_callback:
                                await self._watch_callback(value)
                    
                except Exception as e:
                    carb.log_error(f"[FileClient] Error watching file: {e}")
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            carb.log_info(f"[FileClient] File watching task cancelled")
        except Exception as e:
            carb.log_error(f"[FileClient] Error in file watching task: {e}")
    
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
        
        return 5.0  # Default to 5 seconds
