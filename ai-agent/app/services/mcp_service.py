"""
MCP Service for integrating with FastMCP server using streamable HTTP transport
Handles communication with MCP server for enhanced AI capabilities
"""

import asyncio
import json
import subprocess
import os
from typing import Dict, List, Optional, Any
import structlog

from mcp import ClientSession, types
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings

logger = structlog.get_logger(__name__)

class MCPService:
    """Service for MCP server integration using streamable HTTP transport"""
    
    def __init__(self):
        self._client_context = None
        self.session: Optional[ClientSession] = None
        self.server_process: Optional[subprocess.Popen] = None
        self._connection_lock = asyncio.Lock()
        self.base_url = f"http://{settings.MCP_HTTP_HOST}:{settings.MCP_HTTP_PORT}{settings.MCP_HTTP_ENDPOINT}"
    
    def _extract_response_content(self, result):
        """Extract text content from MCP response - from working test files"""
        if hasattr(result, 'content') and result.content:
            for item in result.content:
                if hasattr(item, 'text'):
                    return item.text
                elif hasattr(item, 'type') and item.type == 'text' and hasattr(item, 'text'):
                    return item.text
        return str(result.content) if hasattr(result, 'content') else str(result)
        
    async def _ensure_server_running(self) -> bool:
        """Check if MCP server is accessible (assumes external server management)"""
        try:
            # Test if server is accessible by making a simple HTTP request
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try to connect to the MCP server endpoint
                response = await client.get(f"http://{settings.MCP_HTTP_HOST}:{settings.MCP_HTTP_PORT}")
                if response.status_code in [200, 404]:  # 404 is OK, means server is running
                    logger.info("MCP server is accessible", url=self.base_url)
                    return True
                else:
                    logger.warning("MCP server responded with unexpected status", 
                                 status=response.status_code)
                    return False
        except Exception as e:
            logger.warning("MCP server not accessible", error=str(e), url=self.base_url)
            return False
        
    
    async def analyze_jenkins_build_failure(
        self,
        job_name: str,
        build_number: str,
        console_log: str,
        build_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Use MCP server to analyze build failure"""
        
        try:
            # Use the working pattern from test files
            async with streamablehttp_client(self.base_url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    # First get console log from MCP server
                    console_response = await session.call_tool(
                        "get_console_log",
                        arguments={
                            "job_name": job_name,
                            "build_number": int(build_number),
                            "start": 0
                        }
                    )
                    
                    if console_response.isError:
                        logger.warning("Failed to get console log via MCP", 
                                     job_name=job_name, 
                                     error=console_response.content)
                        return None
                    
                    # Then get build status for more details
                    status_response = await session.call_tool(
                        "get_build_status",
                        arguments={
                            "job_name": job_name,
                            "build_number": int(build_number)
                        }
                    )
                    
                    if status_response.isError:
                        logger.warning("Failed to get build status via MCP",
                                     job_name=job_name,
                                     error=status_response.content)
                        return None
                    
                    # Summarize the build log using MCP server's built-in capability
                    summary_response = await session.call_tool(
                        "summarize_build_log",
                        arguments={
                            "job_name": job_name,
                            "build_number": int(build_number)
                        }
                    )
                    
                    # Parse responses using proper content handling
                    console_log = ""
                    build_status = {}
                    summary = None
                    
                    # Parse console log response
                    if not console_response.isError:
                        for content in console_response.content:
                            if isinstance(content, types.TextContent):
                                console_log = content.text
                                break
                    
                    # Parse build status response  
                    if not status_response.isError:
                        for content in status_response.content:
                            if isinstance(content, types.TextContent):
                                try:
                                    build_status = json.loads(content.text)
                                except json.JSONDecodeError:
                                    logger.warning("Failed to parse build status JSON")
                                break
                    
                    # Parse summary response
                    if not summary_response.isError:
                        for content in summary_response.content:
                            if isinstance(content, types.TextContent):
                                try:
                                    summary = json.loads(content.text)
                                except json.JSONDecodeError:
                                    logger.warning("Failed to parse summary JSON")
                                break
                    
                    result = {
                        "console_log": console_log,
                        "build_status": build_status,
                        "summary": summary,
                        "analysis": {
                            "job_name": job_name,
                            "build_number": build_number,
                            "failure_detected": True,
                            "recommendations": []
                        }
                    }
                    
                    # Add basic failure analysis
                    if result["build_status"].get("result") == "FAILURE":
                        result["analysis"]["recommendations"] = [
                            "Check console log for error messages",
                            "Verify build parameters and environment variables",
                            "Review recent code changes that might have caused the failure"
                        ]
                    
                    logger.info("Build failure analysis completed via MCP",
                               job_name=job_name,
                               build_number=build_number,
                               analysis_available=True)
                    return result
                
        except Exception as e:
            logger.error("Error in MCP build analysis",
                        error=str(e),
                        job_name=job_name,
                        build_number=build_number)
            return None
    
    async def get_jenkins_recommendations(
        self,
        user_context: Dict[str, Any],
        current_query: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get job recommendations from MCP server"""
        
        try:
            # Use the working pattern from test files
            async with streamablehttp_client(self.base_url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    # Get list of jobs the user can access
                    jobs_response = await session.call_tool(
                        "search_jobs",
                        arguments={
                            "pattern": "*",  # Get all jobs
                            "max_depth": 3
                        }
                    )
                    
                    if jobs_response.isError:
                        logger.warning("Failed to get job list via MCP")
                        for content in jobs_response.content:
                            if isinstance(content, types.TextContent):
                                logger.warning("MCP error", error=content.text)
                        return None
                    
                    # Parse jobs response using proper content handling
                    jobs_data = {}
                    for content in jobs_response.content:
                        if isinstance(content, types.TextContent):
                            try:
                                jobs_data = json.loads(content.text)
                                break
                            except json.JSONDecodeError:
                                logger.warning("Failed to parse jobs data JSON")
                                return None
                    
                    jobs = jobs_data.get("jobs", []) if jobs_data else []
                    
                    # Filter jobs based on user query and context
                    recommendations = []
                    query_lower = current_query.lower()
                    
                    for job in jobs:
                        job_name = job.get("name", "")
                        job_name_lower = job_name.lower()
                        
                        # Simple relevance scoring based on query matching
                        relevance_score = 0
                        if any(word in job_name_lower for word in query_lower.split()):
                            relevance_score += 2
                        
                        if job.get("lastBuild", {}).get("result") == "FAILURE":
                            relevance_score += 1  # Failed builds might need attention
                        
                        if relevance_score > 0:
                            recommendations.append({
                                "job_name": job_name,
                                "description": job.get("description", ""),
                                "last_build_status": job.get("lastBuild", {}).get("result", "UNKNOWN"),
                                "relevance_score": relevance_score,
                                "url": job.get("url", ""),
                                "buildable": job.get("buildable", False)
                            })
                    
                    # Sort by relevance score
                    recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
                    
                    logger.info("Got Jenkins recommendations from MCP",
                               user_id=user_context.get("user_id"),
                               recommendation_count=len(recommendations))
                    return recommendations[:10]  # Return top 10 recommendations
            
            logger.info("Got Jenkins recommendations from MCP",
                       user_id=user_context.get("user_id"),
                       recommendation_count=len(recommendations))
            return recommendations[:10]  # Return top 10 recommendations
                
        except Exception as e:
            logger.error("Error getting MCP recommendations",
                        error=str(e),
                        user_id=user_context.get("user_id"))
            return None
    
    async def enhance_ai_response(
        self,
        user_query: str,
        ai_response: str,
        jenkins_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Enhance AI response using MCP server capabilities with proper content parsing"""
        
        try:
            # Use the working pattern from test files
            async with streamablehttp_client(self.base_url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    enhancement_parts = [ai_response]  # Start with original AI response
                    additional_info = []
                    
                    # Get server info using proper content parsing
                    server_response = await session.call_tool("server_info", arguments={})
                    
                    if server_response.isError:
                        logger.warning("MCP server_info call failed")
                        for content in server_response.content:
                            if isinstance(content, types.TextContent):
                                logger.warning("Server error", error=content.text)
                    else:
                        # Parse server info with proper content handling
                        for content in server_response.content:
                            if isinstance(content, types.TextContent):
                                try:
                                    server_info = json.loads(content.text)
                                    if server_info.get("version"):
                                        additional_info.append(f"📋 Jenkins Version: {server_info['version']}")
                                    if server_info.get("url"):
                                        additional_info.append(f"🔗 Server: {server_info['url']}")
                                except json.JSONDecodeError:
                                    logger.warning("Failed to parse server info JSON")
                    
                    # If query is about builds, jobs, or status - get relevant information
                    if any(word in user_query.lower() for word in ["build", "queue", "running", "job", "status"]):
                        
                        # Get queue info
                        queue_response = await session.call_tool("get_queue_info", arguments={})
                        if not queue_response.isError:
                            for content in queue_response.content:
                                if isinstance(content, types.TextContent):
                                    try:
                                        queue_info = json.loads(content.text)
                                        if queue_info and len(queue_info) > 0:
                                            additional_info.append(f"⏳ Build Queue: {len(queue_info)} items")
                                            for item in queue_info[:3]:  # Show first 3 items
                                                task_name = item.get('task', {}).get('name', 'Unknown')
                                                additional_info.append(f"  • {task_name}")
                                    except json.JSONDecodeError:
                                        logger.warning("Failed to parse queue info JSON")
                        
                        # Get jobs list for context - use list_jobs instead of search_jobs
                        jobs_response = await session.call_tool("list_jobs", arguments={"recursive": True})
                        if not jobs_response.isError:
                            for content in jobs_response.content:
                                if isinstance(content, types.TextContent):
                                    try:
                                        jobs_data = json.loads(content.text)
                                        if jobs_data and len(jobs_data) > 0:
                                            additional_info.append(f"📁 Available Jobs: {len(jobs_data)} total")
                                            # Include actual job names for "list" queries
                                            if any(word in user_query.lower() for word in ["list", "show", "all"]):
                                                job_names = [job.get('name', 'Unknown') for job in jobs_data]
                                                additional_info.append(f"📋 Job Names:")
                                                for job_name in job_names:
                                                    additional_info.append(f"  • {job_name}")
                                            else:
                                                recent_jobs = [job.get('name', 'Unknown') for job in jobs_data[:5]]
                                                additional_info.append(f"  Recent: {', '.join(recent_jobs)}")
                                    except json.JSONDecodeError:
                                        logger.warning("Failed to parse jobs data JSON")
                    
                    # If query is about specific job, get detailed info
                    job_keywords = ["trigger", "start", "status of", "build"]
                    if any(keyword in user_query.lower() for keyword in job_keywords):
                        # Try to extract job name from query
                        words = user_query.split()
                        potential_job_names = [word for word in words if len(word) > 3 and not word.lower() in ["build", "trigger", "status", "start"]]
                        
                        for job_name in potential_job_names[:2]:  # Check first 2 potential job names
                            job_response = await session.call_tool("get_job_info", arguments={"job_name": job_name, "auto_search": True})
                            if not job_response.isError:
                                for content in job_response.content:
                                    if isinstance(content, types.TextContent):
                                        try:
                                            job_info = json.loads(content.text)
                                            if job_info:
                                                job_display_name = job_info.get('displayName', job_name)
                                                last_build = job_info.get('lastBuild', {})
                                                if last_build:
                                                    build_num = last_build.get('number', 'N/A')
                                                    build_result = last_build.get('result', 'UNKNOWN')
                                                    additional_info.append(f"🔧 Job '{job_display_name}' - Last Build #{build_num}: {build_result}")
                                                break
                                        except json.JSONDecodeError:
                                            continue
                    
                    # Combine original response with MCP enhancements
                    if additional_info:
                        enhancement_parts.extend(["", "📊 **Live Jenkins Data:**"] + additional_info)
                    
                    enhanced_response = "\n".join(enhancement_parts)
                    
                    result = {
                        "original_response": ai_response,
                        "enhanced_response": enhanced_response,  # This is what AI service expects!
                        "mcp_data_included": len(additional_info) > 0
                    }
                    
                    logger.info("AI response enhanced by MCP", 
                              enhancements_count=len(additional_info),
                              has_enhanced_response=True)
                    return result
                
        except Exception as e:
            logger.error("Error enhancing AI response with MCP", error=str(e))
            return None
    
    async def validate_jenkins_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate Jenkins operation using MCP server"""
        
        try:
            # Use the working pattern from test files
            async with streamablehttp_client(self.base_url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    validation_result = {
                        "valid": False,
                        "operation": operation,
                        "message": "",
                        "suggestions": []
                    }
                    
                    # For job operations, check if job exists
                    if operation in ["trigger_job", "get_build_status", "get_console_log"]:
                        job_name = parameters.get("job_name")
                        if job_name:
                            job_response = await session.call_tool(
                                "get_job_info",
                                arguments={"job_name": job_name, "auto_search": True}
                            )
                            
                            if job_response.isError:
                                validation_result["message"] = f"Job '{job_name}' not found or not accessible"
                                validation_result["suggestions"] = [
                                    "Check job name spelling",
                                    "Verify you have permission to access this job",
                                    "Use search functionality to find similar jobs"
                                ]
                            else:
                                validation_result["valid"] = True
                                validation_result["message"] = f"Job '{job_name}' is accessible"
                                
                                # Parse job info with proper content handling
                                job_info = {}
                                for content in job_response.content:
                                    if isinstance(content, types.TextContent):
                                        try:
                                            job_info = json.loads(content.text)
                                            break
                                        except json.JSONDecodeError:
                                            logger.warning("Failed to parse job info JSON")
                                if not job_info.get("buildable", False):
                                    validation_result["valid"] = False
                                    validation_result["message"] = f"Job '{job_name}' is not buildable"
                    else:
                        # For other operations, assume valid for now
                        validation_result["valid"] = True
                        validation_result["message"] = f"Operation '{operation}' appears valid"
                    
                    logger.info("Operation validation completed",
                               operation=operation,
                               valid=validation_result["valid"])
                    return validation_result
                
        except Exception as e:
            logger.error("Error validating operation with MCP",
                        error=str(e),
                        operation=operation)
            return None
    
    async def health_check(self) -> bool:
        """Check MCP server health using working pattern"""
        try:
            async with streamablehttp_client(self.base_url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    tool_count = len(tools.tools)
                    
                    logger.info("MCP server health check passed", tool_count=tool_count)
                    return True
                    
        except Exception as e:
            logger.error("MCP server health check failed", error=str(e))
            return False
    
    async def get_jenkins_help(
        self,
        help_topic: str,
        user_permissions: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get contextual help from MCP server"""
        
        try:
            # Use the working pattern from test files
            async with streamablehttp_client(self.base_url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the connection
                    await session.initialize()
                    
                    help_content = {
                        "topic": help_topic,
                        "available_commands": [],
                        "examples": [],
                        "tips": []
                    }
                    
                    # Get server info for context
                    server_response = await session.call_tool("server_info", arguments={})
                    if not server_response.isError and server_response.content:
                        # Parse server info with proper content handling
                        server_info = {}
                        for content in server_response.content:
                            if isinstance(content, types.TextContent):
                                try:
                                    server_info = json.loads(content.text)
                                    break
                                except json.JSONDecodeError:
                                    logger.warning("Failed to parse server info JSON")
                        help_content["jenkins_version"] = server_info.get("version", "unknown")
                    
                    # Provide help based on topic
                    if help_topic.lower() in ["build", "trigger", "job"]:
                        help_content["available_commands"] = [
                            "trigger_job",
                            "get_build_status", 
                            "get_console_log",
                            "search_jobs"
                        ]
                        help_content["examples"] = [
                            "trigger my-job",
                            "build the frontend",
                            "start deployment job"
                        ]
                        help_content["tips"] = [
                            "Use natural language to describe what you want to build",
                            "Check build status before triggering new builds",
                            "Review console logs if builds fail"
                        ]
                    
                    elif help_topic.lower() in ["status", "monitor", "check"]:
                        help_content["available_commands"] = [
                            "get_build_status",
                            "get_queue_info",
                            "get_pipeline_status"
                        ]
                        help_content["examples"] = [
                            "check build status",
                            "what's in the queue",
                            "show pipeline status"
                        ]
                    
                    logger.info("Contextual help retrieved from MCP", topic=help_topic)
                    return help_content
                
        except Exception as e:
            logger.error("Error getting help from MCP",
                        error=str(e),
                        topic=help_topic)
            return None
    
    async def health_check(self) -> bool:
        """Check MCP server health using working pattern from test files"""
        
        # Check if MCP is enabled
        if not settings.MCP_ENABLED:
            logger.info("MCP server is disabled in configuration")
            return False
        
        try:
            # Use the working pattern from test files
            async with streamablehttp_client(self.base_url) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    tool_count = len(tools.tools)
                    
                    logger.info("MCP server health check passed", tool_count=tool_count)
                    return True
                    
        except Exception as e:
            logger.error("MCP server health check failed", error=str(e))
            return False
    
    async def close(self):
        """Close MCP client session and server process"""
        if self.session:
            try:
                await self.session.close()
                self.session = None
            except Exception as e:
                logger.error("Error closing MCP session", error=str(e))
        
        if self._client_context:
            try:
                await self._client_context.__aexit__(None, None, None)
                self._client_context = None
                logger.info("MCP streamable HTTP client closed")
            except Exception as e:
                logger.error("Error closing MCP client context", error=str(e))
        
        # Note: Server process is managed externally, no cleanup needed