"""
Pydantic models for request/response validation
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class ChatRequest(BaseModel):
    """Request model for chat messages"""
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="Jenkins user ID")
    user_token: str = Field(..., description="Short-lived Jenkins token")
    permissions: List[str] = Field(default=[], description="User's Jenkins permissions")
    message: str = Field(..., min_length=1, max_length=1000, description="User's chat message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")

class Action(BaseModel):
    """Model for AI-planned actions"""
    type: str = Field(..., description="Action type (e.g., 'jenkins_api_call')")
    endpoint: Optional[str] = Field(None, description="API endpoint if applicable")
    method: Optional[str] = Field(None, description="HTTP method if applicable")
    requires_permission: Optional[str] = Field(None, description="Required Jenkins permission")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Action parameters")
    description: Optional[str] = Field(None, description="Human-readable description")

class ChatResponse(BaseModel):
    """Response model for chat messages"""
    response: str = Field(..., description="AI assistant response")
    actions: Optional[List[Action]] = Field(default=None, description="Planned actions")
    session_state: Optional[Dict[str, Any]] = Field(default=None, description="Updated session state")
    intent_detected: Optional[str] = Field(None, description="Detected user intent")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Response confidence")
    response_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    tool_results: Optional[List[Dict[str, Any]]] = Field(default=None, description="Tool execution results")

class SessionRequest(BaseModel):
    """Request model for session creation"""
    user_id: str = Field(..., description="Jenkins user ID")
    user_token: str = Field(..., description="Jenkins authentication token")
    permissions: List[str] = Field(default=[], description="User's Jenkins permissions")
    session_timeout: Optional[int] = Field(default=900, description="Session timeout in seconds")

class SessionResponse(BaseModel):
    """Response model for session operations"""
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="Jenkins user ID")
    user_token: str = Field(..., description="User authentication token")
    permissions: List[str] = Field(..., description="User's Jenkins permissions")
    conversation_history: Optional[List[Dict[str, Any]]] = Field(default=None, description="Recent conversation")
    pending_actions: Optional[List[Action]] = Field(default=None, description="Pending actions")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Session context")
    created_at: int = Field(..., description="Session creation timestamp")
    last_activity: Optional[int] = Field(None, description="Last activity timestamp")
    expires_at: int = Field(..., description="Session expiration timestamp")

class PermissionValidationRequest(BaseModel):
    """Request model for permission validation"""
    user_token: str = Field(..., description="Jenkins user token")
    action: str = Field(..., description="Action to validate")
    resource: Optional[str] = Field(None, description="Resource identifier")

class HealthResponse(BaseModel):
    """Response model for health checks"""
    status: str = Field(..., description="Overall service status")
    database_healthy: bool = Field(..., description="Database connection status")
    redis_healthy: bool = Field(..., description="Redis connection status")
    ai_service_healthy: bool = Field(..., description="AI service status")
    mcp_server_healthy: Optional[bool] = Field(None, description="MCP server status")
    jenkins_api_healthy: Optional[bool] = Field(None, description="Jenkins API status")
    active_sessions: Optional[int] = Field(None, description="Number of active sessions")
    timestamp: int = Field(..., description="Health check timestamp")

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    code: int = Field(..., description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: int = Field(..., description="Error timestamp")

class AuditLogEntry(BaseModel):
    """Model for audit log entries"""
    id: Optional[int] = Field(None, description="Log entry ID")
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Log timestamp")
    user_query: Optional[str] = Field(None, description="User's original query")
    ai_response: Optional[str] = Field(None, description="AI response")
    intent_detected: Optional[str] = Field(None, description="Detected intent")
    permissions_used: Optional[List[str]] = Field(default=None, description="Permissions checked")
    actions_planned: Optional[List[Action]] = Field(default=None, description="Planned actions")
    response_time_ms: Optional[int] = Field(None, description="Response time")
    success: bool = Field(True, description="Operation success status")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class SecurityEventEntry(BaseModel):
    """Model for security event logs"""
    id: Optional[int] = Field(None, description="Event ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    event_type: str = Field(..., description="Type of security event")
    user_id: Optional[str] = Field(None, description="User involved in event")
    session_id: Optional[str] = Field(None, description="Session identifier")
    source_ip: Optional[str] = Field(None, description="Source IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Event details")
    severity: str = Field(default="medium", description="Event severity level")
    resolved: bool = Field(default=False, description="Whether event was resolved")

class JenkinsApiCallLog(BaseModel):
    """Model for Jenkins API call audit logs"""
    id: Optional[int] = Field(None, description="Log entry ID")
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    ai_interaction_id: Optional[int] = Field(None, description="Related AI interaction ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Call timestamp")
    endpoint: str = Field(..., description="Jenkins API endpoint")
    method: str = Field(..., description="HTTP method")
    status_code: Optional[int] = Field(None, description="Response status code")
    permission_required: Optional[str] = Field(None, description="Required permission")
    permission_granted: bool = Field(..., description="Whether permission was granted")
    request_body: Optional[Dict[str, Any]] = Field(default=None, description="Request payload")
    response_body: Optional[Dict[str, Any]] = Field(default=None, description="Response payload")
    execution_time_ms: Optional[int] = Field(None, description="Execution time")
    user_token_hash: Optional[str] = Field(None, description="Hash of user token")
    error_details: Optional[str] = Field(None, description="Error details if failed")

# Conversation models
class ConversationMessage(BaseModel):
    """Model for individual conversation messages"""
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    user_id: Optional[str] = Field(None, description="User ID for user messages")
    actions_taken: Optional[List[str]] = Field(default=None, description="Actions taken")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

class ConversationContext(BaseModel):
    """Model for conversation context"""
    current_jobs: Optional[List[str]] = Field(default=None, description="Current jobs in context")
    last_build_status: Optional[Dict[str, str]] = Field(default=None, description="Last build statuses")
    workspace_info: Optional[str] = Field(None, description="Workspace information")
    pending_actions: Optional[List[Action]] = Field(default=None, description="Pending actions")

# Models for conversation service compatibility
class ChatMessage(BaseModel):
    """Chat message model for conversation service"""
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")

class UserContext(BaseModel):
    """User context model for conversation service"""
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier") 
    jenkins_token: str = Field(..., description="Jenkins authentication token")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    user_preferences: Optional[Dict[str, Any]] = Field(default=None, description="User preferences")

