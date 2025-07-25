"""
SQL protocol client implementation
"""

import asyncio
import json
from typing import Dict, Any, Callable, Optional, List
import carb

try:
    import aioodbc
    SQL_AVAILABLE = True
except ImportError:
    SQL_AVAILABLE = False
    carb.log_warn("[SQLClient] aioodbc not available, SQL functionality disabled")

from .base_client import BaseProtocolClient


class SQLClient(BaseProtocolClient):
    """SQL protocol client"""
    
    def __init__(self):
        super().__init__()
        self._connection: Optional[Any] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._poll_callback: Optional[Callable] = None
    
    async def connect(self, config: Dict[str, Any]):
        """Connect to SQL database"""
        if not SQL_AVAILABLE:
            raise RuntimeError("SQL client not available - install aioodbc package")
        
        self._validate_config(config, ["uri"])
        self._config = config
        
        try:
            # Get connection string from auth manager if auth profile is specified
            auth_profile = config.get("authProfile")
            connection_string = None
            
            if auth_profile:
                try:
                    from ..auth_manager import AuthenticationManager
                    auth_manager = AuthenticationManager()
                    connection_string = auth_manager.get_sql_connection_string(auth_profile)
                    carb.log_info(f"[SQLClient] Using auth profile connection string: {auth_profile}")
                except Exception as e:
                    carb.log_error(f"[SQLClient] Error loading auth profile: {e}")
            
            if not connection_string:
                # Parse SQL connection string from URI
                uri = config["uri"]
                if uri.startswith("sql://"):
                    connection_string = uri[6:]  # Remove "sql://" prefix
                else:
                    connection_string = uri
            
            # Connect to database
            self._connection = await aioodbc.connect(dsn=connection_string)
            self._connected = True
            
            carb.log_info(f"[SQLClient] Connected to database")
            
        except Exception as e:
            self._connected = False
            raise RuntimeError(f"Failed to connect to SQL database: {e}")
    
    async def disconnect(self):
        """Disconnect from SQL database"""
        try:
            if self._poll_task:
                self._poll_task.cancel()
                self._poll_task = None
            
            if self._connection:
                await self._connection.close()
                self._connection = None
            
            self._connected = False
            carb.log_info(f"[SQLClient] Disconnected from database")
            
        except Exception as e:
            carb.log_error(f"[SQLClient] Error during disconnect: {e}")
    
    async def read(self, config: Dict[str, Any]) -> Any:
        """Execute SQL query and return results"""
        if not self._connected or not self._connection:
            raise RuntimeError("SQL client not connected")
        
        query = config.get("query")
        if not query:
            raise ValueError("SQL operation requires 'query' field")
        
        try:
            async with self._connection.cursor() as cursor:
                await cursor.execute(query)
                
                # Fetch all results
                rows = await cursor.fetchall()
                
                if not rows:
                    return None
                
                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Convert to list of dictionaries
                if len(rows) == 1 and len(rows[0]) == 1:
                    # Single value result
                    return rows[0][0]
                elif len(rows) == 1:
                    # Single row result
                    return dict(zip(columns, rows[0]))
                else:
                    # Multiple rows result
                    return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            raise RuntimeError(f"Failed to execute SQL query: {e}")
    
    async def write(self, config: Dict[str, Any], value: Any) -> bool:
        """Execute SQL write operation"""
        if not self._connected or not self._connection:
            raise RuntimeError("SQL client not connected")
        
        query = config.get("query")
        if not query:
            raise ValueError("SQL write operation requires 'query' field")
        
        try:
            async with self._connection.cursor() as cursor:
                # If value is a dictionary, use it for parameter substitution
                if isinstance(value, dict):
                    await cursor.execute(query, value)
                else:
                    # Simple value substitution
                    await cursor.execute(query, (value,))
                
                await self._connection.commit()
                return True
                
        except Exception as e:
            carb.log_error(f"[SQLClient] Failed to execute write query: {e}")
            return False
    
    async def start_stream(self, config: Dict[str, Any], callback: Callable[[Any], None]):
        """Start polling SQL query"""
        if not self._connected:
            raise RuntimeError("SQL client not connected")
        
        self._poll_callback = callback
        
        # Get refresh policy (default to 60 seconds for SQL)
        refresh_policy = config.get("refreshPolicy", "interval:60s")
        interval = self._parse_refresh_interval(refresh_policy)
        
        # Start polling task
        self._poll_task = asyncio.create_task(self._poll_query(config, interval))
    
    async def stop_stream(self):
        """Stop polling SQL query"""
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        
        self._poll_callback = None
    
    async def _poll_query(self, config: Dict[str, Any], interval: float):
        """Internal task to poll SQL query"""
        try:
            while True:
                try:
                    value = await self.read(config)
                    if self._poll_callback:
                        await self._poll_callback(value)
                except Exception as e:
                    carb.log_error(f"[SQLClient] Error polling query: {e}")
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            carb.log_info(f"[SQLClient] Polling task cancelled")
        except Exception as e:
            carb.log_error(f"[SQLClient] Error in polling task: {e}")
    
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
        
        return 60.0  # Default to 60 seconds
