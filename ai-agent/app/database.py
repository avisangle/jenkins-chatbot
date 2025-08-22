"""
Database configuration and setup for PostgreSQL
Handles SQLAlchemy async engine and session management
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.config import settings

logger = structlog.get_logger(__name__)

# Database engine and session factory
engine = None
SessionLocal = None

# Base class for models
Base = declarative_base()

class AuditLogTable(Base):
    """Database table for AI interaction audit logs"""
    __tablename__ = "ai_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_query = Column(Text, nullable=False)
    ai_response = Column(Text)
    intent_detected = Column(String(255))
    permissions_used = Column(JSON)  # Array of permissions
    actions_planned = Column(JSON)   # Array of planned actions
    response_time_ms = Column(Integer)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text)

class JenkinsApiCallTable(Base):
    """Database table for Jenkins API call audit logs"""
    __tablename__ = "jenkins_api_calls"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    ai_interaction_id = Column(Integer, ForeignKey("ai_interactions.id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    endpoint = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer)
    permission_required = Column(String(255))
    permission_granted = Column(Boolean, nullable=False)
    request_body = Column(JSON)
    response_body = Column(JSON)
    execution_time_ms = Column(Integer)
    user_token_hash = Column(String(255))
    error_details = Column(Text)

class SecurityEventTable(Base):
    """Database table for security events"""
    __tablename__ = "security_events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    user_id = Column(String(255), index=True)
    session_id = Column(UUID(as_uuid=True), index=True)
    source_ip = Column(String(45))  # Support IPv6
    user_agent = Column(Text)
    details = Column(JSON)
    severity = Column(String(20), default="medium", nullable=False, index=True)
    resolved = Column(Boolean, default=False, nullable=False, index=True)

async def init_database():
    """Initialize database connection and create tables"""
    global engine, SessionLocal
    
    try:
        # Create async engine
        engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_POOL_MAX_OVERFLOW,
            pool_pre_ping=True,
            echo=settings.DEBUG  # Log SQL queries in debug mode
        )
        
        # Create session factory
        SessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully",
                   url=settings.DATABASE_URL.split('@')[-1])  # Log without credentials
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise

async def close_database():
    """Close database connections"""
    global engine
    
    try:
        if engine:
            await engine.dispose()
            logger.info("Database connections closed")
    except Exception as e:
        logger.error("Error closing database", error=str(e))

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session with automatic cleanup"""
    if not SessionLocal:
        raise RuntimeError("Database not initialized")
    
    async with SessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", error=str(e))
            raise
        finally:
            await session.close()

async def health_check() -> bool:
    """Check database health"""
    try:
        if not engine:
            return False
            
        async with get_db_session() as db:
            # Simple query to test connection
            result = await db.execute("SELECT 1")
            return result.scalar() == 1
            
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False