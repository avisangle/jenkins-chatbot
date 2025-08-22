"""
Configuration Manager for Universal MCP Architecture
Handles dynamic configuration, validation, and multiple server setup
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import structlog

from app.config import settings
from app.services.mcp_universal_client import MCPServerConfig, TransportType

logger = structlog.get_logger(__name__)

@dataclass
class UniversalMCPConfig:
    """Universal MCP configuration"""
    discovery_enabled: bool = True
    fallback_enabled: bool = True
    load_balancing: bool = False
    connection_pooling: bool = True
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    health_check_interval: int = 60
    max_concurrent_connections: int = 10
    servers: List[MCPServerConfig] = None
    
    def __post_init__(self):
        if self.servers is None:
            self.servers = []

class ConfigManager:
    """Manages universal MCP configuration with validation and defaults"""
    
    def __init__(self):
        self.config: Optional[UniversalMCPConfig] = None
        self._config_file_path = os.getenv("MCP_CONFIG_FILE", settings.MCP_CONFIG_FILE)
        
    def load_configuration(self) -> UniversalMCPConfig:
        """Load and validate MCP configuration"""
        
        logger.info("Loading MCP configuration")
        
        # Load from JSON file (primary source)
        file_config = self._load_from_file()
        
        # Get environment overrides (settings only)
        env_overrides = self._load_from_environment()
        
        # Apply environment overrides to file config
        final_config = self._apply_environment_overrides(file_config, env_overrides)
        
        # Validate configuration
        validated_config = self._validate_configuration(final_config)
        
        # Set up default server if none configured
        if not validated_config.servers:
            default_server = self._create_default_server()
            validated_config.servers.append(default_server)
        
        self.config = validated_config
        
        logger.info("MCP configuration loaded", 
                   server_count=len(validated_config.servers),
                   discovery_enabled=validated_config.discovery_enabled)
        
        return validated_config
    
    def _load_from_file(self) -> Optional[UniversalMCPConfig]:
        """Load configuration from JSON file"""
        
        try:
            if os.path.exists(self._config_file_path):
                with open(self._config_file_path, 'r') as f:
                    config_data = json.load(f)
                
                # Convert servers to MCPServerConfig objects
                servers = []
                for server_data in config_data.get('servers', []):
                    # Remove comment fields from server data
                    clean_server_data = {k: v for k, v in server_data.items() 
                                       if not k.startswith('_')}
                    servers.append(MCPServerConfig(**clean_server_data))
                
                # Remove comment fields from main config
                clean_config_data = {k: v for k, v in config_data.items() 
                                   if not k.startswith('_')}
                clean_config_data['servers'] = servers
                
                return UniversalMCPConfig(**clean_config_data)
                
        except Exception as e:
            logger.warning("Failed to load config from file", 
                          file=self._config_file_path, 
                          error=str(e))
        
        return None
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration defaults from environment variables (settings only, no servers)"""
        
        return {
            'discovery_enabled': getattr(settings, 'MCP_DISCOVERY_ENABLED', True),
            'fallback_enabled': getattr(settings, 'MCP_FALLBACK_ENABLED', True),
            'load_balancing': getattr(settings, 'MCP_LOAD_BALANCING', False),
            'connection_pooling': getattr(settings, 'MCP_CONNECTION_POOLING', True),
            'cache_enabled': getattr(settings, 'MCP_CACHE_ENABLED', True),
            'cache_ttl_seconds': getattr(settings, 'MCP_CACHE_TTL_SECONDS', 300),
            'health_check_interval': getattr(settings, 'MCP_HEALTH_CHECK_INTERVAL', 60),
            'max_concurrent_connections': getattr(settings, 'MCP_MAX_CONCURRENT_CONNECTIONS', 10),
        }
    
    def _apply_environment_overrides(self, file_config: Optional[UniversalMCPConfig], 
                                   env_overrides: Dict[str, Any]) -> UniversalMCPConfig:
        """Apply environment variable overrides to file configuration"""
        
        if not file_config:
            # Create default config with environment overrides
            config_data = env_overrides.copy()
            config_data['servers'] = []  # No servers from env
            return UniversalMCPConfig(**config_data)
        
        # Apply environment overrides to file config
        for key, value in env_overrides.items():
            if hasattr(file_config, key):
                # Only override if the environment value is different from the default
                current_default = getattr(UniversalMCPConfig(), key, None)
                if value != current_default:
                    setattr(file_config, key, value)
        
        return file_config
    
    def _validate_configuration(self, config: UniversalMCPConfig) -> UniversalMCPConfig:
        """Validate and fix configuration issues"""
        
        # Validate server configurations
        valid_servers = []
        
        for server in config.servers:
            if self._validate_server_config(server):
                valid_servers.append(server)
            else:
                logger.warning("Invalid server configuration removed", 
                              server_name=server.name)
        
        config.servers = valid_servers
        
        # Validate numeric settings
        config.cache_ttl_seconds = max(60, config.cache_ttl_seconds)  # Min 1 minute
        config.health_check_interval = max(30, config.health_check_interval)  # Min 30 seconds
        config.max_concurrent_connections = max(1, min(100, config.max_concurrent_connections))  # 1-100
        
        return config
    
    def _validate_server_config(self, server: MCPServerConfig) -> bool:
        """Validate individual server configuration"""
        
        # Check required fields
        if not server.name or not server.url:
            logger.error("Server missing required fields", name=server.name, url=server.url)
            return False
        
        # Validate transport type
        try:
            TransportType(server.transport)
        except ValueError:
            logger.error("Invalid transport type", transport=server.transport)
            return False
        
        # Validate timeout
        if server.timeout <= 0:
            logger.error("Invalid timeout", timeout=server.timeout)
            return False
        
        # Validate URL format
        if not (server.url.startswith('http://') or server.url.startswith('https://') or 
               server.url.startswith('ws://') or server.url.startswith('wss://') or
               server.url.startswith('unix:')):
            logger.error("Invalid URL format", url=server.url)
            return False
        
        return True
    
    def _create_default_server(self) -> MCPServerConfig:
        """Create default Jenkins MCP server configuration"""
        
        return MCPServerConfig(
            name="jenkins-default",
            url=f"http://{settings.MCP_HTTP_HOST}:{settings.MCP_HTTP_PORT}{settings.MCP_HTTP_ENDPOINT}",
            transport=TransportType.HTTP,
            priority=1,
            timeout=settings.MCP_CLIENT_TIMEOUT,
            retry_count=3,
            enabled=settings.MCP_ENABLED
        )
    
    def save_configuration(self, config: UniversalMCPConfig) -> bool:
        """Save configuration to file"""
        
        try:
            # Convert to serializable format
            config_dict = asdict(config)
            
            # Convert server configs to dicts
            config_dict['servers'] = [asdict(server) for server in config.servers]
            
            # Write to file
            os.makedirs(os.path.dirname(self._config_file_path), exist_ok=True)
            with open(self._config_file_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            logger.info("Configuration saved", file=self._config_file_path)
            return True
            
        except Exception as e:
            logger.error("Failed to save configuration", error=str(e))
            return False
    
    def add_server(self, server_config: MCPServerConfig) -> bool:
        """Add a new server configuration"""
        
        if not self.config:
            self.load_configuration()
        
        # Validate new server
        if not self._validate_server_config(server_config):
            return False
        
        # Check for duplicate names
        existing_names = {server.name for server in self.config.servers}
        if server_config.name in existing_names:
            logger.error("Server name already exists", name=server_config.name)
            return False
        
        self.config.servers.append(server_config)
        logger.info("Server added", name=server_config.name, url=server_config.url)
        
        return True
    
    def remove_server(self, server_name: str) -> bool:
        """Remove a server configuration"""
        
        if not self.config:
            self.load_configuration()
        
        original_count = len(self.config.servers)
        self.config.servers = [s for s in self.config.servers if s.name != server_name]
        
        if len(self.config.servers) < original_count:
            logger.info("Server removed", name=server_name)
            return True
        else:
            logger.warning("Server not found for removal", name=server_name)
            return False
    
    def update_server(self, server_name: str, updates: Dict[str, Any]) -> bool:
        """Update existing server configuration"""
        
        if not self.config:
            self.load_configuration()
        
        for server in self.config.servers:
            if server.name == server_name:
                # Apply updates
                for key, value in updates.items():
                    if hasattr(server, key):
                        setattr(server, key, value)
                    else:
                        logger.warning("Unknown server property", property=key)
                
                # Validate updated configuration
                if self._validate_server_config(server):
                    logger.info("Server updated", name=server_name, updates=updates)
                    return True
                else:
                    logger.error("Server update failed validation", name=server_name)
                    return False
        
        logger.warning("Server not found for update", name=server_name)
        return False
    
    def get_server_by_name(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get server configuration by name"""
        
        if not self.config:
            self.load_configuration()
        
        for server in self.config.servers:
            if server.name == server_name:
                return server
        
        return None
    
    def get_servers_by_priority(self) -> List[MCPServerConfig]:
        """Get servers sorted by priority (highest first)"""
        
        if not self.config:
            self.load_configuration()
        
        return sorted(self.config.servers, key=lambda s: s.priority, reverse=True)
    
    def get_enabled_servers(self) -> List[MCPServerConfig]:
        """Get only enabled servers"""
        
        if not self.config:
            self.load_configuration()
        
        return [server for server in self.config.servers if server.enabled]
    
    def reload_configuration(self) -> UniversalMCPConfig:
        """Reload configuration from sources"""
        
        logger.info("Reloading MCP configuration")
        self.config = None
        return self.load_configuration()
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get configuration summary for monitoring/debugging"""
        
        if not self.config:
            self.load_configuration()
        
        return {
            "discovery_enabled": self.config.discovery_enabled,
            "fallback_enabled": self.config.fallback_enabled,
            "load_balancing": self.config.load_balancing,
            "connection_pooling": self.config.connection_pooling,
            "cache_enabled": self.config.cache_enabled,
            "cache_ttl_seconds": self.config.cache_ttl_seconds,
            "health_check_interval": self.config.health_check_interval,
            "max_concurrent_connections": self.config.max_concurrent_connections,
            "total_servers": len(self.config.servers),
            "enabled_servers": len([s for s in self.config.servers if s.enabled]),
            "servers": [
                {
                    "name": server.name,
                    "url": server.url,
                    "transport": server.transport,
                    "priority": server.priority,
                    "enabled": server.enabled,
                    "timeout": server.timeout
                }
                for server in self.config.servers
            ]
        }

# Global configuration manager instance
config_manager = ConfigManager()