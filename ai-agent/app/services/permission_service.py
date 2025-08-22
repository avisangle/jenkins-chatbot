"""
Permission Service for validating user permissions and actions
Handles security validation and permission caching
"""

import time
from typing import Dict, List, Optional, Any, NamedTuple
import structlog
import redis.asyncio as redis

from app.config import settings
from app.redis_client import get_redis

logger = structlog.get_logger(__name__)

class ValidationResult(NamedTuple):
    """Result of permission validation"""
    valid: bool
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class PermissionService:
    """Service for permission validation and security checks"""
    
    def __init__(self):
        self.redis = None
        
        # Sensitive operations that require additional validation
        self.sensitive_permissions = {
            "Jenkins.ADMINISTER",
            "Job.DELETE", 
            "Job.CREATE",
            "Build.DELETE",
            "Jenkins.RUN_SCRIPTS"
        }
        
        # Operations blocked from AI automation
        self.blocked_operations = {
            "user_creation",
            "permission_modification", 
            "plugin_installation",
            "system_configuration",
            "credential_management"
        }
        
        # Permission mappings for actions
        self.action_permissions = {
            "build_job": "Job.BUILD",
            "trigger_build": "Job.BUILD",
            "read_job": "Job.READ",
            "list_jobs": "Job.READ", 
            "get_job_status": "Job.READ",
            "create_job": "Job.CREATE",
            "delete_job": "Job.DELETE",
            "configure_job": "Job.CONFIGURE",
            "read_build": "Job.READ",
            "get_build_log": "Job.READ",
            "get_build_status": "Job.READ",
            "delete_build": "Build.DELETE",
            "cancel_build": "Job.BUILD",
            "read_console": "Job.READ"
        }
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        if not self.redis:
            self.redis = await get_redis()
        return self.redis
    
    async def validate_session(
        self, 
        session_id: str, 
        user_id: str, 
        permissions: List[str]
    ) -> bool:
        """Validate session and cache permissions"""
        
        try:
            # Cache user permissions for faster access
            await self._cache_permissions(user_id, permissions)
            
            logger.info("Session validation successful",
                       session_id=session_id,
                       user_id=user_id,
                       permission_count=len(permissions))
            
            return True
            
        except Exception as e:
            logger.error("Session validation failed",
                        error=str(e),
                        session_id=session_id,
                        user_id=user_id)
            return False
    
    async def validate_action(
        self,
        user_id: str,
        session_id: str,
        action: str,
        resource: Optional[str] = None
    ) -> ValidationResult:
        """Validate if user can perform specific action"""
        
        try:
            # Check if operation is blocked
            if action in self.blocked_operations:
                await self._log_security_event(
                    "blocked_operation",
                    user_id,
                    session_id,
                    {"action": action, "resource": resource}
                )
                return ValidationResult(
                    valid=False,
                    message="This operation cannot be performed through the chatbot"
                )
            
            # Get required permission
            required_permission = self.action_permissions.get(action)
            if not required_permission:
                await self._log_security_event(
                    "unknown_action",
                    user_id,
                    session_id,
                    {"action": action, "resource": resource}
                )
                return ValidationResult(
                    valid=False,
                    message="Unknown operation"
                )
            
            # Check if user has required permission
            user_permissions = await self._get_cached_permissions(user_id)
            if not user_permissions:
                return ValidationResult(
                    valid=False,
                    message="Unable to verify permissions"
                )
            
            if required_permission not in user_permissions:
                await self._log_security_event(
                    "permission_denied",
                    user_id,
                    session_id,
                    {
                        "action": action,
                        "resource": resource,
                        "required_permission": required_permission,
                        "user_permissions": user_permissions
                    }
                )
                return ValidationResult(
                    valid=False,
                    message=f"Insufficient permissions. Required: {required_permission}"
                )
            
            # Additional validation for sensitive operations
            if required_permission in self.sensitive_permissions:
                sensitive_result = await self._validate_sensitive_operation(
                    action, resource, user_id, session_id
                )
                if not sensitive_result.valid:
                    return sensitive_result
            
            # Log successful validation
            await self._log_security_event(
                "action_validated",
                user_id,
                session_id,
                {
                    "action": action,
                    "resource": resource,
                    "permission": required_permission
                }
            )
            
            return ValidationResult(valid=True)
            
        except Exception as e:
            logger.error("Permission validation error",
                        error=str(e),
                        user_id=user_id,
                        action=action)
            
            await self._log_security_event(
                "validation_error",
                user_id,
                session_id,
                {"error": str(e), "action": action}
            )
            
            return ValidationResult(
                valid=False,
                message="Permission validation error"
            )
    
    async def validate_resource_access(
        self,
        user_id: str,
        resource_type: str,
        resource_name: str,
        permission_type: str
    ) -> ValidationResult:
        """Validate access to specific resource"""
        
        try:
            user_permissions = await self._get_cached_permissions(user_id)
            if not user_permissions:
                return ValidationResult(
                    valid=False,
                    message="Unable to verify permissions"
                )
            
            # Check general permission
            required_permission = f"{resource_type}.{permission_type}"
            if required_permission not in user_permissions:
                return ValidationResult(
                    valid=False,
                    message=f"Insufficient permissions for {resource_type} {permission_type}"
                )
            
            # TODO: Add resource-specific permission checks
            # This would integrate with Jenkins ACL system for fine-grained permissions
            
            return ValidationResult(valid=True)
            
        except Exception as e:
            logger.error("Resource access validation error",
                        error=str(e),
                        user_id=user_id,
                        resource_type=resource_type,
                        resource_name=resource_name)
            return ValidationResult(
                valid=False,
                message="Resource access validation error"
            )
    
    async def _validate_sensitive_operation(
        self,
        action: str,
        resource: Optional[str],
        user_id: str,
        session_id: str
    ) -> ValidationResult:
        """Additional validation for sensitive operations"""
        
        try:
            # Check session age for sensitive operations
            session_info = await self._get_session_info(session_id)
            if session_info:
                session_age = time.time() * 1000 - session_info.get("created_at", 0)
                max_age = 5 * 60 * 1000  # 5 minutes
                
                if session_age > max_age:
                    await self._log_security_event(
                        "stale_session_sensitive",
                        user_id,
                        session_id,
                        {"action": action, "session_age_ms": session_age}
                    )
                    return ValidationResult(
                        valid=False,
                        message="Please re-authenticate for sensitive operations"
                    )
            
            # Check for rate limiting on sensitive operations
            rate_limit_key = f"sensitive_ops:{user_id}"
            redis_client = await self._get_redis()
            
            current_count = await redis_client.get(rate_limit_key)
            current_count = int(current_count) if current_count else 0
            
            if current_count >= 5:  # Max 5 sensitive ops per hour
                await self._log_security_event(
                    "rate_limit_exceeded",
                    user_id,
                    session_id,
                    {"action": action, "current_count": current_count}
                )
                return ValidationResult(
                    valid=False,
                    message="Rate limit exceeded for sensitive operations"
                )
            
            # Increment rate limit counter
            await redis_client.setex(rate_limit_key, 3600, current_count + 1)  # 1 hour TTL
            
            return ValidationResult(valid=True)
            
        except Exception as e:
            logger.error("Sensitive operation validation error",
                        error=str(e),
                        action=action,
                        user_id=user_id)
            return ValidationResult(
                valid=False,
                message="Sensitive operation validation failed"
            )
    
    async def _cache_permissions(self, user_id: str, permissions: List[str]) -> bool:
        """Cache user permissions in Redis"""
        
        try:
            redis_client = await self._get_redis()
            
            permission_data = {
                "permissions": permissions,
                "cached_at": int(time.time() * 1000)
            }
            
            cache_key = f"permissions:{user_id}"
            import json
            await redis_client.setex(
                cache_key,
                300,  # 5 minutes TTL
                json.dumps(permission_data)
            )
            
            return True
            
        except Exception as e:
            logger.error("Error caching permissions",
                        error=str(e),
                        user_id=user_id)
            return False
    
    async def _get_cached_permissions(self, user_id: str) -> Optional[List[str]]:
        """Get cached user permissions"""
        
        try:
            redis_client = await self._get_redis()
            cache_key = f"permissions:{user_id}"
            
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                import json
                data = json.loads(cached_data)
                return data.get("permissions", [])
            
            return None
            
        except Exception as e:
            logger.error("Error getting cached permissions",
                        error=str(e),
                        user_id=user_id)
            return None
    
    async def _get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information for validation"""
        
        try:
            redis_client = await self._get_redis()
            
            # Search for session
            pattern = f"session:*:{session_id}"
            async for key in redis_client.scan_iter(match=pattern):
                session_data = await redis_client.get(key)
                if session_data:
                    import json
                    return json.loads(session_data)
            
            return None
            
        except Exception as e:
            logger.error("Error getting session info",
                        error=str(e),
                        session_id=session_id)
            return None
    
    async def _log_security_event(
        self,
        event_type: str,
        user_id: str,
        session_id: str,
        details: Dict[str, Any]
    ) -> bool:
        """Log security event"""
        
        try:
            # In production, this would write to PostgreSQL audit table
            # For now, log to structured logger
            logger.warning("SECURITY_EVENT",
                          event_type=event_type,
                          user_id=user_id,
                          session_id=session_id,
                          details=details,
                          timestamp=int(time.time() * 1000))
            
            return True
            
        except Exception as e:
            logger.error("Error logging security event",
                        error=str(e),
                        event_type=event_type)
            return False
    
    async def check_rate_limit(
        self,
        user_id: str,
        operation_type: str = "general",
        window_seconds: int = 60,
        max_requests: int = 10
    ) -> ValidationResult:
        """Check rate limiting for user operations"""
        
        try:
            redis_client = await self._get_redis()
            
            # Use sliding window rate limiting
            now = time.time()
            window_start = now - window_seconds
            
            rate_limit_key = f"rate_limit:{user_id}:{operation_type}"
            
            # Remove old entries
            await redis_client.zremrangebyscore(rate_limit_key, 0, window_start)
            
            # Count current requests in window
            current_count = await redis_client.zcard(rate_limit_key)
            
            if current_count >= max_requests:
                return ValidationResult(
                    valid=False,
                    message=f"Rate limit exceeded: {max_requests} requests per {window_seconds} seconds"
                )
            
            # Add current request
            await redis_client.zadd(rate_limit_key, {str(now): now})
            await redis_client.expire(rate_limit_key, window_seconds)
            
            return ValidationResult(valid=True)
            
        except Exception as e:
            logger.error("Rate limit check error",
                        error=str(e),
                        user_id=user_id,
                        operation_type=operation_type)
            return ValidationResult(
                valid=False,
                message="Rate limit check failed"
            )
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired permission cache entries"""
        
        try:
            redis_client = await self._get_redis()
            
            # Redis TTL handles most cleanup, but we can do additional cleanup here
            pattern = "permissions:*"
            cleaned_count = 0
            
            async for key in redis_client.scan_iter(match=pattern):
                ttl = await redis_client.ttl(key)
                if ttl == -1:  # No TTL set
                    await redis_client.expire(key, 300)  # Set 5 minute TTL
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info("Cleaned up permission cache entries", count=cleaned_count)
            
            return cleaned_count
            
        except Exception as e:
            logger.error("Error cleaning up permission cache", error=str(e))
            return 0