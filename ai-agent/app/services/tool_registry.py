"""
Tool Registry System - Intelligent tool selection and fallback management
Maps user intents to optimal tools across multiple MCP servers
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from collections import defaultdict

from app.services.mcp_universal_client import (
    UniversalMCPClient, StandardizedSchema, NormalizedResponse, 
    MCPServerConfig, ServerCapabilities
)

logger = structlog.get_logger(__name__)

class ToolCategory(str, Enum):
    """Tool categories for intelligent selection"""
    JOB_MANAGEMENT = "job_management"
    BUILD_OPERATIONS = "build_operations"  
    SERVER_INFO = "server_info"
    MONITORING = "monitoring"
    SEARCH = "search"
    ANALYSIS = "analysis"
    LOGS = "logs"
    QUEUE = "queue"
    PIPELINE = "pipeline"

class IntentType(str, Enum):
    """User intent types"""
    LIST_JOBS = "list_jobs"
    GET_JOB_INFO = "get_job_info"
    TRIGGER_BUILD = "trigger_build"
    GET_BUILD_STATUS = "get_build_status"
    GET_CONSOLE_LOG = "get_console_log"
    SEARCH_JOBS = "search_jobs"
    GET_QUEUE_INFO = "get_queue_info"
    SERVER_STATUS = "server_status"
    ANALYZE_FAILURE = "analyze_failure"
    GET_BUILD_HISTORY = "get_build_history"

@dataclass
class ToolMapping:
    """Maps intent to tools with priority and fallbacks"""
    intent: IntentType
    primary_tools: List[str] = field(default_factory=list)
    fallback_tools: List[str] = field(default_factory=list)
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    category: ToolCategory = ToolCategory.JOB_MANAGEMENT
    description: str = ""

@dataclass
class ToolPerformance:
    """Track tool performance metrics"""
    tool_name: str
    server_name: str
    success_count: int = 0
    failure_count: int = 0
    avg_response_time_ms: float = 0.0
    last_used: float = 0.0
    last_success: float = 0.0
    last_failure: float = 0.0
    error_patterns: List[str] = field(default_factory=list)

@dataclass
class FallbackChain:
    """Defines fallback strategy for a tool"""
    primary_tool: str
    fallbacks: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    max_fallback_attempts: int = 3

class ToolRegistry:
    """Intelligent tool registry with capability mapping and fallback management"""
    
    def __init__(self, mcp_client: UniversalMCPClient):
        self.mcp_client = mcp_client
        self.tool_mappings: Dict[IntentType, ToolMapping] = {}
        self.performance_metrics: Dict[str, ToolPerformance] = {}
        self.available_tools: Dict[str, StandardizedSchema] = {}
        self.server_tools: Dict[str, Set[str]] = defaultdict(set)
        self.fallback_chains: Dict[str, FallbackChain] = {}
        self.tool_categories: Dict[str, ToolCategory] = {}
        
        # Initialize default mappings and fallback chains
        self._initialize_default_mappings()
        self._initialize_fallback_chains()
    
    def _initialize_default_mappings(self):
        """Initialize default tool mappings for common intents"""
        
        mappings = [
            ToolMapping(
                intent=IntentType.LIST_JOBS,
                primary_tools=["list_jobs", "list_jenkins_jobs"],
                fallback_tools=["search_jobs", "get_jobs"],
                category=ToolCategory.JOB_MANAGEMENT,
                description="List all available Jenkins jobs"
            ),
            ToolMapping(
                intent=IntentType.GET_JOB_INFO,
                primary_tools=["get_job_info", "job_info"],
                fallback_tools=["get_job_details", "job_status"],
                required_params=["job_name"],
                optional_params=["include_builds", "auto_search"],
                category=ToolCategory.JOB_MANAGEMENT,
                description="Get detailed information about a specific job"
            ),
            ToolMapping(
                intent=IntentType.GET_BUILD_STATUS,
                primary_tools=["get_build_status", "build_status"],
                fallback_tools=["get_build_info", "build_details"],
                required_params=["job_name", "build_number"],
                category=ToolCategory.BUILD_OPERATIONS,
                description="Get status of a specific build"
            ),
            ToolMapping(
                intent=IntentType.GET_CONSOLE_LOG,
                primary_tools=["get_console_log", "console_log"],
                fallback_tools=["get_build_log", "build_log"],
                required_params=["job_name", "build_number"],
                optional_params=["start", "limit"],
                category=ToolCategory.LOGS,
                description="Get console output for a build"
            ),
            ToolMapping(
                intent=IntentType.TRIGGER_BUILD,
                primary_tools=["trigger_job", "trigger_build"],
                fallback_tools=["start_job", "build_job"],
                required_params=["job_name"],
                optional_params=["parameters"],
                category=ToolCategory.BUILD_OPERATIONS,
                description="Start a new build for a job"
            ),
            ToolMapping(
                intent=IntentType.SEARCH_JOBS,
                primary_tools=["search_jobs", "find_jobs"],
                fallback_tools=["list_jobs", "query_jobs"],
                required_params=["pattern"],
                optional_params=["max_depth", "recursive"],
                category=ToolCategory.SEARCH,
                description="Search for jobs matching a pattern"
            ),
            ToolMapping(
                intent=IntentType.GET_QUEUE_INFO,
                primary_tools=["get_queue_info", "queue_status"],
                fallback_tools=["build_queue", "queue_list"],
                category=ToolCategory.MONITORING,
                description="Get information about the build queue"
            ),
            ToolMapping(
                intent=IntentType.SERVER_STATUS,
                primary_tools=["server_info", "jenkins_info"],
                fallback_tools=["system_info", "status"],
                category=ToolCategory.SERVER_INFO,
                description="Get Jenkins server information and status"
            ),
            ToolMapping(
                intent=IntentType.GET_BUILD_HISTORY,
                primary_tools=["get_build_history", "build_history"],
                fallback_tools=["list_builds", "job_builds"],
                required_params=["job_name"],
                optional_params=["limit", "offset"],
                category=ToolCategory.BUILD_OPERATIONS,
                description="Get build history for a job"
            )
        ]
        
        for mapping in mappings:
            self.tool_mappings[mapping.intent] = mapping
    
    def _initialize_fallback_chains(self):
        """Initialize fallback chains for tools"""
        
        chains = [
            FallbackChain(
                primary_tool="list_jobs",
                fallbacks=["search_jobs", "get_jobs", "list_jenkins_jobs"],
                conditions={"empty_result": True, "timeout": True}
            ),
            FallbackChain(
                primary_tool="get_job_info", 
                fallbacks=["job_info", "get_job_details", "search_jobs"],
                conditions={"not_found": True, "access_denied": True}
            ),
            FallbackChain(
                primary_tool="get_build_status",
                fallbacks=["build_status", "get_build_info", "get_job_info"],
                conditions={"build_not_found": True, "invalid_build_number": True}
            ),
            FallbackChain(
                primary_tool="search_jobs",
                fallbacks=["find_jobs", "list_jobs"],
                conditions={"no_results": True, "pattern_invalid": True}
            )
        ]
        
        for chain in chains:
            self.fallback_chains[chain.primary_tool] = chain
    
    async def discover_tools(self):
        """Discover all available tools from MCP servers"""
        
        logger.info("Starting tool discovery")
        
        # Discover server capabilities
        capabilities = await self.mcp_client.discover_all_servers()
        
        # Build tool registry
        for server_name, server_caps in capabilities.items():
            for tool_schema in server_caps.tools:
                # Store tool schema
                tool_key = f"{server_name}:{tool_schema.name}"
                self.available_tools[tool_key] = tool_schema
                
                # Track which servers have which tools
                self.server_tools[server_name].add(tool_schema.name)
                
                # Categorize tool
                category = self._categorize_tool(tool_schema.name)
                self.tool_categories[tool_schema.name] = category
                
                # Initialize performance tracking
                perf_key = f"{server_name}:{tool_schema.name}"
                if perf_key not in self.performance_metrics:
                    self.performance_metrics[perf_key] = ToolPerformance(
                        tool_name=tool_schema.name,
                        server_name=server_name
                    )
        
        logger.info("Tool discovery completed", 
                   total_tools=len(self.available_tools),
                   servers=len(capabilities))
    
    def _categorize_tool(self, tool_name: str) -> ToolCategory:
        """Categorize tool based on name patterns"""
        
        name_lower = tool_name.lower()
        
        if any(keyword in name_lower for keyword in ["list", "jobs", "job_info", "get_job"]):
            return ToolCategory.JOB_MANAGEMENT
        elif any(keyword in name_lower for keyword in ["build", "trigger", "start"]):
            return ToolCategory.BUILD_OPERATIONS
        elif any(keyword in name_lower for keyword in ["console", "log", "output"]):
            return ToolCategory.LOGS
        elif any(keyword in name_lower for keyword in ["search", "find", "query"]):
            return ToolCategory.SEARCH
        elif any(keyword in name_lower for keyword in ["queue", "running", "active"]):
            return ToolCategory.MONITORING
        elif any(keyword in name_lower for keyword in ["server", "info", "status", "system"]):
            return ToolCategory.SERVER_INFO
        elif any(keyword in name_lower for keyword in ["pipeline", "stage"]):
            return ToolCategory.PIPELINE
        else:
            return ToolCategory.JOB_MANAGEMENT  # Default
    
    async def select_optimal_tool(self, intent: IntentType, 
                                context: Dict[str, Any] = None) -> Optional[Tuple[str, str]]:
        """Select optimal tool for an intent, returns (tool_name, server_name)"""
        
        context = context or {}
        
        # Get tool mapping for intent
        mapping = self.tool_mappings.get(intent)
        if not mapping:
            logger.warning("No mapping found for intent", intent=intent)
            return None
        
        # Check primary tools first
        for tool_name in mapping.primary_tools:
            result = await self._find_best_server_for_tool(tool_name, context)
            if result:
                return result
        
        # Try fallback tools
        for tool_name in mapping.fallback_tools:
            result = await self._find_best_server_for_tool(tool_name, context)
            if result:
                logger.info("Using fallback tool", 
                           intent=intent, 
                           tool=tool_name, 
                           server=result[1])
                return result
        
        logger.warning("No available tool found for intent", intent=intent)
        return None
    
    async def _find_best_server_for_tool(self, tool_name: str, 
                                       context: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """Find best server for a specific tool"""
        
        candidate_servers = []
        
        # Find servers that have this tool
        for server_name, tools in self.server_tools.items():
            if tool_name in tools:
                # Get performance metrics
                perf_key = f"{server_name}:{tool_name}"
                performance = self.performance_metrics.get(perf_key)
                
                if performance:
                    # Calculate score based on performance
                    success_rate = (performance.success_count / 
                                  (performance.success_count + performance.failure_count)) if (
                                  performance.success_count + performance.failure_count) > 0 else 0.5
                    
                    # Prefer faster, more reliable tools
                    score = success_rate * 0.7 + (1000 / max(performance.avg_response_time_ms, 1)) * 0.3
                    
                    candidate_servers.append({
                        'server_name': server_name,
                        'tool_name': tool_name,
                        'score': score,
                        'last_success': performance.last_success
                    })
        
        if not candidate_servers:
            return None
        
        # Sort by score (descending) and recency
        candidate_servers.sort(key=lambda x: (x['score'], x['last_success']), reverse=True)
        
        best_candidate = candidate_servers[0]
        return (best_candidate['tool_name'], best_candidate['server_name'])
    
    async def execute_with_fallback(self, intent: IntentType, params: Dict[str, Any],
                                  context: Dict[str, Any] = None) -> NormalizedResponse:
        """Execute tool with automatic fallback handling"""
        
        start_time = time.time()
        context = context or {}
        
        # Select optimal tool
        tool_selection = await self.select_optimal_tool(intent, context)
        if not tool_selection:
            return NormalizedResponse(
                success=False,
                error=f"No available tool for intent: {intent}"
            )
        
        tool_name, server_name = tool_selection
        
        # Try primary tool
        response = await self._execute_tool_with_tracking(tool_name, params, server_name)
        
        # If primary failed, try fallback chain
        if not response.success and tool_name in self.fallback_chains:
            chain = self.fallback_chains[tool_name]
            
            for fallback_tool in chain.fallbacks:
                # Check if fallback is available
                fallback_selection = await self._find_best_server_for_tool(fallback_tool, context)
                if fallback_selection:
                    fallback_tool_name, fallback_server = fallback_selection
                    
                    logger.info("Trying fallback tool", 
                               primary=tool_name,
                               fallback=fallback_tool_name,
                               server=fallback_server)
                    
                    fallback_response = await self._execute_tool_with_tracking(
                        fallback_tool_name, params, fallback_server
                    )
                    
                    if fallback_response.success:
                        logger.info("Fallback succeeded", 
                                   fallback_tool=fallback_tool_name,
                                   server=fallback_server)
                        return fallback_response
        
        return response
    
    async def _execute_tool_with_tracking(self, tool_name: str, params: Dict[str, Any],
                                        server_name: str) -> NormalizedResponse:
        """Execute tool and track performance metrics"""
        
        perf_key = f"{server_name}:{tool_name}"
        performance = self.performance_metrics.get(perf_key)
        
        if not performance:
            performance = ToolPerformance(tool_name=tool_name, server_name=server_name)
            self.performance_metrics[perf_key] = performance
        
        start_time = time.time()
        
        try:
            response = await self.mcp_client.execute_tool_with_retry(
                tool_name, params, server_name
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            # Update performance metrics
            if response.success:
                performance.success_count += 1
                performance.last_success = time.time()
                
                # Update average response time
                total_calls = performance.success_count + performance.failure_count
                performance.avg_response_time_ms = (
                    (performance.avg_response_time_ms * (total_calls - 1) + execution_time) / total_calls
                )
            else:
                performance.failure_count += 1
                performance.last_failure = time.time()
                
                # Track error patterns
                if response.error and len(performance.error_patterns) < 10:
                    if response.error not in performance.error_patterns:
                        performance.error_patterns.append(response.error[:100])  # First 100 chars
            
            performance.last_used = time.time()
            
            return response
            
        except Exception as e:
            performance.failure_count += 1
            performance.last_failure = time.time()
            performance.last_used = time.time()
            
            return NormalizedResponse(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                tool_name=tool_name,
                server_name=server_name
            )
    
    def get_tools_for_category(self, category: ToolCategory) -> List[Tuple[str, str]]:
        """Get all tools for a specific category"""
        
        tools = []
        for tool_key, schema in self.available_tools.items():
            if self.tool_categories.get(schema.name) == category:
                server_name = tool_key.split(':', 1)[0]
                tools.append((schema.name, server_name))
        
        return tools
    
    def get_performance_metrics(self, tool_name: str = None) -> Dict[str, ToolPerformance]:
        """Get performance metrics, optionally filtered by tool"""
        
        if tool_name:
            return {k: v for k, v in self.performance_metrics.items() 
                   if v.tool_name == tool_name}
        
        return self.performance_metrics.copy()
    
    async def generate_gemini_functions(self) -> List[Dict[str, Any]]:
        """Generate Gemini Function Calling declarations from discovered tools"""
        
        function_declarations = []
        
        for tool_key, schema in self.available_tools.items():
            server_name, tool_name = tool_key.split(':', 1)
            
            # Convert schema to Gemini function format
            function_def = {
                "name": tool_name,
                "description": schema.description or f"Execute {tool_name} on {server_name}",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": schema.required.copy()
                }
            }
            
            # Add parameters
            for param_name, param_def in schema.parameters.items():
                if isinstance(param_def, dict):
                    function_def["parameters"]["properties"][param_name] = {
                        "type": param_def.get("type", "string"),
                        "description": param_def.get("description", f"Parameter {param_name}")
                    }
                    
                    # Add enum values if available
                    if "enum" in param_def:
                        function_def["parameters"]["properties"][param_name]["enum"] = param_def["enum"]
                else:
                    # Simple parameter definition
                    function_def["parameters"]["properties"][param_name] = {
                        "type": "string",
                        "description": f"Parameter {param_name}"
                    }
            
            function_declarations.append(function_def)
        
        logger.info("Generated Gemini function declarations", count=len(function_declarations))
        return function_declarations
    
    def get_tool_suggestions(self, partial_query: str) -> List[Dict[str, Any]]:
        """Get tool suggestions based on partial user query"""
        
        query_lower = partial_query.lower()
        suggestions = []
        
        for intent, mapping in self.tool_mappings.items():
            # Simple keyword matching for suggestions
            intent_keywords = intent.value.split('_') + [mapping.description.lower()]
            
            if any(keyword in query_lower for keyword in intent_keywords):
                suggestions.append({
                    "intent": intent.value,
                    "description": mapping.description,
                    "primary_tools": mapping.primary_tools,
                    "required_params": mapping.required_params,
                    "optional_params": mapping.optional_params
                })
        
        return suggestions[:5]  # Return top 5 suggestions
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of tool registry"""
        
        return {
            "total_tools": len(self.available_tools),
            "servers_with_tools": len(self.server_tools),
            "tool_mappings": len(self.tool_mappings),
            "fallback_chains": len(self.fallback_chains),
            "performance_tracked": len(self.performance_metrics),
            "healthy": len(self.available_tools) > 0
        }