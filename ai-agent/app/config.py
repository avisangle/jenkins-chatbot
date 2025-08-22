"""
Configuration settings for Jenkins AI Agent Service
"""

import os
from typing import List, Dict, Any
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALLOWED_ORIGINS: List[str] = ["*"]  # Restrict in production
    
    # Gemini AI Configuration
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"
    GEMINI_MAX_TOKENS: int = 4000
    GEMINI_TEMPERATURE: float = 0.7
    
    # MCP Server Integration (using streamable HTTP transport)
    MCP_SERVER_SCRIPT_PATH: str = "/app/jenkins_mcp_server_enhanced.py"
    MCP_CLIENT_TIMEOUT: int = 30
    MCP_ENABLED: bool = True
    MCP_TRANSPORT: str = "streamable-http"
    MCP_HTTP_PORT: int = 8010
    MCP_HTTP_HOST: str = "mcp-server"
    MCP_HTTP_ENDPOINT: str = "/mcp"
    
    # Universal MCP Configuration - JSON File Based
    MCP_CONFIG_FILE: str = "./mcp_servers.json"
    MCP_DISCOVERY_ENABLED: bool = True  # Can be overridden by JSON config
    MCP_FALLBACK_ENABLED: bool = True   # Can be overridden by JSON config
    MCP_LOAD_BALANCING: bool = False    # Can be overridden by JSON config
    MCP_CONNECTION_POOLING: bool = True # Can be overridden by JSON config
    MCP_CACHE_ENABLED: bool = True      # Can be overridden by JSON config
    MCP_CACHE_TTL_SECONDS: int = 300    # Can be overridden by JSON config
    MCP_HEALTH_CHECK_INTERVAL: int = 60 # Can be overridden by JSON config
    MCP_MAX_CONCURRENT_CONNECTIONS: int = 10  # Can be overridden by JSON config
    
    # Jenkins Integration
    JENKINS_URL: str = "http://localhost:8080"
    JENKINS_WEBHOOK_SECRET: str = ""
    JENKINS_API_TIMEOUT: int = 30
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    REDIS_SESSION_TTL: int = 3600  # 1 hour
    REDIS_CONVERSATION_TTL: int = 86400  # 24 hours
    
    # PostgreSQL Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/jenkins_ai_agent"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_POOL_MAX_OVERFLOW: int = 20
    
    # Session Management
    CHAT_SESSION_TIMEOUT: int = 900  # 15 minutes
    MAX_CONVERSATION_LENGTH: int = 50
    USER_TOKEN_EXPIRY: int = 900  # 15 minutes
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    
    
    # Audit and Security
    AUDIT_LOG_RETENTION_DAYS: int = 90
    ENABLE_REQUEST_LOGGING: bool = True
    ENABLE_SECURITY_EVENTS: bool = True
    
    # Performance
    MAX_CONCURRENT_REQUESTS: int = 100
    AI_REQUEST_TIMEOUT: int = 30
    CACHE_TTL_SECONDS: int = 300  # 5 minutes
    
    # LLM-First Architecture (now default)
    USE_LLM_FIRST_ARCHITECTURE: bool = True  # LLM-First is now the production architecture
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# Global settings instance
settings = Settings()

# Validation
def validate_settings():
    """Validate critical settings"""
    errors = []
    
    if not settings.GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is required")
    
    if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key-change-in-production":
        errors.append("SECRET_KEY must be set and changed from default")
    
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    
    if not settings.REDIS_URL:
        errors.append("REDIS_URL is required")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"- {error}" for error in errors))

# Validate on import
validate_settings()