# Phase 3 Deployment Guide - Jenkins AI Chatbot

This guide covers the deployment of Phase 3, which completes the integration between Jenkins Plugin, AI Agent Service, and MCP Server.

## 🎯 Phase 3 Overview

Phase 3 implements the complete end-to-end integration:
- **Jenkins Plugin** → **AI Agent Service** → **Google Gemini API**
- **Optional MCP Server** integration for enhanced capabilities
- **Comprehensive error handling** and timeout management
- **Production-ready authentication** and security measures

## 🚀 Quick Deployment

### Prerequisites
- Phase 1 & 2 components deployed and working
- Google Gemini API key
- Jenkins instance running (v2.462.3+)
- Docker and Docker Compose

### 1. Update Environment Configuration

Edit `ai-agent/.env`:
```env
# AI Configuration (Required)
GEMINI_API_KEY=your-google-gemini-api-key-here

# Jenkins Integration
JENKINS_URL=http://localhost:8080
JENKINS_WEBHOOK_SECRET=your-webhook-secret

# MCP Server Integration (Optional)
MCP_SERVER_URL=http://localhost:8010
MCP_SERVER_AUTH=your-mcp-auth-token

# Security
SECRET_KEY=your-strong-secret-key-32-chars-minimum

# Database
DATABASE_URL=postgresql://chatbot_user:chatbot_db_pass@localhost:5432/jenkins_chatbot
REDIS_URL=redis://:chatbot_redis_pass@localhost:6379/0

# Performance
AI_REQUEST_TIMEOUT=30
CHAT_SESSION_TIMEOUT=900
MAX_CONCURRENT_REQUESTS=100
```

### 2. Deploy AI Agent Service

```bash
# Start infrastructure
docker-compose up -d redis postgres

# Deploy AI Agent with Phase 3 enhancements
docker-compose up -d ai-agent

# Verify health
curl http://localhost:8000/health
```

### 3. Deploy Jenkins Plugin

```bash
# Build updated plugin with AI Agent integration
cd jenkins-plugin
mvn clean package

# Upload jenkins-plugin/target/jenkins-chatbot.hpi to Jenkins
# Go to Manage Jenkins → Manage Plugins → Advanced → Upload Plugin

# Configure plugin
# Go to Manage Jenkins → Configure System → AI Chatbot
# Set AI Agent URL: http://localhost:8000
```

### 4. Test Phase 3 Integration

```bash
# Run comprehensive integration tests
export JENKINS_API_TOKEN="your-jenkins-api-token"
./scripts/test_phase3_integration.sh
```

## 🔧 Configuration Details

### AI Agent Service Configuration

**New Phase 3 Settings** in `ai-agent/.env`:
```env
# AI Processing Timeouts
AI_REQUEST_TIMEOUT=30          # Max time for AI processing
GEMINI_MAX_TOKENS=4000         # Max tokens per request
GEMINI_TEMPERATURE=0.7         # AI response creativity

# MCP Integration
MCP_SERVER_TIMEOUT=30          # MCP server timeout
MCP_SERVER_AUTH=               # Optional MCP authentication

# Error Handling
ENABLE_REQUEST_LOGGING=true    # Log all requests
ENABLE_SECURITY_EVENTS=true    # Log security events
AUDIT_LOG_RETENTION_DAYS=90    # Audit log retention

# Performance
MAX_CONCURRENT_SESSIONS=100    # Max concurrent chat sessions
RATE_LIMIT_PER_USER=60         # Rate limit per minute per user
CACHE_TTL_SECONDS=300          # Response cache duration
```

### Jenkins Plugin Configuration

**New Phase 3 Features**:
- Direct AI Agent Service communication
- Enhanced error handling with fallback responses
- Improved timeout management (35 second timeout)
- Better authentication token handling
- Connection pooling for performance

## 🔒 Security Enhancements

### Authentication Flow
1. User accesses Jenkins AI Assistant
2. Jenkins generates secure session token: `jenkins_token_{userId}_{sessionId}_{expiry}`
3. Token passed to AI Agent Service with user permissions
4. AI Agent validates token and processes with user context
5. All actions limited by user's Jenkins permissions

### Security Features
- **Token Expiry**: 15-minute session timeout
- **Permission Validation**: Every operation checked against user permissions
- **Audit Logging**: All interactions logged to PostgreSQL
- **Rate Limiting**: 60 requests per minute per user
- **Error Sanitization**: No sensitive data in error responses

## 🤖 AI Integration Features

### Intent Recognition
```yaml
build_trigger: ["build", "trigger", "start", "run", "execute"]
status_query: ["status", "check", "how", "running", "finished"] 
log_access: ["log", "console", "output", "error", "debug"]
job_listing: ["list", "show", "all", "jobs", "available"]
help_request: ["help", "what can", "guide", "tutorial"]
```

### MCP Server Integration (Optional)
- **Build Analysis**: Enhanced failure analysis and recommendations
- **Job Recommendations**: Context-aware job suggestions
- **Response Enhancement**: Improved AI responses with domain knowledge
- **Operation Validation**: Additional security validation layer

### Error Handling
- **AI Service Timeout**: 30-second timeout with graceful fallback
- **MCP Service Timeout**: 3-second timeout for optional features
- **Conversation Storage**: 5-second timeout for conversation updates
- **Fallback Responses**: Local pattern matching when AI unavailable

## 🔄 Operational Workflows

### MVP User Stories - Now Fully Functional

**1. Trigger Build**
```
User: "trigger the frontend build"
Flow: Jenkins → AI Agent → Intent: build_trigger → Permission Check → Response
Result: Build triggered if user has Job.BUILD permission
```

**2. Build Status Query**
```
User: "what's the status of my latest build?"
Flow: Jenkins → AI Agent → Jenkins API → Build Status → AI Response
Result: Current build status with details
```

**3. Permission-Aware Job Listing**
```
User: "list all jobs"
Flow: Jenkins → AI Agent → Permission Check → Job List → Filtered Response
Result: Only jobs user can access
```

**4. Build Log Access**
```
User: "show me the log for build #123"
Flow: Jenkins → AI Agent → Permission Check → Log Retrieval → Formatted Response
Result: Build console output if accessible
```

**5. Help & Discovery**
```
User: "what can you do?"
Flow: Jenkins → AI Agent → Permission Analysis → Contextual Help
Result: Capabilities based on user's permissions
```

## 📊 Monitoring & Observability

### Health Checks
- **AI Agent**: `GET /health` - Gemini API + MCP Server status
- **Jenkins Plugin**: Built-in health validation
- **Database**: Connection and performance monitoring
- **Redis**: Session storage health

### Metrics & Logging
```bash
# View AI Agent logs
docker-compose logs -f ai-agent

# View Jenkins plugin logs
tail -f $JENKINS_HOME/logs/jenkins.log | grep -i chatbot

# Monitor database performance
docker-compose exec postgres psql -U chatbot_user -d jenkins_chatbot -c "
SELECT 
    schemaname, tablename, 
    n_tup_ins as inserts, 
    n_tup_upd as updates, 
    n_tup_del as deletes 
FROM pg_stat_user_tables;"

# Check Redis sessions
docker-compose exec redis redis-cli --scan --pattern "session:*" | wc -l
```

### Performance Monitoring
- **Response Times**: Target <3 seconds for all operations
- **Error Rates**: Target <5% error rate
- **Session Health**: Monitor active sessions and cleanup
- **Token Usage**: Monitor Gemini API usage and costs

## 🚨 Troubleshooting

### Common Issues

**1. AI Agent Service Won't Start**
```bash
# Check logs
docker-compose logs ai-agent

# Common fixes:
# - Verify GEMINI_API_KEY is set
# - Check database connection
# - Ensure Redis is healthy
# - Validate environment variables
```

**2. Jenkins Plugin Not Connecting to AI Agent**
```bash
# Check Jenkins logs
tail -f $JENKINS_HOME/logs/jenkins.log | grep -i chatbot

# Test AI Agent connectivity from Jenkins host
curl -v http://localhost:8000/health

# Verify plugin configuration in Jenkins → Configure System
```

**3. Chat Responses Are Slow**
```bash
# Check AI Agent processing times
grep "processing_time_ms" logs/ai-agent.log

# Monitor Gemini API response times
grep "Gemini API" logs/ai-agent.log

# Check MCP server performance (if enabled)
curl -w "@curl-format.txt" -s -o /dev/null http://localhost:8010/health
```

**4. Authentication Errors**
```bash
# Verify token generation in Jenkins logs
grep "token" $JENKINS_HOME/logs/jenkins.log

# Check token validation in AI Agent
grep "token" logs/ai-agent.log

# Test session creation manually
curl -X POST http://localhost:8080/ai-assistant/apiSession \
  -u admin:your-api-token
```

### Performance Tuning

**AI Agent Service**:
```env
# Increase concurrency for high load
MAX_CONCURRENT_SESSIONS=200
MAX_CONCURRENT_REQUESTS=200

# Reduce timeouts for faster responses
AI_REQUEST_TIMEOUT=20
MCP_SERVER_TIMEOUT=2

# Enable caching
CACHE_TTL_SECONDS=600
```

**Jenkins Plugin**:
- Increase connection pool: Default 50 total, 10 per route
- Reduce timeouts for faster failures: 35s socket, 10s connection
- Monitor memory usage with large user bases

## 🎯 Success Criteria

Phase 3 is successful when:

### Functional Requirements
- [ ] All 5 MVP user stories work end-to-end
- [ ] Jenkins Plugin communicates with AI Agent Service
- [ ] AI responses are contextual and permission-aware
- [ ] Error handling provides graceful fallbacks
- [ ] Authentication and authorization work correctly

### Performance Requirements
- [ ] Response times under 3 seconds for 95% of requests
- [ ] Error rate below 5%
- [ ] System handles concurrent users without degradation
- [ ] Memory usage stable under load

### Security Requirements
- [ ] All requests properly authenticated
- [ ] User permissions enforced for all operations
- [ ] Audit logging captures all interactions
- [ ] No privilege escalation vulnerabilities
- [ ] Sensitive data not exposed in logs or errors

### Integration Requirements
- [ ] MCP server integration works (when available)
- [ ] Fallback modes work when MCP unavailable
- [ ] Database and Redis performance acceptable
- [ ] Monitoring and observability functional

## 🚀 Next Steps (Phase 4)

After successful Phase 3 deployment:

1. **Advanced AI Features**
   - Build failure analysis with recommendations
   - Intelligent job suggestions
   - Pipeline creation assistance
   - Historical trend analysis

2. **Enhanced User Experience**
   - Rich UI components for responses
   - Interactive action buttons
   - Real-time build notifications
   - Chat history search

3. **Enterprise Features**
   - Multi-tenant support
   - Advanced analytics
   - Custom AI model training
   - Integration with external tools

Phase 3 provides the solid foundation for these advanced features!