"""
Authentication manager for resolving auth profiles and handling credentials
"""

import json
import os
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import carb

try:
    import aiohttp
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False


class AuthenticationManager:
    """Manages authentication profiles and credential resolution"""
    
    def __init__(self, auth_dir: str = None):
        if auth_dir is None:
            # Default to auth directory relative to this file
            self._auth_dir = Path(__file__).parent.parent / "auth"
        else:
            self._auth_dir = Path(auth_dir)
        
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        self._load_profiles()
    
    def _load_profiles(self):
        """Load authentication profiles from profiles.json"""
        try:
            profiles_file = self._auth_dir / "profiles.json"
            if profiles_file.exists():
                with open(profiles_file, 'r') as f:
                    data = json.load(f)
                    self._profiles = data.get("profiles", {})
                carb.log_info(f"[AuthManager] Loaded {len(self._profiles)} auth profiles")
            else:
                carb.log_warn(f"[AuthManager] Profiles file not found: {profiles_file}")
        except Exception as e:
            carb.log_error(f"[AuthManager] Error loading profiles: {e}")
    
    def get_auth_headers(self, auth_profile: str, auth_method: str = None) -> Dict[str, str]:
        """Get authentication headers for a profile"""
        if not auth_profile or auth_profile not in self._profiles:
            return {}
        
        try:
            profile = self._profiles[auth_profile]
            auth_type = profile.get("type", auth_method)
            
            if auth_type == "oauth2":
                return self._get_oauth2_headers(profile)
            elif auth_type == "apikey":
                return self._get_apikey_headers(profile)
            else:
                carb.log_warn(f"[AuthManager] Unsupported auth type for headers: {auth_type}")
                return {}
                
        except Exception as e:
            carb.log_error(f"[AuthManager] Error getting auth headers for {auth_profile}: {e}")
            return {}
    
    def get_connection_config(self, auth_profile: str) -> Dict[str, Any]:
        """Get connection configuration for protocols like SQL, mTLS"""
        if not auth_profile or auth_profile not in self._profiles:
            return {}
        
        try:
            profile = self._profiles[auth_profile]
            config_file = profile.get("config_file")
            
            if not config_file:
                return {}
            
            config_path = self._auth_dir / config_file
            if not config_path.exists():
                carb.log_warn(f"[AuthManager] Config file not found: {config_path}")
                return {}
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Substitute environment variables
            config = self._substitute_env_vars(config)
            
            return config
            
        except Exception as e:
            carb.log_error(f"[AuthManager] Error getting connection config for {auth_profile}: {e}")
            return {}
    
    def _get_oauth2_headers(self, profile: Dict[str, Any]) -> Dict[str, str]:
        """Get OAuth2 authentication headers"""
        try:
            # Load OAuth2 config
            config_file = profile.get("config_file")
            if not config_file:
                return {}
            
            config_path = self._auth_dir / config_file
            if not config_path.exists():
                return {}
            
            with open(config_path, 'r') as f:
                oauth_config = json.load(f)
            
            # Substitute environment variables
            oauth_config = self._substitute_env_vars(oauth_config)
            
            # Check token cache first
            cache_key = f"oauth2_{profile.get('description', 'unknown')}"
            cached_token = self._get_cached_token(cache_key, oauth_config)
            
            if cached_token:
                token_format = oauth_config.get("token_format", {})
                header_name = token_format.get("header_name", "Authorization")
                header_template = token_format.get("header_value_template", "Bearer {access_token}")
                header_value = header_template.format(access_token=cached_token["access_token"])
                
                headers = {header_name: header_value}
                
                # Add additional headers
                additional_headers = oauth_config.get("additional_headers", {})
                headers.update(additional_headers)
                
                return headers
            
            # If no cached token, we would need to implement OAuth2 flow
            # For now, return empty headers and log a warning
            carb.log_warn(f"[AuthManager] No cached OAuth2 token found for profile. Implement token refresh flow.")
            return {}
            
        except Exception as e:
            carb.log_error(f"[AuthManager] Error getting OAuth2 headers: {e}")
            return {}
    
    def _get_apikey_headers(self, profile: Dict[str, Any]) -> Dict[str, str]:
        """Get API key authentication headers"""
        try:
            # Load API key config
            config_file = profile.get("config_file")
            if not config_file:
                return {}
            
            config_path = self._auth_dir / config_file
            if not config_path.exists():
                return {}
            
            with open(config_path, 'r') as f:
                apikey_config = json.load(f)
            
            # Substitute environment variables
            apikey_config = self._substitute_env_vars(apikey_config)
            
            api_key = apikey_config.get("api_key")
            if not api_key:
                return {}
            
            key_name = apikey_config.get("key_name", "X-API-Key")
            key_prefix = apikey_config.get("key_prefix", "")
            key_value = f"{key_prefix}{api_key}"
            
            headers = {key_name: key_value}
            
            # Add additional headers
            additional_headers = apikey_config.get("additional_headers", {})
            headers.update(additional_headers)
            
            return headers
            
        except Exception as e:
            carb.log_error(f"[AuthManager] Error getting API key headers: {e}")
            return {}
    
    def _get_cached_token(self, cache_key: str, oauth_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached OAuth2 token if valid"""
        try:
            token_cache_config = oauth_config.get("token_cache", {})
            if not token_cache_config.get("enabled", False):
                return None
            
            cache_file = token_cache_config.get("cache_file")
            if not cache_file:
                return None
            
            cache_path = self._auth_dir / cache_file
            if not cache_path.exists():
                return None
            
            with open(cache_path, 'r') as f:
                token_data = json.load(f)
            
            # Check if token is still valid
            expires_at = token_data.get("expires_at", 0)
            refresh_threshold = token_cache_config.get("refresh_threshold_seconds", 300)
            
            import time
            if time.time() + refresh_threshold < expires_at:
                return token_data
            
            return None
            
        except Exception as e:
            carb.log_warn(f"[AuthManager] Error reading cached token: {e}")
            return None
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """Recursively substitute environment variables in config"""
        if isinstance(config, str):
            # Handle ${VAR_NAME} syntax
            import re
            def replace_var(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))
            
            return re.sub(r'\$\{([^}]+)\}', replace_var, config)
        
        elif isinstance(config, dict):
            return {key: self._substitute_env_vars(value) for key, value in config.items()}
        
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        
        else:
            return config
    
    def get_mtls_config(self, auth_profile: str) -> Optional[Tuple[str, str, str]]:
        """Get mTLS certificate paths (cert_path, key_path, ca_path)"""
        try:
            if auth_profile not in self._profiles:
                return None
            
            profile = self._profiles[auth_profile]
            if profile.get("type") != "mtls":
                return None
            
            config = self.get_connection_config(auth_profile)
            if not config:
                return None
            
            cert_path = config.get("client_cert_path")
            key_path = config.get("client_key_path")
            ca_path = config.get("ca_cert_path")
            
            if cert_path and key_path:
                # Make paths absolute relative to auth directory
                cert_dir = self._auth_dir / Path(profile.get("config_file", "")).parent
                
                if not os.path.isabs(cert_path):
                    cert_path = cert_dir / cert_path
                if not os.path.isabs(key_path):
                    key_path = cert_dir / key_path
                if ca_path and not os.path.isabs(ca_path):
                    ca_path = cert_dir / ca_path
                
                return (str(cert_path), str(key_path), str(ca_path) if ca_path else None)
            
            return None
            
        except Exception as e:
            carb.log_error(f"[AuthManager] Error getting mTLS config for {auth_profile}: {e}")
            return None
    
    def get_sql_connection_string(self, auth_profile: str) -> Optional[str]:
        """Get SQL connection string"""
        try:
            if auth_profile not in self._profiles:
                return None
            
            profile = self._profiles[auth_profile]
            if profile.get("type") != "connection_string":
                return None
            
            config = self.get_connection_config(auth_profile)
            if not config:
                return None
            
            connection_string = config.get("connection_string")
            if connection_string:
                # Environment variable substitution already done in get_connection_config
                return connection_string
            
            return None
            
        except Exception as e:
            carb.log_error(f"[AuthManager] Error getting SQL connection string for {auth_profile}: {e}")
            return None
    
    def list_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get list of all available auth profiles"""
        return self._profiles.copy()
    
    def validate_profile(self, auth_profile: str) -> Tuple[bool, str]:
        """Validate an auth profile configuration"""
        if not auth_profile:
            return False, "No auth profile specified"
        
        if auth_profile not in self._profiles:
            return False, f"Auth profile '{auth_profile}' not found"
        
        try:
            profile = self._profiles[auth_profile]
            config = self.get_connection_config(auth_profile)
            
            auth_type = profile.get("type")
            if not auth_type:
                return False, "Auth type not specified in profile"
            
            if auth_type in ["oauth2", "apikey"]:
                # Check if we can get headers
                headers = self.get_auth_headers(auth_profile)
                if not headers:
                    return False, f"Could not generate auth headers for {auth_type}"
            
            elif auth_type == "mtls":
                # Check certificate files
                mtls_config = self.get_mtls_config(auth_profile)
                if not mtls_config:
                    return False, "Could not load mTLS certificate configuration"
                
                cert_path, key_path, ca_path = mtls_config
                if not os.path.exists(cert_path):
                    return False, f"Client certificate not found: {cert_path}"
                if not os.path.exists(key_path):
                    return False, f"Private key not found: {key_path}"
            
            elif auth_type == "connection_string":
                # Check connection string
                conn_str = self.get_sql_connection_string(auth_profile)
                if not conn_str:
                    return False, "Could not generate connection string"
            
            return True, "Profile validation successful"
            
        except Exception as e:
            return False, f"Profile validation error: {e}"
