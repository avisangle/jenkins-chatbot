"""
MCP Service using SSE transport to avoid STDIO protocol mismatch
Handles communication with FastMCP server via Server-Sent Events
"""

import asyncio
import json
import subprocess
import httpx
from typing import Dict, List, Optional, Any
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

class MCPServiceSSE:
    """Service for MCP server integration using SSE transport"""
    
    def __init__(self):
        self.server_process: Optional[subprocess.Popen] = None
        self.base_url = f"http://localhost:{settings.MCP_SSE_PORT}"
        self._connection_lock = asyncio.Lock()
        
    async def _ensure_server_running(self) -> bool:
        """Ensure MCP server is running in SSE mode"""
        async with self._connection_lock:
            if self.server_process is None:
                try:
                    # Start MCP server in SSE mode
                    logger.info("Starting MCP server in SSE mode", port=settings.MCP_SSE_PORT)
                    
                    self.server_process = subprocess.Popen([
                        "python3", settings.MCP_SERVER_SCRIPT_PATH,
                        "--transport", "streamable-http",
                        "--port", str(settings.MCP_SSE_PORT),
                        "--host", "0.0.0.0"
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    # Wait for server to start
                    await asyncio.sleep(3)
                    
                    # Check if server is responding
                    if await self._test_connection():
                        logger.info("MCP server started successfully in SSE mode")
                        return True
                    else:
                        logger.error("MCP server failed to start properly")
                        return False
                        
                except Exception as e:
                    logger.error("Failed to start MCP server", error=str(e))
                    return False
            
            return await self._test_connection()
    
    async def _test_connection(self) -> bool:
        """Test if MCP server is responding"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
    
    async def _make_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a tool call to the MCP server via SSE/HTTP"""
        try:
            if not await self._ensure_server_running():
                return None
                
            async with httpx.AsyncClient(timeout=settings.MCP_CLIENT_TIMEOUT) as client:
                payload = {
                    "tool": tool_name,
                    "arguments": arguments
                }
                
                response = await client.post(f"{self.base_url}/tools/{tool_name}", json=payload)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning("MCP tool call failed", 
                                 tool=tool_name, 
                                 status=response.status_code,
                                 error=response.text)
                    return None
                    
        except Exception as e:
            logger.error("Error making MCP tool call", tool=tool_name, error=str(e))
            return None
    
    async def analyze_jenkins_build_failure(
        self,
        job_name: str,
        build_number: str,
        console_log: str,
        build_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Use MCP server to analyze build failure"""
        
        try:
            # Get console log from MCP server
            console_response = await self._make_tool_call(
                "get_console_log",
                {
                    "job_name": job_name,
                    "build_number": int(build_number),
                    "start": 0
                }
            )
            
            if not console_response:
                return None
            
            # Get build status
            status_response = await self._make_tool_call(
                "get_build_status",
                {
                    "job_name": job_name,
                    "build_number": int(build_number)
                }
            )
            
            if not status_response:
                return None
            
            # Summarize the build log
            summary_response = await self._make_tool_call(
                "summarize_build_log",
                {
                    "job_name": job_name,
                    "build_number": int(build_number)
                }
            )
            
            result = {
                "console_log": console_response.get("result", ""),
                "build_status": status_response.get("result", {}),
                "summary": summary_response.get("result") if summary_response else None,
                "analysis": {
                    "job_name": job_name,
                    "build_number": build_number,
                    "failure_detected": True,
                    "recommendations": [
                        "Check console log for error messages",
                        "Verify build parameters and environment variables",
                        "Review recent code changes that might have caused the failure"
                    ]
                }
            }
            
            logger.info("Build failure analysis completed via MCP SSE",
                       job_name=job_name,
                       build_number=build_number)
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
            # Get list of jobs
            jobs_response = await self._make_tool_call(
                "search_jobs",
                {
                    "pattern": "*",
                    "max_depth": 3,
                    "include_folders": False,
                    "max_results": 50
                }
            )
            
            if not jobs_response:
                return None
            
            jobs = jobs_response.get("result", {}).get("jobs", [])
            
            # Filter jobs based on user query and context
            recommendations = []
            query_lower = current_query.lower()
            
            for job in jobs:
                job_name = job.get("name", "")
                job_name_lower = job_name.lower()
                
                # Simple relevance scoring
                relevance_score = 0
                if any(word in job_name_lower for word in query_lower.split()):
                    relevance_score += 2
                
                if job.get("lastBuild", {}).get("result") == "FAILURE":
                    relevance_score += 1
                
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
            
            logger.info("Got Jenkins recommendations from MCP SSE",
                       user_id=user_context.get("user_id"),
                       recommendation_count=len(recommendations))
            return recommendations[:10]
                
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
        """Enhance AI response using MCP server capabilities"""
        
        try:
            # Get server info
            server_response = await self._make_tool_call("server_info", {})
            
            enhancement = {
                "original_response": ai_response,
                "enhanced_context": {},
                "additional_actions": []
            }
            
            if server_response and server_response.get("result"):
                server_info = server_response["result"]
                enhancement["enhanced_context"]["jenkins_version"] = server_info.get("version", "unknown")
                enhancement["enhanced_context"]["server_url"] = server_info.get("url", "")
            
            # If query is about builds, get queue info
            if any(word in user_query.lower() for word in ["build", "queue", "running"]):
                queue_response = await self._make_tool_call("get_queue_info", {})
                if queue_response and queue_response.get("result"):
                    queue_info = queue_response["result"]
                    if queue_info:
                        enhancement["additional_actions"].append({
                            "type": "queue_info",
                            "message": f"There are {len(queue_info)} items in the build queue",
                            "details": queue_info[:3]
                        })
            
            logger.info("AI response enhanced by MCP SSE")
            return enhancement
                
        except Exception as e:
            logger.error("Error enhancing AI response with MCP", error=str(e))
            return None
    
    async def health_check(self) -> bool:
        """Check MCP server health using SSE transport"""
        
        # Check if MCP is enabled
        if not settings.MCP_ENABLED:
            logger.info("MCP server is disabled in configuration")
            return False
        
        try:
            # Test if server is running and responsive
            if await self._ensure_server_running():
                logger.info("MCP server health check passed - SSE transport")
                return True
            else:
                logger.warning("MCP server health check failed - SSE transport")
                return False
            
        except Exception as e:
            logger.error("MCP server health check failed", error=str(e))
            return False
    
    async def close(self):
        """Close MCP server process"""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                self.server_process = None
                logger.info("MCP server process closed")
            except Exception as e:
                logger.error("Error closing MCP server process", error=str(e))
                if self.server_process:
                    self.server_process.kill()
                    self.server_process = None