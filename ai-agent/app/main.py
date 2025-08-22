"""
Jenkins AI Agent Service
FastAPI service that provides AI-powered chat interface for Jenkins operations
"""

import os
import logging
import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from app.config import settings
from app.models import ChatRequest, ChatResponse, SessionRequest, SessionResponse, HealthResponse
from app.services.ai_service import AIService
from app.services.ai_service_llm_first import AIServiceLLMFirst
from app.services.conversation_service import ConversationService
from app.services.permission_service import PermissionService
from app.services.jenkins_service import JenkinsService
from app.services.audit_service import AuditService
from app.database import init_database, close_database
from app.redis_client import init_redis, close_redis

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Security
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Jenkins AI Agent service", version="1.0.0")
    
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized")
        
        # Initialize Redis
        await init_redis()
        logger.info("Redis initialized")
        
        # Initialize AI services (support both architectures)
        if settings.USE_LLM_FIRST_ARCHITECTURE:
            app.state.ai_service = AIServiceLLMFirst()
            logger.info("Initialized LLM-First AI Service")
        else:
            app.state.ai_service = AIService()
            logger.info("Initialized Legacy AI Service")
        app.state.conversation_service = ConversationService()
        app.state.permission_service = PermissionService()
        app.state.jenkins_service = JenkinsService()
        app.state.audit_service = AuditService()
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Jenkins AI Agent service")
    
    try:
        await close_redis()
        await close_database()
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

# Create FastAPI application
app = FastAPI(
    title="Jenkins AI Agent",
    description="AI-powered assistant for Jenkins automation and management",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token from Jenkins plugin"""
    try:
        # Extract token from credentials
        token = credentials.credentials
        
        # Validate token format (jenkins_token_userId_sessionId_expiry)
        if not token.startswith("jenkins_token_"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
        
        # Parse token components using regex for more robust parsing
        # Expected format: jenkins_token_{user_id}_{session_uuid}_{expiry}
        import re
        
        # Pattern: jenkins_token_<userid>_<uuid>_<timestamp>
        # UUID pattern: 8-4-4-4-12 hex digits with dashes
        pattern = r"jenkins_token_(.+)_([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})_(\d+)"
        match = re.match(pattern, token, re.IGNORECASE)
        
        if not match:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token - regex parse failed"
            )
        
        user_id = match.group(1)
        session_id = match.group(2)
        expiry = int(match.group(3))
        
        # Check token expiry
        current_time_ms = time.time() * 1000
        logger.info("Token verification", 
                   current_time=current_time_ms,
                   token_expiry=expiry, 
                   user_id=user_id,
                   session_id=session_id)
        
        if current_time_ms > expiry:
            logger.warning("Token expired", 
                         current_time=current_time_ms,
                         token_expiry=expiry,
                         difference_ms=current_time_ms - expiry)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        
        return user_id, session_id
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )
    except Exception as e:
        logger.error("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    token_info = Depends(verify_token)
) -> ChatResponse:
    """
    Process chat message and return AI response with planned actions
    """
    user_id, session_id = token_info
    
    # Validate request
    if request.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session mismatch"
        )
    
    if request.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User mismatch"
        )
    
    try:
        # Log interaction start
        interaction_id = await app.state.audit_service.log_interaction_start(
            session_id=session_id,
            user_id=user_id,
            query=request.message,
            permissions=request.permissions
        )
        
        # Validate user permissions
        permission_valid = await app.state.permission_service.validate_session(
            session_id=session_id,
            user_id=user_id,
            permissions=request.permissions
        )
        
        if not permission_valid:
            await app.state.audit_service.log_security_event(
                event_type="invalid_permissions",
                user_id=user_id,
                session_id=session_id,
                details={"error": "Permission validation failed"}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid permissions"
            )
        
        # Process message through AI with timeout
        try:
            ai_response = await asyncio.wait_for(
                app.state.ai_service.process_message(
                    message=request.message,
                    user_context={
                        "user_id": user_id,
                        "session_id": session_id,
                        "user_token": request.user_token,
                        "permissions": request.permissions,
                        "context": request.context
                    },
                    conversation_service=app.state.conversation_service
                ),
                timeout=30.0  # 30 second timeout for AI processing
            )
        except asyncio.TimeoutError:
            logger.error("AI processing timeout", user_id=user_id, session_id=session_id)
            # Return timeout fallback response
            ai_response = ChatResponse(
                response="I'm sorry, but processing your request is taking longer than expected. Please try again with a simpler request.",
                actions=[],
                intent_detected="timeout",
                response_time_ms=30000,
                confidence_score=0.0
            )
        
        # Update conversation history with error handling
        try:
            await asyncio.wait_for(
                app.state.conversation_service.add_interaction(
                    session_id=session_id,
                    user_message=request.message,
                    ai_response=ai_response.response,
                    actions=ai_response.actions,
                    tool_results=ai_response.tool_results
                ),
                timeout=5.0  # 5 second timeout for conversation update
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("Failed to update conversation history", 
                          error=str(e), session_id=session_id)
            # Continue without failing the request
        
        # Log successful interaction
        await app.state.audit_service.log_interaction_complete(
            interaction_id=interaction_id,
            response=ai_response.response,
            actions=ai_response.actions,
            success=True
        )
        
        return ai_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing chat message", 
                    error=str(e), user_id=user_id, session_id=session_id)
        
        # Log error
        await app.state.audit_service.log_interaction_complete(
            interaction_id=interaction_id,
            response="",
            actions=[],
            success=False,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post("/api/v1/session/create", response_model=SessionResponse)
async def create_session(request: SessionRequest) -> SessionResponse:
    """
    Create a new chat session with user context
    """
    try:
        session = await app.state.conversation_service.create_session(
            user_id=request.user_id,
            user_token=request.user_token,
            permissions=request.permissions,
            timeout=request.session_timeout or 900  # 15 minutes default
        )
        
        logger.info("Created new session", 
                   session_id=session["session_id"], 
                   user_id=request.user_id)
        
        return SessionResponse(**session)
        
    except Exception as e:
        logger.error("Error creating session", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )

@app.get("/api/v1/session/{session_id}/state", response_model=SessionResponse)
async def get_session_state(
    session_id: str,
    token_info = Depends(verify_token)
) -> SessionResponse:
    """
    Get current session state
    """
    user_id, verified_session_id = token_info
    
    if session_id != verified_session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session access denied"
        )
    
    try:
        session = await app.state.conversation_service.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session access denied"
            )
        
        return SessionResponse(**session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving session", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session"
        )

@app.post("/api/v1/permissions/validate")
async def validate_permissions(
    request: dict,
    token_info = Depends(verify_token)
) -> dict:
    """
    Validate user permissions for specific action
    """
    user_id, session_id = token_info
    
    try:
        result = await app.state.permission_service.validate_action(
            user_id=user_id,
            session_id=session_id,
            action=request.get("action"),
            resource=request.get("resource")
        )
        
        return {"valid": result.valid, "message": result.message}
        
    except Exception as e:
        logger.error("Error validating permissions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Permission validation failed"
        )

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    """
    try:
        # Check database connection
        db_healthy = await app.state.conversation_service.health_check()
        
        # Check Redis connection
        redis_healthy = await app.state.conversation_service.redis_health_check()
        
        # Check AI service
        ai_healthy = await app.state.ai_service.health_check()
        
        return HealthResponse(
            status="ok" if all([db_healthy, redis_healthy, ai_healthy]) else "degraded",
            database_healthy=db_healthy,
            redis_healthy=redis_healthy,
            ai_service_healthy=ai_healthy,
            timestamp=int(time.time() * 1000)
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthResponse(
            status="error",
            database_healthy=False,
            redis_healthy=False,
            ai_service_healthy=False,
            timestamp=int(time.time() * 1000)
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler with logging"""
    from fastapi.responses import JSONResponse
    logger.warning("HTTP exception", 
                  status_code=exc.status_code, 
                  detail=exc.detail,
                  path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    from fastapi.responses import JSONResponse
    logger.error("Unhandled exception", 
                error=str(exc), 
                path=request.url.path,
                method=request.method)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )