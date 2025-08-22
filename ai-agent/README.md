# Jenkins AI Agent Service

**LLM-First AI Assistant for Jenkins Automation**

A production-ready FastAPI service that provides intelligent Jenkins automation through natural language processing. Built with Google Gemini AI and 21 specialized MCP tools for comprehensive Jenkins operations.

## 🚀 Quick Start

```bash
# 1. Clone and configure
cd ai-agent
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and Jenkins credentials

# 2. Start infrastructure services
docker-compose up -d redis postgres

# 3. Run development server
./scripts/start_dev.sh
```

**Service available at**: `http://localhost:8000`  
**API Documentation**: `http://localhost:8000/docs`  
**Health Check**: `http://localhost:8000/health`

## 📋 Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Services](#services)
- [MCP Tools](#mcp-tools)
- [Deployment](#deployment)
- [Security](#security)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## 🏗️ Architecture

### Service Overview
```
Browser → Jenkins Plugin → AI Agent Service (LLM-First) → Google Gemini API
                              ↓                            ↙
             Redis (sessions) + PostgreSQL (audit) + MCP Server (21 tools)
```

### Core Components

**AI Agent Service** (FastAPI + Google Gemini)
- **LLM-First Architecture**: Direct Gemini processing with intelligent tool selection
- **21 MCP Tools**: Dynamic discovery and universal tool execution
- **Multi-Tool Orchestration**: Complex queries using multiple Jenkins tools
- **Natural Language Understanding**: No hardcoded patterns - pure LLM intelligence
- **Iterative Tool Execution**: Multi-step operations for complex queries

**Infrastructure Services**
- **Redis**: Session management and conversation history
- **PostgreSQL**: Comprehensive audit logging and security events
- **MCP Server**: Enhanced Jenkins operations with 21 specialized tools

**Security & Monitoring**
- **Token-Based Authentication**: Delegated user permissions from Jenkins
- **Audit Trail**: Complete interaction logging and security events
- **Health Monitoring**: Service health checks and metrics (optional Prometheus/Grafana)

## ✨ Features

### 🤖 LLM-First Intelligence
- **Natural Language Processing**: Understand complex Jenkins queries in plain English
- **Intelligent Tool Selection**: Automatically choose the best MCP tools for each task
- **Multi-Step Operations**: Execute complex workflows spanning multiple Jenkins operations
- **Context Awareness**: Maintain conversation context for follow-up queries
- **Permission-Aware**: All operations respect user's actual Jenkins permissions

### 🔧 Jenkins Integration
- **21 MCP Tools Available**: Complete Jenkins API coverage through specialized tools
- **Real-time Operations**: Build triggers, status monitoring, log access
- **Job Management**: Create, configure, and manage Jenkins jobs
- **Build Pipeline Support**: Multi-stage pipeline operations and monitoring
- **Plugin Management**: Install, configure, and manage Jenkins plugins

### 🛡️ Security & Compliance
- **Delegated Authorization**: AI acts with user's exact Jenkins permissions
- **Session Management**: 15-minute token expiry with Redis storage
- **Comprehensive Audit**: All interactions logged to PostgreSQL
- **Security Events**: Suspicious activity detection and logging
- **CSRF Protection**: Automatic handling of Jenkins CSRF tokens

### 📊 Monitoring & Observability
- **Health Checks**: Service, database, and Redis health monitoring
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Performance Metrics**: Response times and success rates
- **Optional Monitoring Stack**: Prometheus + Grafana integration

## 🚀 Installation

### Development Setup

**Prerequisites**
- Python 3.11+
- Docker & Docker Compose
- Jenkins instance with API access

**Step 1: Environment Setup**
```bash
cd ai-agent
cp .env.example .env
```

**Step 2: Configure Environment**
```env
# Required Settings
GEMINI_API_KEY=your-google-gemini-api-key
JENKINS_URL=http://localhost:8080
JENKINS_USER=your-jenkins-username
JENKINS_API_TOKEN=your-jenkins-api-token
SECRET_KEY=your-secret-key-change-in-production

# Database URLs (configured for Docker Compose)
REDIS_URL=redis://:chatbot_redis_pass@localhost:6379/0
DATABASE_URL=postgresql+asyncpg://chatbot_user:chatbot_db_pass@localhost:5431/jenkins_chatbot
```

**Step 3: Start Infrastructure**
```bash
docker-compose up -d redis postgres
```

**Step 4: Development Server**
```bash
./scripts/start_dev.sh
```

### Production Deployment

**Full Stack with Docker Compose**
```bash
# Configure environment
cp .env.example .env
# Edit .env with production values

# Deploy all services
docker-compose up -d

# Check service health
curl http://localhost:8000/health
```

**Services Deployed:**
- `ai-agent`: Main AI service (port 8000)
- `mcp-server`: MCP tools server (port 8010)
- `redis`: Session storage (port 6379)
- `postgres`: Audit database (port 5431)
- `prometheus`: Metrics collection (port 9090) [optional]
- `grafana`: Monitoring dashboards (port 3000) [optional]

## ⚙️ Configuration

### Environment Variables

#### Core Settings
```env
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Security
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_ORIGINS=["*"]  # Restrict in production
```

#### AI Configuration
```env
# Google Gemini Settings
GEMINI_API_KEY=your-google-gemini-api-key
GEMINI_MODEL=gemini-1.5-pro
GEMINI_MAX_TOKENS=4000
GEMINI_TEMPERATURE=0.7

# LLM-First Architecture (production default)
USE_LLM_FIRST_ARCHITECTURE=true
```

#### MCP Server Configuration
```env
# MCP Integration
MCP_ENABLED=true
MCP_CONFIG_FILE=./mcp_servers.json
MCP_HTTP_HOST=mcp-server
MCP_HTTP_PORT=8010
MCP_CLIENT_TIMEOUT=30
```

#### Database Configuration
```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
DATABASE_POOL_SIZE=10
DATABASE_POOL_MAX_OVERFLOW=20

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_SESSION_TTL=3600
REDIS_CONVERSATION_TTL=86400
```

#### Jenkins Integration
```env
# Jenkins Settings
JENKINS_URL=http://localhost:8080
JENKINS_USER=your-username
JENKINS_API_TOKEN=your-api-token
JENKINS_API_TIMEOUT=30
```

#### Session Management
```env
CHAT_SESSION_TIMEOUT=900  # 15 minutes
MAX_CONVERSATION_LENGTH=50
USER_TOKEN_EXPIRY=900  # 15 minutes
```

### MCP Server Configuration

**File**: `mcp_servers.json` (copy from `mcp_servers.json.example`)

```json
{
  "discovery_enabled": true,
  "fallback_enabled": true,
  "connection_pooling": true,
  "cache_enabled": true,
  "cache_ttl_seconds": 300,
  "health_check_interval": 60,
  "max_concurrent_connections": 10,
  
  "servers": [
    {
      "name": "jenkins-primary",
      "url": "http://mcp-server:8010/mcp",
      "transport": "http",
      "priority": 1,
      "timeout": 30,
      "retry_count": 3,
      "enabled": true
    }
  ]
}
```

## 🔌 API Reference

### Authentication

All endpoints require Bearer token authentication:
```
Authorization: Bearer jenkins_token_{userId}_{sessionId}_{expiry}
```

Token format: `jenkins_token_{user_id}_{session_uuid}_{expiry_timestamp}`

### Endpoints

#### POST `/api/v1/chat`
Process chat message and return AI response with planned actions.

**Request:**
```json
{
  "session_id": "uuid",
  "user_id": "jenkins_username",
  "user_token": "jenkins_api_token",
  "permissions": ["Job.BUILD", "Job.READ"],
  "message": "What's the status of my build?",
  "context": {}
}
```

**Response:**
```json
{
  "response": "Your latest build for project-x completed successfully...",
  "actions": [
    {
      "type": "jenkins_api_call",
      "endpoint": "/job/project-x/lastBuild/api/json",
      "method": "GET",
      "requires_permission": "Job.READ",
      "parameters": {},
      "description": "Fetch latest build status"
    }
  ],
  "intent_detected": "build_status_query",
  "confidence_score": 0.95,
  "response_time_ms": 1250,
  "tool_results": [...]
}
```

#### POST `/api/v1/session/create`
Create new chat session with user context.

**Request:**
```json
{
  "user_id": "jenkins_username",
  "user_token": "jenkins_api_token", 
  "permissions": ["Job.BUILD", "Job.READ"],
  "session_timeout": 900
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "jenkins_username",
  "user_token": "jenkins_api_token",
  "permissions": ["Job.BUILD", "Job.READ"],
  "conversation_history": []
}
```

#### GET `/api/v1/session/{session_id}/state`
Get current session state and conversation history.

#### POST `/api/v1/permissions/validate`
Validate user permissions for specific action.

#### GET `/health`
Service health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "database_healthy": true,
  "redis_healthy": true,
  "ai_service_healthy": true,
  "timestamp": 1640995200000
}
```

## 🛠️ Services

### AIServiceLLMFirst
**Primary AI service with LLM-First architecture**

**Capabilities:**
- Direct Google Gemini integration with function calling
- Intelligent tool selection from 21 MCP tools
- Iterative tool execution for complex operations
- Natural language understanding without hardcoded patterns
- Context-aware conversation management

**Key Methods:**
- `process_message()`: Main message processing with tool orchestration
- `_discover_available_tools()`: Dynamic MCP tool discovery
- `health_check()`: Service health validation

### ConversationService
**Redis-backed session and conversation management**

**Features:**
- Session lifecycle management with automatic expiry
- Conversation history with configurable retention
- User context and permission tracking
- Health monitoring for Redis connectivity

### JenkinsService
**Direct Jenkins API integration**

**Operations:**
- Job management (create, configure, delete)
- Build operations (trigger, monitor, logs)
- System information and plugin management
- Permission-aware resource access

### MCPService
**MCP server integration with 21 specialized tools**

**Architecture:**
- Streamable HTTP transport for real-time communication
- Tool discovery and dynamic execution
- Connection pooling and caching
- Fallback and retry mechanisms

### AuditService
**Comprehensive audit logging and security events**

**Tracking:**
- All user interactions with full context
- Jenkins API calls with permission validation
- Security events and suspicious activity
- Performance metrics and response times

### PermissionService
**User authorization and security validation**

**Security Features:**
- Jenkins permission validation
- Session-based authorization
- Security event detection
- User context management

## 🔧 MCP Tools

The AI Agent leverages 21 specialized MCP tools for comprehensive Jenkins operations:

### Build Operations (6 tools)
- **trigger_build**: Start builds for specific jobs with parameters
- **get_build_status**: Check status of specific builds or latest builds
- **get_build_logs**: Access build console output and logs
- **stop_build**: Cancel running builds
- **get_build_artifacts**: Access build artifacts and downloadable files
- **get_build_test_results**: Access test results and reports

### Job Management (5 tools)
- **list_jobs**: List all jobs with filtering and permissions
- **get_job_details**: Get detailed job configuration and information
- **create_job**: Create new jobs with XML configuration
- **update_job**: Modify existing job configurations
- **delete_job**: Remove jobs (with permission validation)

### Node Management (3 tools)
- **list_nodes**: List all Jenkins nodes/agents
- **get_node_details**: Get detailed node information and status
- **manage_node**: Enable/disable nodes and manage availability

### System Operations (4 tools)
- **get_system_info**: Jenkins system information and version details
- **get_queue_info**: Build queue status and pending jobs
- **manage_plugins**: Plugin installation, updates, and management
- **system_health**: Overall system health and performance metrics

### User & Security (3 tools)
- **get_user_info**: User account information and permissions
- **validate_permissions**: Check user permissions for specific operations
- **security_audit**: Security configuration and audit information

### Tool Features
- **Dynamic Discovery**: Tools are automatically discovered at startup
- **Permission Validation**: Each tool validates user permissions before execution
- **Caching**: Results cached for performance optimization
- **Retry Logic**: Automatic retry with exponential backoff
- **Audit Trail**: All tool executions logged for security and compliance

## 🚀 Deployment

### Docker Compose (Recommended)

**Production Deployment:**
```bash
# Configure environment
cp .env.example .env
# Edit production values

# Deploy full stack
docker-compose up -d

# Verify deployment
curl http://localhost:8000/health
docker-compose ps
docker-compose logs ai-agent
```

### Kubernetes (Advanced)

**Deployment Structure:**
```yaml
# ai-agent-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jenkins-ai-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: jenkins-ai-agent
  template:
    spec:
      containers:
      - name: ai-agent
        image: jenkins-ai-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: ai-agent-secrets
              key: gemini-api-key
```

### Scaling Considerations

**Horizontal Scaling:**
- Stateless AI service design enables easy horizontal scaling
- Redis sessions shared across all instances
- PostgreSQL supports connection pooling
- MCP server can be scaled independently

**Resource Requirements:**
- **AI Agent**: 512MB RAM, 0.5 CPU per instance
- **MCP Server**: 256MB RAM, 0.25 CPU
- **Redis**: 128MB RAM, 0.1 CPU
- **PostgreSQL**: 1GB RAM, 0.5 CPU (varies with audit volume)

## 🛡️ Security

### Authentication & Authorization

**Token-Based Security:**
- Jenkins plugin generates time-limited tokens
- Format: `jenkins_token_{user_id}_{session_uuid}_{expiry}`
- 15-minute default expiry with automatic renewal
- All operations use delegated user permissions

**Permission Validation:**
```python
# Every operation validates permissions
result = await permission_service.validate_action(
    user_id=user_id,
    session_id=session_id,
    action="Job.BUILD",
    resource="job/my-project"
)
```

### Audit & Compliance

**Comprehensive Audit Trail:**
- All user interactions logged with full context
- Jenkins API calls tracked with permission validation
- Security events and suspicious activity detection
- 90-day retention period (configurable)

**Security Events Monitored:**
- Failed authentication attempts
- Permission violations
- Suspicious query patterns
- API abuse detection
- Token expiry and renewal events

### Data Protection

**Sensitive Data Handling:**
- Passwords and tokens never logged in plain text
- Database connections use SSL/TLS encryption
- Session data encrypted in Redis
- CSRF protection for all operations

## 📊 Monitoring

### Health Checks

**Service Health:**
```bash
# Overall service health
curl http://localhost:8000/health

# Response format
{
  "status": "ok|degraded|error",
  "database_healthy": true,
  "redis_healthy": true, 
  "ai_service_healthy": true,
  "timestamp": 1640995200000
}
```

**Component Health Checks:**
- **Database**: Connection and query performance
- **Redis**: Connection and basic operations
- **AI Service**: Gemini API connectivity and tool discovery
- **MCP Server**: Tool availability and response times

### Logging

**Structured JSON Logging:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "ai_service",
  "message": "Processing user query",
  "user_id": "john_doe",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "query_length": 45,
  "tools_used": ["get_build_status", "list_jobs"]
}
```

### Optional Monitoring Stack

**Enable with Docker Compose profiles:**
```bash
# Start with monitoring
docker-compose --profile monitoring up -d

# Access monitoring
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

**Metrics Collected:**
- Request response times and success rates
- Tool execution performance
- Database query performance
- Session creation and expiry rates
- Error rates by category

## 🔍 Troubleshooting

### Common Issues

#### 1. Service Won't Start
```bash
# Check logs
docker-compose logs ai-agent

# Common causes:
# - Missing GEMINI_API_KEY in .env
# - Database connection issues
# - Redis connection issues
# - Invalid SECRET_KEY configuration
```

#### 2. AI Service Health Check Fails
```bash
# Test Gemini API connectivity
python -c "
import google.generativeai as genai
genai.configure(api_key='YOUR_API_KEY')
model = genai.GenerativeModel('gemini-1.5-pro')
response = model.generate_content('Hello')
print('Gemini API working')
"
```

#### 3. MCP Tools Not Available
```bash
# Check MCP server health
curl http://localhost:8010/health

# Verify MCP configuration
cat mcp_servers.json

# Check MCP server logs
docker-compose logs mcp-server
```

#### 4. Database Connection Issues
```bash
# Test PostgreSQL connection
docker-compose exec postgres psql -U chatbot_user -d jenkins_chatbot -c "SELECT version();"

# Check database initialization
docker-compose logs postgres | grep "database system is ready"
```

#### 5. Authentication Failures
```bash
# Verify token format in logs
docker-compose logs ai-agent | grep "Token verification"

# Check Jenkins plugin token generation
# Look for malformed tokens or expired timestamps
```

### Debug Mode

**Enable detailed logging:**
```env
# In .env file
DEBUG=true
LOG_LEVEL=DEBUG
```

**Development debugging:**
```bash
# Start with hot reload
./scripts/start_dev.sh

# View real-time logs
docker-compose logs -f ai-agent
```

### Performance Issues

**High Response Times:**
- Check Gemini API rate limits and quotas
- Monitor MCP tool response times
- Verify database query performance
- Consider enabling caching (`MCP_CACHE_ENABLED=true`)

**Memory Issues:**
- Monitor conversation history length (`MAX_CONVERSATION_LENGTH`)
- Check Redis memory usage
- Verify no memory leaks in long-running sessions

## 🧪 Development

### Local Development Setup

**Prerequisites:**
```bash
# Python 3.11+
python --version

# Docker for infrastructure
docker --version
docker-compose --version
```

**Development Workflow:**
```bash
# 1. Clone and setup
cd ai-agent
cp .env.example .env

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Start infrastructure
docker-compose up -d redis postgres

# 5. Run tests
pytest test/

# 6. Start development server
uvicorn app.main:app --reload
```

### Testing

**Test Categories:**
```bash
# Unit tests
pytest test/test_ai_service.py
pytest test/test_jenkins_service.py

# Integration tests
pytest test/test_mcp_integration.py
pytest test/test_jenkins_integration.py

# End-to-end tests
./scripts/test_end_to_end.sh
```

**Test Configuration:**
```python
# test/conftest.py
import pytest
from app.config import Settings

@pytest.fixture
def test_settings():
    return Settings(
        GEMINI_API_KEY="test-key",
        JENKINS_URL="http://test-jenkins:8080",
        DATABASE_URL="sqlite:///:memory:",
        REDIS_URL="redis://test-redis:6379/1"
    )
```

### Code Quality

**Pre-commit hooks:**
```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

**Code formatting:**
```bash
# Black code formatter
black app/ test/

# Import sorting
isort app/ test/

# Type checking
mypy app/
```

### Contributing

**Development Standards:**
- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write comprehensive docstrings
- Include unit tests for new features
- Update API documentation for endpoint changes

**Pull Request Process:**
1. Fork and create feature branch
2. Implement changes with tests
3. Run full test suite
4. Update documentation
5. Submit pull request with detailed description

## 📄 License

This project is part of the Jenkins AI Chatbot system. See the main project repository for license information.

## 🤝 Support

For support and questions:
- **Issues**: Create GitHub issues for bugs and feature requests
- **Documentation**: Check the `docs/` directory for additional guides
- **Jenkins Integration**: See the main project README for end-to-end setup

---

**Built with**: FastAPI, Google Gemini AI, MCP Protocol, PostgreSQL, Redis, Docker