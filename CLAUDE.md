# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Jenkins AI Chatbot with intelligent LLM-First architecture: a Jenkins Plugin (Java) that provides UI integration, and an AI Agent Service (Python/FastAPI) that handles natural language processing via Google Gemini API with access to 21 MCP tools. The system uses intelligent tool selection and implements delegated authorization where the AI agent acts on behalf of users using their Jenkins permissions.

### Architecture Highlights
- **LLM-First Intelligence**: Direct Gemini processing with intelligent tool selection (production default)
- **21 MCP Tools Available**: Dynamic discovery and universal tool execution  
- **Multi-Tool Orchestration**: Complex queries using multiple Jenkins tools
- **Natural Language Understanding**: No hardcoded patterns - pure LLM intelligence
- **Iterative Tool Execution**: Multi-step operations for complex queries

## Development Commands

### Environment Setup
```bash
# Copy environment configuration
cp ai-agent/.env.example ai-agent/.env
# Edit ai-agent/.env with your GEMINI_API_KEY and other settings

# Start infrastructure services (Redis + PostgreSQL)
docker-compose up -d redis postgres

# Development mode (AI Agent Service)
cd ai-agent && ./scripts/start_dev.sh

# Full stack deployment
docker-compose up -d
```

### Build Commands
```bash
# Build Jenkins Plugin
cd jenkins-plugin
mvn clean package
# Outputs: target/jenkins-chatbot.hpi

# Build AI Agent Service Docker image
cd ai-agent
docker build -t jenkins-chatbot-ai-agent .

# Build all services
docker-compose build
```

### Testing Commands
```bash
# Test AI Agent Service endpoints
python scripts/test_api.py

# Test Jenkins Plugin integration
./scripts/test_jenkins_plugin.sh

# Test complete end-to-end flow
JENKINS_API_TOKEN="your-token" ./scripts/test_end_to_end.sh

# Test individual components
./scripts/test_ai_agent.sh          # AI service health
./scripts/test_csrf_flow.sh         # CSRF token handling
```

### Development Workflow
```bash
# Start development environment
./scripts/start_dev.sh

# Install Jenkins plugin for testing
# 1. Build: cd jenkins-plugin && mvn clean package  
# 2. Upload target/jenkins-chatbot.hpi to Jenkins → Manage Plugins → Advanced
# 3. Configure AI Agent URL in Jenkins → Configure System → AI Chatbot

# Monitor logs
docker-compose logs -f ai-agent
docker-compose logs -f postgres redis
```

## Architecture Overview

### Service Architecture
```
Browser → Jenkins Plugin UI → REST/WebSocket → AI Agent Service (LLM-First) → Gemini API
                                               ↓                            ↙
                               Redis (sessions) + PostgreSQL (audit) + MCP Server (21 tools)
```

### Key Components

**Jenkins Plugin** (`jenkins-plugin/src/main/java/io/jenkins/plugins/chatbot/`)
- `ChatbotRootAction.java` - Sidebar "AI Assistant" link and session creation
- `ChatApiHandler.java` - MVP user stories implementation with pattern matching
- `ChatSessionManager.java` - Token generation and session lifecycle
- `SecurityManager.java` - Permission validation and user context
- `ChatWebSocketHandler.java` - Real-time communication support

**AI Agent Service - LLM-First Architecture** (`ai-agent/app/`)
- `main.py` - FastAPI application with intelligent service selection
- `services/ai_service_llm_first.py` - **Primary**: LLM-driven tool selection with 21 MCP tools
- `services/ai_service.py` - **Deprecated**: Legacy fallback service
- `services/conversation_service.py` - Redis-backed session management
- `services/permission_service.py` - User authorization validation
- `services/jenkins_service.py` - Jenkins API integration
- `services/mcp_service.py` - MCP server integration (21 tools)
- `services/audit_service.py` - PostgreSQL audit logging

**Frontend** (`jenkins-plugin/src/main/webapp/chat-interface.js`)
- REST API communication (no WebSocket dependency)
- CSRF token handling and authentication
- Message formatting and error handling

### Authentication Flow
1. User accesses `/ai-assistant/` in Jenkins
2. Jenkins plugin generates token: `jenkins_token_{userId}_{sessionId}_{expiry}`
3. Frontend uses token for AI Agent Service authentication
4. AI Agent validates token format and expiry
5. All operations use delegated user permissions

### MVP User Stories Implementation
Located in `ChatApiHandler.java` with pattern-based intent recognition:
1. **Trigger Build** - Pattern: "trigger", "build", "start"
2. **Build Status Query** - Pattern: "status", "check", "how"  
3. **Permission-Aware Job Listing** - Pattern: "list", "jobs", "show"
4. **Build Log Access** - Pattern: "log", "console", "output"
5. **Help & Discovery** - Pattern: "help", "what can", "guide"

## Configuration

### Environment Variables (ai-agent/.env)
```env
GEMINI_API_KEY=your-google-gemini-api-key
JENKINS_URL=http://localhost:8080
MCP_SERVER_URL=http://localhost:8010
SECRET_KEY=your-secret-key-change-in-production
DATABASE_URL=postgresql://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0
```

### Jenkins Plugin Configuration
- Navigate to Manage Jenkins → Configure System → AI Chatbot
- Set AI Agent URL (default: http://localhost:8000)
- Plugin automatically appears as "AI Assistant" in sidebar for authorized users

## Security Model

- **Delegated Authorization**: AI Agent operates with user's Jenkins permissions only
- **Session Management**: 15-minute token expiry with Redis storage
- **Audit Logging**: All interactions logged to PostgreSQL with user context
- **Permission Validation**: Every action validated against user's Jenkins permissions
- **CSRF Protection**: Frontend handles Jenkins CSRF tokens automatically

## Database Schema

PostgreSQL tables (see `init.sql`):
- `chat_sessions` - Session tracking with user context
- `chat_interactions` - Message history and audit trail
- `user_permissions` - Permission caching and validation
- `security_events` - Security violations and suspicious activity

## Integration Points

### MCP Server Integration
- Configured via `MCP_SERVER_URL` environment variable  
- Used for advanced Jenkins operations and tool calling
- Fallback to direct Jenkins API when MCP unavailable

### Jenkins API Integration
- Direct REST API calls for job operations
- User token delegation for authentication
- Permission-aware resource access

## Troubleshooting

### Common Issues
- **Plugin not loading**: Check Java 11+ and Jenkins version 2.462.3+
- **AI Agent connection**: Verify GEMINI_API_KEY and service health at `/health`
- **Database errors**: Ensure PostgreSQL is running and `init.sql` executed
- **Session failures**: Check Redis connectivity and token format
- **Permission errors**: Verify user has required Jenkins permissions

### Log Locations
- AI Agent Service: `docker-compose logs ai-agent`
- Jenkins Plugin: `$JENKINS_HOME/logs/jenkins.log`
- Database: `docker-compose logs postgres`
- Redis: `docker-compose logs redis`

## Development Notes

### Adding New MVP Stories
1. Add intent patterns to `ai_service.py` → `intent_patterns`
2. Implement handler in `ChatApiHandler.java` → `processUserMessage()`
3. Add action parsing in `ai_service.py` → `_parse_actions()`
4. Update tests in `scripts/test_end_to_end.sh`

### Extending AI Capabilities
- Modify system prompts in `ai_service.py` → `_build_system_prompt()`
- Add new service methods in `jenkins_service.py`
- Enhance intent detection with additional patterns
- Integrate MCP server tools via `mcp_service.py`

### Plugin Development
- Java 11+ with Maven for builds
- Follow Jenkins plugin conventions for security
- Use `@Extension` for auto-discovery
- Implement proper permission checks for all endpoints