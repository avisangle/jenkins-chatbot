"""
Universal MCP Client - Works with ANY MCP Server
Provides dynamic tool discovery, schema normalization, and connection management
"""

import asyncio
import json
import httpx
from typing import Dict, List, Optional, Any, Union, Protocol
from dataclasses import dataclass, field
from enum import Enum
import structlog
from urllib.parse import urlparse

from mcp import ClientSession, types
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings

logger = structlog.get_logger(__name__)

class TransportType(str, Enum):
    """Supported transport types"""
    HTTP = "http"
    WEBSOCKET = "websocket" 
    SSE = "sse"
    STDIO = "stdio"
    UNIX_SOCKET = "unix"

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""
    name: str
    url: str
    transport: TransportType = TransportType.HTTP
    priority: int = 1
    timeout: int = 30
    retry_count: int = 3
    headers: Dict[str, str] = field(default_factory=dict)
    auth_token: Optional[str] = None
    enabled: bool = True

@dataclass 
class StandardizedSchema:
    """Standardized tool schema across different MCP servers"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    examples: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class NormalizedResponse:
    """Normalized response format"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    tool_name: str = ""
    execution_time_ms: int = 0
    server_name: str = ""
    raw_response: Any = None

@dataclass
class ServerCapabilities:
    """Discovered server capabilities"""
    server_name: str
    version: str = "unknown"
    transport_types: List[TransportType] = field(default_factory=list)
    tools: List[StandardizedSchema] = field(default_factory=list)
    features: Dict[str, bool] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class ValidationResult:
    """Parameter validation result"""
    def __init__(self, valid: bool, errors: List[str] = None, 
                 converted_params: Dict[str, Any] = None):
        self.valid = valid
        self.errors = errors or []
        self.converted_params = converted_params or {}

class UniversalMCPClient:
    """Universal MCP client that works with any MCP server"""
    
    def __init__(self, servers: List[MCPServerConfig] = None):
        self.servers = servers or []
        self.capabilities: Dict[str, ServerCapabilities] = {}
        self.active_connections: Dict[str, Any] = {}
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        self._tools_cache: Dict[str, StandardizedSchema] = {}
        self._server_health: Dict[str, bool] = {}
        
        # Initialize default server if none provided
        if not self.servers:
            self._add_default_server()
    
    def _add_default_server(self):
        """Add default Jenkins MCP server from settings"""
        default_server = MCPServerConfig(
            name="jenkins-default",
            url=f"http://{settings.MCP_HTTP_HOST}:{settings.MCP_HTTP_PORT}{settings.MCP_HTTP_ENDPOINT}",
            transport=TransportType.HTTP,
            priority=1,
            timeout=settings.MCP_CLIENT_TIMEOUT
        )
        self.servers.append(default_server)
    
    async def discover_server_capabilities(self, server: MCPServerConfig) -> ServerCapabilities:
        """Discover capabilities of an MCP server"""
        logger.info("Discovering server capabilities", server_name=server.name, url=server.url)
        
        try:
            capabilities = ServerCapabilities(server_name=server.name)
            
            # Connect based on transport type
            if server.transport == TransportType.HTTP:
                capabilities = await self._discover_http_capabilities(server, capabilities)
            else:
                # Add support for other transports in future
                logger.warning("Transport not yet supported", transport=server.transport)
                return capabilities
            
            # Cache capabilities
            self.capabilities[server.name] = capabilities
            self._server_health[server.name] = True
            
            logger.info("Server capabilities discovered", 
                       server_name=server.name, 
                       tool_count=len(capabilities.tools))
            
            return capabilities
            
        except Exception as e:
            logger.error("Failed to discover server capabilities", 
                        server_name=server.name, 
                        error=str(e))
            self._server_health[server.name] = False
            return ServerCapabilities(server_name=server.name)
    
    async def _discover_http_capabilities(self, server: MCPServerConfig, 
                                        capabilities: ServerCapabilities) -> ServerCapabilities:
        """Discover HTTP MCP server capabilities"""
        
        async with streamablehttp_client(server.url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # Get server info if available
                try:
                    info_response = await session.call_tool("server_info", arguments={})
                    if not info_response.isError:
                        server_info = self._extract_response_content(info_response)
                        if isinstance(server_info, dict):
                            capabilities.version = server_info.get("version", "unknown")
                            capabilities.metadata = server_info
                except:
                    pass  # server_info not available
                
                # List all available tools
                tools_response = await session.list_tools()
                
                # Convert to standardized schema
                for tool in tools_response.tools:
                    schema = self.normalize_tool_schema(tool)
                    capabilities.tools.append(schema)
                    # Cache for quick lookup
                    self._tools_cache[f"{server.name}:{tool.name}"] = schema
                
                capabilities.transport_types = [TransportType.HTTP]
                
        return capabilities
    
    def normalize_tool_schema(self, raw_tool: Any) -> StandardizedSchema:
        """Convert MCP tool schema to standardized format"""
        
        # Handle different MCP tool formats
        if hasattr(raw_tool, 'name'):
            # Standard MCP tool format
            return StandardizedSchema(
                name=raw_tool.name,
                description=raw_tool.description or "",
                parameters=raw_tool.inputSchema.get("properties", {}) if raw_tool.inputSchema else {},
                required=raw_tool.inputSchema.get("required", []) if raw_tool.inputSchema else [],
                returns=raw_tool.inputSchema.get("returns") if raw_tool.inputSchema else None
            )
        elif isinstance(raw_tool, dict):
            # Dictionary format
            return StandardizedSchema(
                name=raw_tool.get("name", ""),
                description=raw_tool.get("description", ""),
                parameters=raw_tool.get("parameters", {}),
                required=raw_tool.get("required", []),
                returns=raw_tool.get("returns")
            )
        else:
            logger.warning("Unknown tool schema format", tool_type=type(raw_tool))
            return StandardizedSchema(name="unknown", description="")
    
    async def validate_parameters(self, tool_name: str, params: Dict[str, Any], 
                                server_name: Optional[str] = None) -> ValidationResult:
        """Validate and convert parameters for a tool"""
        
        # Find tool schema
        tool_schema = await self._find_tool_schema(tool_name, server_name)
        if not tool_schema:
            return ValidationResult(False, [f"Tool '{tool_name}' not found"])
        
        errors = []
        converted_params = {}
        
        # Validate required parameters
        for required_param in tool_schema.required:
            if required_param not in params:
                errors.append(f"Required parameter '{required_param}' is missing")
        
        # Validate and convert parameters
        for param_name, param_value in params.items():
            if param_name in tool_schema.parameters:
                param_def = tool_schema.parameters[param_name]
                param_type = param_def.get("type", "string")
                
                # Type conversion
                try:
                    converted_value = self._convert_parameter_type(param_value, param_type)
                    converted_params[param_name] = converted_value
                except ValueError as e:
                    errors.append(f"Parameter '{param_name}': {str(e)}")
            else:
                # Unknown parameter - include with warning
                converted_params[param_name] = param_value
                logger.warning("Unknown parameter for tool", 
                             tool=tool_name, 
                             parameter=param_name)
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            converted_params=converted_params
        )
    
    def _convert_parameter_type(self, value: Any, expected_type: str) -> Any:
        """Convert parameter to expected type"""
        
        if expected_type == "integer":
            if isinstance(value, int):
                return value
            elif isinstance(value, str) and value.isdigit():
                return int(value)
            else:
                raise ValueError(f"Cannot convert '{value}' to integer")
        
        elif expected_type == "boolean":
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                if value.lower() in ["true", "yes", "1"]:
                    return True
                elif value.lower() in ["false", "no", "0"]:
                    return False
                else:
                    raise ValueError(f"Cannot convert '{value}' to boolean")
        
        elif expected_type == "number":
            try:
                return float(value)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert '{value}' to number")
        
        else:  # string or other
            return str(value)
    
    async def execute_tool_with_retry(self, tool_name: str, params: Dict[str, Any],
                                    server_name: Optional[str] = None) -> NormalizedResponse:
        """Execute tool with automatic retry and fallback"""
        
        import time
        start_time = time.time()
        
        # Find best server for this tool
        target_server = await self._select_server_for_tool(tool_name, server_name)
        if not target_server:
            return NormalizedResponse(
                success=False,
                error=f"No server available for tool '{tool_name}'",
                tool_name=tool_name
            )
        
        # Validate parameters
        validation = await self.validate_parameters(tool_name, params, target_server.name)
        if not validation.valid:
            return NormalizedResponse(
                success=False,
                error=f"Parameter validation failed: {'; '.join(validation.errors)}",
                tool_name=tool_name,
                server_name=target_server.name
            )
        
        # Execute with retry
        last_error = None
        for attempt in range(target_server.retry_count):
            try:
                response = await self._execute_tool_on_server(
                    tool_name, validation.converted_params, target_server
                )
                
                execution_time = int((time.time() - start_time) * 1000)
                response.execution_time_ms = execution_time
                response.server_name = target_server.name
                
                return response
                
            except Exception as e:
                last_error = str(e)
                logger.warning("Tool execution attempt failed", 
                             tool=tool_name, 
                             server=target_server.name, 
                             attempt=attempt + 1, 
                             error=str(e))
                
                if attempt < target_server.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return NormalizedResponse(
            success=False,
            error=f"Tool execution failed after {target_server.retry_count} attempts: {last_error}",
            tool_name=tool_name,
            server_name=target_server.name,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
    
    async def _execute_tool_on_server(self, tool_name: str, params: Dict[str, Any],
                                    server: MCPServerConfig) -> NormalizedResponse:
        """Execute tool on specific server"""
        
        if server.transport == TransportType.HTTP:
            return await self._execute_http_tool(tool_name, params, server)
        else:
            raise ValueError(f"Transport {server.transport} not yet supported")
    
    async def _execute_http_tool(self, tool_name: str, params: Dict[str, Any],
                               server: MCPServerConfig) -> NormalizedResponse:
        """Execute tool on HTTP MCP server"""
        
        async with streamablehttp_client(server.url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                response = await session.call_tool(tool_name, arguments=params)
                
                if response.isError:
                    error_content = self._extract_response_content(response)
                    return NormalizedResponse(
                        success=False,
                        error=f"Tool execution error: {error_content}",
                        tool_name=tool_name,
                        raw_response=response
                    )
                
                # Extract and normalize response content
                content = self._extract_response_content(response)
                
                return NormalizedResponse(
                    success=True,
                    data=content,
                    tool_name=tool_name,
                    raw_response=response
                )
    
    def _extract_response_content(self, response: Any) -> Any:
        """Extract content from MCP response in universal way"""
        
        if hasattr(response, 'content') and response.content:
            # Handle list of content items
            if isinstance(response.content, list):
                for item in response.content:
                    if hasattr(item, 'text'):
                        try:
                            # Try to parse as JSON first
                            return json.loads(item.text)
                        except json.JSONDecodeError:
                            # Return as text if not JSON
                            return item.text
                    elif isinstance(item, dict) and 'text' in item:
                        try:
                            return json.loads(item['text'])
                        except json.JSONDecodeError:
                            return item['text']
            
            # Handle direct content
            elif hasattr(response.content, 'text'):
                try:
                    return json.loads(response.content.text)
                except json.JSONDecodeError:
                    return response.content.text
        
        # Fallback - return string representation
        return str(response.content) if hasattr(response, 'content') else str(response)
    
    async def _find_tool_schema(self, tool_name: str, server_name: Optional[str] = None) -> Optional[StandardizedSchema]:
        """Find tool schema in cached tools"""
        
        if server_name:
            cache_key = f"{server_name}:{tool_name}"
            return self._tools_cache.get(cache_key)
        
        # Search across all servers
        for cache_key, schema in self._tools_cache.items():
            if schema.name == tool_name:
                return schema
        
        return None
    
    async def _select_server_for_tool(self, tool_name: str, 
                                    preferred_server: Optional[str] = None) -> Optional[MCPServerConfig]:
        """Select best server for executing a tool"""
        
        # If preferred server specified and available
        if preferred_server:
            for server in self.servers:
                if (server.name == preferred_server and 
                    server.enabled and 
                    self._server_health.get(server.name, False)):
                    # Check if server has the tool
                    if f"{server.name}:{tool_name}" in self._tools_cache:
                        return server
        
        # Find servers that have this tool, sorted by priority
        available_servers = []
        for server in self.servers:
            if (server.enabled and 
                self._server_health.get(server.name, False) and
                f"{server.name}:{tool_name}" in self._tools_cache):
                available_servers.append(server)
        
        # Sort by priority (higher priority first)
        available_servers.sort(key=lambda s: s.priority, reverse=True)
        
        return available_servers[0] if available_servers else None
    
    async def discover_all_servers(self) -> Dict[str, ServerCapabilities]:
        """Discover capabilities of all configured servers"""
        
        logger.info("Starting server capability discovery", server_count=len(self.servers))
        
        discovery_tasks = []
        for server in self.servers:
            if server.enabled:
                task = asyncio.create_task(self.discover_server_capabilities(server))
                discovery_tasks.append(task)
        
        # Wait for all discoveries to complete
        if discovery_tasks:
            await asyncio.gather(*discovery_tasks, return_exceptions=True)
        
        logger.info("Server discovery completed", 
                   discovered_servers=len(self.capabilities),
                   total_tools=len(self._tools_cache))
        
        return self.capabilities
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all servers"""
        
        health_results = {}
        
        for server in self.servers:
            try:
                if server.transport == TransportType.HTTP:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        parsed_url = urlparse(server.url)
                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        response = await client.get(base_url)
                        health_results[server.name] = response.status_code in [200, 404]
                else:
                    # For other transports, assume healthy if enabled
                    health_results[server.name] = server.enabled
                    
            except Exception as e:
                logger.warning("Server health check failed", 
                             server=server.name, 
                             error=str(e))
                health_results[server.name] = False
        
        self._server_health = health_results
        return health_results
    
    async def get_available_tools(self, server_name: Optional[str] = None) -> List[StandardizedSchema]:
        """Get all available tools, optionally filtered by server"""
        
        if server_name:
            server_capabilities = self.capabilities.get(server_name)
            return server_capabilities.tools if server_capabilities else []
        
        # Return all tools from all servers
        all_tools = []
        for capabilities in self.capabilities.values():
            all_tools.extend(capabilities.tools)
        
        return all_tools
    
    async def close(self):
        """Clean up connections and resources"""
        
        # Close any active connections
        for connection in self.active_connections.values():
            try:
                if hasattr(connection, 'close'):
                    await connection.close()
            except Exception as e:
                logger.warning("Error closing connection", error=str(e))
        
        self.active_connections.clear()
        self._connection_locks.clear()
        
        logger.info("Universal MCP Client closed")