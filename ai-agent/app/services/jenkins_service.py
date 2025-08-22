"""
Jenkins Service for interacting with Jenkins API
Handles job operations, build management, and status queries
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
import structlog
import httpx
from urllib.parse import quote

from app.config import settings

logger = structlog.get_logger(__name__)

class JenkinsService:
    """Service for Jenkins API interactions"""
    
    def __init__(self):
        self.base_url = settings.JENKINS_URL.rstrip('/')
        self.timeout = settings.JENKINS_API_TIMEOUT
        self.client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client for Jenkins API"""
        if not self.client:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True
            )
        return self.client
    
    async def get_user_jobs(self, user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get jobs accessible to the user"""
        
        try:
            client = await self._get_client()
            
            # Validate user token
            user_token = user_context.get('user_token', '').strip()
            if not user_token:
                logger.error("No user token provided for Jenkins API call")
                return []
            
            # Use user token for authentication
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            # Get jobs from Jenkins API
            url = f"{self.base_url}/api/json"
            params = {"tree": "jobs[name,url,buildable,lastBuild[number,result,timestamp,duration]]"}
            
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            jobs = data.get("jobs", [])
            
            # Filter and enrich job data
            accessible_jobs = []
            for job in jobs:
                if self._is_job_accessible(job, user_context):
                    accessible_jobs.append({
                        "name": job.get("name"),
                        "url": job.get("url"),
                        "buildable": job.get("buildable", False),
                        "last_build": self._format_build_info(job.get("lastBuild"))
                    })
            
            logger.info("Retrieved user jobs",
                       user_id=user_context.get("user_id"),
                       job_count=len(accessible_jobs))
            
            return accessible_jobs
            
        except httpx.HTTPStatusError as e:
            logger.error("Jenkins API error getting jobs",
                        status_code=e.response.status_code,
                        error=str(e))
            return []
        except Exception as e:
            logger.error("Error getting user jobs", error=str(e))
            return []
    
    async def trigger_build(
        self, 
        job_name: str, 
        user_context: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Trigger a build for the specified job"""
        
        try:
            client = await self._get_client()
            
            # Validate user token
            user_token = user_context.get('user_token', '').strip()
            if not user_token:
                logger.error("No user token provided for build trigger", job_name=job_name)
                return False, "Authentication token missing", None
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Encode job name for URL
            encoded_job_name = quote(job_name, safe='')
            
            # Determine endpoint based on parameters
            if parameters:
                url = f"{self.base_url}/job/{encoded_job_name}/buildWithParameters"
                data = parameters
            else:
                url = f"{self.base_url}/job/{encoded_job_name}/build"
                data = {}
            
            response = await client.post(url, headers=headers, data=data)
            
            if response.status_code in [200, 201]:
                # Build triggered successfully
                queue_location = response.headers.get('Location')
                
                result = {
                    "success": True,
                    "message": f"Build triggered successfully for job '{job_name}'",
                    "queue_location": queue_location
                }
                
                # Try to get queue item info
                if queue_location:
                    queue_info = await self._get_queue_item_info(queue_location, headers)
                    if queue_info:
                        result.update(queue_info)
                
                return True, result["message"], result
                
            elif response.status_code == 403:
                return False, "Insufficient permissions to trigger this build", None
                
            elif response.status_code == 404:
                return False, f"Job '{job_name}' not found", None
                
            else:
                return False, f"Build trigger failed with status {response.status_code}", None
                
        except Exception as e:
            logger.error("Error triggering build",
                        error=str(e),
                        job_name=job_name,
                        user_id=user_context.get("user_id"))
            return False, f"Error triggering build: {str(e)}", None
    
    async def get_job_status(
        self, 
        job_name: str, 
        user_context: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Get status information for a job"""
        
        try:
            client = await self._get_client()
            
            # Validate user token
            user_token = user_context.get('user_token', '').strip()
            if not user_token:
                logger.error("No user token provided for job status", job_name=job_name)
                return False, None
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            
            encoded_job_name = quote(job_name, safe='')
            url = f"{self.base_url}/job/{encoded_job_name}/api/json"
            params = {
                "tree": "name,url,buildable,inQueue,lastBuild[number,result,timestamp,duration,url],lastSuccessfulBuild[number,timestamp],lastFailedBuild[number,timestamp]"
            }
            
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                status_info = {
                    "name": data.get("name"),
                    "url": data.get("url"),
                    "buildable": data.get("buildable", False),
                    "in_queue": data.get("inQueue", False),
                    "last_build": self._format_build_info(data.get("lastBuild")),
                    "last_successful_build": self._format_build_info(data.get("lastSuccessfulBuild")),
                    "last_failed_build": self._format_build_info(data.get("lastFailedBuild"))
                }
                
                return True, status_info
                
            elif response.status_code == 404:
                return False, None
                
            else:
                logger.warning("Unexpected status code getting job status",
                              status_code=response.status_code,
                              job_name=job_name)
                return False, None
                
        except Exception as e:
            logger.error("Error getting job status",
                        error=str(e),
                        job_name=job_name)
            return False, None
    
    async def get_build_log(
        self, 
        job_name: str, 
        build_number: str, 
        user_context: Dict[str, Any],
        start_line: int = 0,
        max_lines: int = 100
    ) -> Tuple[bool, Optional[str]]:
        """Get build console log"""
        
        try:
            client = await self._get_client()
            
            # Validate user token
            user_token = user_context.get('user_token', '').strip()
            if not user_token:
                logger.error("No user token provided for build log", job_name=job_name, build_number=build_number)
                return False, None
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Accept": "text/plain"
            }
            
            encoded_job_name = quote(job_name, safe='')
            url = f"{self.base_url}/job/{encoded_job_name}/{build_number}/logText/progressiveText"
            params = {"start": start_line}
            
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                log_text = response.text
                
                # Limit log length
                log_lines = log_text.split('\n')
                if len(log_lines) > max_lines:
                    log_lines = log_lines[-max_lines:]  # Get last N lines
                    log_text = '\n'.join(log_lines)
                    log_text = f"... (showing last {max_lines} lines)\n" + log_text
                
                return True, log_text
                
            elif response.status_code == 404:
                return False, None
                
            else:
                logger.warning("Unexpected status code getting build log",
                              status_code=response.status_code,
                              job_name=job_name,
                              build_number=build_number)
                return False, None
                
        except Exception as e:
            logger.error("Error getting build log",
                        error=str(e),
                        job_name=job_name,
                        build_number=build_number)
            return False, None
    
    async def cancel_build(
        self, 
        job_name: str, 
        build_number: str, 
        user_context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Cancel a running build"""
        
        try:
            client = await self._get_client()
            
            # Validate user token
            user_token = user_context.get('user_token', '').strip()
            if not user_token:
                logger.error("No user token provided for build cancel", job_name=job_name, build_number=build_number)
                return False, "Authentication token missing"
            
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            encoded_job_name = quote(job_name, safe='')
            url = f"{self.base_url}/job/{encoded_job_name}/{build_number}/stop"
            
            response = await client.post(url, headers=headers)
            
            if response.status_code in [200, 302]:  # 302 is redirect after successful stop
                return True, f"Build #{build_number} cancelled successfully"
            elif response.status_code == 403:
                return False, "Insufficient permissions to cancel this build"
            elif response.status_code == 404:
                return False, f"Build #{build_number} not found for job '{job_name}'"
            else:
                return False, f"Failed to cancel build (status: {response.status_code})"
                
        except Exception as e:
            logger.error("Error cancelling build",
                        error=str(e),
                        job_name=job_name,
                        build_number=build_number)
            return False, f"Error cancelling build: {str(e)}"
    
    def _is_job_accessible(self, job: Dict[str, Any], user_context: Dict[str, Any]) -> bool:
        """Check if job is accessible to user based on permissions"""
        
        # Basic check - if we can see the job in the API response, user likely has read access
        # More sophisticated permission checking would be done here in production
        user_permissions = user_context.get("permissions", [])
        
        # Must have at least Job.READ permission
        return "Job.READ" in user_permissions
    
    def _format_build_info(self, build_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Format build information for consistent response"""
        
        if not build_data:
            return None
        
        timestamp = build_data.get("timestamp", 0)
        duration = build_data.get("duration", 0)
        
        return {
            "number": build_data.get("number"),
            "result": build_data.get("result"),
            "timestamp": timestamp,
            "duration": duration,
            "url": build_data.get("url"),
            "formatted_timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp / 1000)) if timestamp else None,
            "formatted_duration": self._format_duration(duration) if duration else None
        }
    
    def _format_duration(self, duration_ms: int) -> str:
        """Format duration in milliseconds to human readable format"""
        
        if duration_ms < 1000:
            return f"{duration_ms}ms"
        
        seconds = duration_ms // 1000
        if seconds < 60:
            return f"{seconds}s"
        
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        
        if minutes < 60:
            if remaining_seconds > 0:
                return f"{minutes}m {remaining_seconds}s"
            else:
                return f"{minutes}m"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        else:
            return f"{hours}h"
    
    async def _get_queue_item_info(
        self, 
        queue_location: str, 
        headers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Get information about queued item"""
        
        try:
            client = await self._get_client()
            
            # Extract queue item ID from location header
            queue_id = queue_location.split('/')[-2] if '/' in queue_location else None
            if not queue_id:
                return None
            
            url = f"{self.base_url}/queue/item/{queue_id}/api/json"
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "queue_id": queue_id,
                    "why": data.get("why", "Waiting in queue"),
                    "blocked": data.get("blocked", False),
                    "buildable": data.get("buildable", True),
                    "stuck": data.get("stuck", False),
                    "in_queue_since": data.get("inQueueSince"),
                    "executable": data.get("executable", {}).get("number") if data.get("executable") else None
                }
            
            return None
            
        except Exception as e:
            logger.warning("Error getting queue item info", error=str(e))
            return None
    
    async def health_check(self) -> bool:
        """Check Jenkins API health"""
        
        try:
            client = await self._get_client()
            
            # Simple ping to Jenkins
            url = f"{self.base_url}/api/json"
            response = await client.get(url, timeout=5.0)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error("Jenkins health check failed", error=str(e))
            return False
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None