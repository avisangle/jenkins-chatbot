# Jenkins AI Chatbot MVP - Setup Guide

This guide walks you through setting up and deploying the Jenkins AI Chatbot MVP according to Phase 2 of the implementation plan.

## Architecture Overview

```
User Browser → Jenkins Plugin UI → WebSocket/REST API → AI Agent Service → Claude API
                                                      ↓
                                   Redis (sessions) + PostgreSQL (audit) + MCP Server
```

## Prerequisites

1. **Development Environment**
   - Java 11+ and Maven 3.6+ (for Jenkins plugin)
   - Python 3.11+ (for AI Agent service)  
   - Docker and Docker Compose
   - Git

2. **Required API Keys & Services**
   - Google Gemini API key (from Google AI Studio)
   - Running Jenkins instance (v2.414.3+)
   - Your existing MCP server (optional but recommended)

3. **System Requirements**
   - 4GB RAM minimum for development
   - 8GB RAM recommended for full deployment

## Quick Start (Development Mode)

### 1. Clone and Configure

```bash
# Clone the repository (if not already done)
cd jenkins-chatbot-project

# Copy and configure AI Agent environment
cp ai-agent/.env.example ai-agent/.env
```

Edit `ai-agent/.env` with your values:
```env
GEMINI_API_KEY=your-google-gemini-api-key-here
JENKINS_URL=http://localhost:8080
MCP_SERVER_URL=http://localhost:8010
SECRET_KEY=your-secure-random-key-here
```

### 2. Start Infrastructure Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait for services to be healthy
docker-compose ps
```

### 3. Start AI Agent Service

```bash
# Option A: Using Docker
docker-compose up -d ai-agent

# Option B: Direct Python (for development)
cd ai-agent
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Build Jenkins Plugin

```bash
cd jenkins-plugin
mvn clean package

# The .hpi file will be in target/jenkins-chatbot.hpi
```

### 5. Install Jenkins Plugin

1. Open Jenkins → Manage Jenkins → Manage Plugins
2. Go to Advanced tab
3. Upload `jenkins-plugin/target/jenkins-chatbot.hpi`
4. Restart Jenkins
5. Configure plugin:
   - Go to Manage Jenkins → Configure System
   - Find "AI Chatbot" section
   - Set AI Agent URL: `http://localhost:8000`

### 6. Test the Setup

1. Navigate to Jenkins → AI Assistant (should appear in sidebar)
2. Try basic interactions:
   - "What jobs do I have access to?"
   - "What can you help me with?"
   - "Show me the status of recent builds"

## Production Deployment

### 1. Security Hardening

**Environment Variables** (create `.env` file):
```env
# Strong secrets (generate with: openssl rand -base64 32)
SECRET_KEY=your-strong-secret-key-32-chars-minimum
REDIS_PASSWORD=your-redis-password
POSTGRES_PASSWORD=your-postgres-password

# Google Gemini API
GEMINI_API_KEY=your-production-api-key

# Jenkins Configuration
JENKINS_URL=https://your-jenkins.company.com
JENKINS_WEBHOOK_SECRET=your-webhook-secret

# MCP Server (if available)
MCP_SERVER_URL=https://your-mcp-server.company.com
MCP_SERVER_AUTH=your-mcp-auth-token

# Production Settings
DEBUG=false
LOG_LEVEL=INFO
ENABLE_METRICS=true
AUDIT_LOG_RETENTION_DAYS=90
```

### 2. Deploy with Docker Compose

```bash
# Production deployment
docker-compose --profile production up -d

# With monitoring (optional)
docker-compose --profile production --profile monitoring up -d
```

### 3. Configure Reverse Proxy (Optional)

**Nginx Example**:
```nginx
upstream ai-agent {
    server localhost:8000;
}

server {
    listen 443 ssl;
    server_name ai-agent.your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://ai-agent;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## MVP Validation Checklist

### ✅ Core Functionality

Test each of the 5 MVP user stories:

**Story 1: Trigger Build**
```
User: "trigger the frontend build"
Expected: Build starts if user has Job.BUILD permission
```

**Story 2: Build Status Query**  
```
User: "what's the status of my latest build?"
Expected: Shows current status with duration/completion info
```

**Story 3: Permission-Aware Job Listing**
```
User: "list all jobs"
Expected: Shows only jobs user can access
```

**Story 4: Build Log Access**
```
User: "show me the log for build #123" 
Expected: Displays recent log entries with errors highlighted
```

**Story 5: Basic Help and Discovery**
```
User: "what can you do?"
Expected: Context-aware help based on user permissions
```

### ✅ Security Requirements

- [ ] User authentication integrated with Jenkins
- [ ] All commands filtered by user permissions  
- [ ] Audit logging captures interactions
- [ ] No privilege escalation vulnerabilities
- [ ] Session management secure with timeout

### ✅ Performance Requirements

- [ ] Response times under 3 seconds
- [ ] System handles expected load without degradation
- [ ] Database and Redis perform well
- [ ] Error rate below 5%

### ✅ User Experience Requirements

- [ ] Chat interface intuitive and responsive
- [ ] Error messages helpful and actionable
- [ ] Help system guides users effectively
- [ ] Fallback to Jenkins UI works seamlessly

## Troubleshooting

### Common Issues

**1. AI Agent Won't Start**
```bash
# Check logs
docker-compose logs ai-agent

# Common fixes:
# - Verify GEMINI_API_KEY is set
# - Check database connection
# - Ensure Redis is healthy
```

**2. Jenkins Plugin Not Loading**
```bash
# Check Jenkins logs
tail -f $JENKINS_HOME/logs/jenkins.log

# Common fixes:
# - Verify Java version compatibility
# - Check plugin dependencies
# - Restart Jenkins service
```

**3. WebSocket Connection Fails**
```bash
# Check browser console for errors
# Verify Jenkins proxy settings
# Test direct AI Agent connection: curl http://localhost:8000/health
```

**4. Permission Errors**
```bash
# Check user permissions in Jenkins
# Verify session token generation
# Review audit logs for permission denied events
```

### Health Checks

```bash
# Check all services
docker-compose ps

# Test AI Agent health
curl http://localhost:8000/health

# Test database connectivity
docker-compose exec postgres pg_isready -U chatbot_user

# Test Redis connectivity  
docker-compose exec redis redis-cli ping
```

### Monitoring

Access monitoring tools:
- **AI Agent Metrics**: http://localhost:8000/docs (development only)
- **Database Admin**: pgAdmin at http://localhost:5050 (if enabled)
- **Prometheus**: http://localhost:9090 (if monitoring profile enabled)
- **Grafana**: http://localhost:3000 (if monitoring profile enabled)

## MVP Success Metrics

Track these metrics to validate MVP success:

- **User Adoption**: 70% of active Jenkins users try chatbot within 2 weeks
- **Task Completion**: 85% success rate for MVP user stories  
- **User Satisfaction**: Average rating ≥ 4.0/5.0 from feedback
- **Performance**: 95% of interactions complete within 3 seconds
- **Error Rate**: < 5% of interactions result in errors

## Next Steps

After MVP validation:

1. **Gather User Feedback**: Conduct user interviews and collect usage analytics
2. **Performance Optimization**: Optimize based on real usage patterns
3. **Security Audit**: Perform comprehensive security review
4. **Scale Planning**: Plan infrastructure for wider deployment
5. **Advanced Features**: Implement Phase 4 advanced AI features

## Support

For issues and questions:
1. Check troubleshooting section above
2. Review logs: `docker-compose logs ai-agent`
3. Validate configuration: `docker-compose config`
4. Test individual components: health check endpoints

## Security Notes

**Important**: This MVP includes comprehensive security measures, but always:
- Use strong, unique secrets in production
- Enable audit logging and monitoring
- Regular security updates for all components
- Network isolation and access controls
- Regular backup of audit logs and session data