# Jenkins Chatbot Manual Testing Guide

Complete manual testing guide for validating the Jenkins Chatbot MVP using API tokens.

## Prerequisites

- Jenkins running on http://localhost:8080 (or update URLs accordingly)
- Jenkins admin access
- `curl` and `jq` installed
- Docker and docker-compose available

## Part 1: Jenkins API Token Setup

### Step 1: Generate Jenkins API Token

1. **Login to Jenkins Web UI**
   - Go to http://localhost:8080
   - Login as admin

2. **Generate API Token**
   - Click your username (top right) → Configure
   - Scroll to "API Token" section
   - Click "Add new Token"
   - Enter name: "Chatbot Testing"
   - Click "Generate"
   - **Copy the token immediately** (it won't be shown again)

3. **Set Environment Variables**
```bash
export JENKINS_URL="http://localhost:8080"
export JENKINS_USER="admin"
export JENKINS_API_TOKEN="11xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Replace with your token
```

### Step 2: Verify API Token Works

```bash
# Test basic Jenkins API access
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     "$JENKINS_URL/api/json" | jq '.jobs | length'
```

**Expected:** Should return number of jobs (even 0 is success)

## Part 2: Jenkins Plugin Testing

### Test 1: Plugin Health Check

```bash
# Health check (no auth needed)
curl -s "$JENKINS_URL/plugin/jenkins-chatbot/health" \
     -w "\nHTTP Code: %{http_code}\n"
```

**Expected Response:**
```json
{"status":"ok","version":"1.0.0"}
HTTP Code: 200
```

### Test 2: Session Creation

```bash
# Create chat session
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST \
     "$JENKINS_URL/plugin/jenkins-chatbot/api/session" \
     -w "\nHTTP Code: %{http_code}\n"
```

**Expected Response:**
```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "admin",
  "permissions": [],
  "createdAt": 1642723200000,
  "expiresAt": 1642724100000
}
HTTP Code: 201
```

### Test 3: Session State Retrieval

```bash
# First create session and capture sessionId
SESSION_RESPONSE=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST \
     "$JENKINS_URL/plugin/jenkins-chatbot/api/session")

SESSION_ID=$(echo $SESSION_RESPONSE | jq -r .sessionId)
echo "Session ID: $SESSION_ID"

# Get session state
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     "$JENKINS_URL/plugin/jenkins-chatbot/api/session/$SESSION_ID" \
     -w "\nHTTP Code: %{http_code}\n"
```

### Test 4: Chat Interface Access

```bash
# Test chat interface page
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     "$JENKINS_URL/ai-assistant/" \
     -w "\nHTTP Code: %{http_code}\n" \
     -o /tmp/chat_interface.html

# Check if page loaded
if [ -f /tmp/chat_interface.html ] && [ -s /tmp/chat_interface.html ]; then
    echo "✅ Chat interface accessible"
    head -n 5 /tmp/chat_interface.html
else
    echo "❌ Chat interface not accessible"
fi
```

## Part 3: AI Agent Service Testing

### Prerequisites: Start AI Agent Service

```bash
# Navigate to project directory
cd /home/admin/mcp-server/jenkins-chatbot-project

# Set required environment variables
export GEMINI_API_KEY="your-gemini-api-key"  # Replace with actual key
export JENKINS_URL="http://localhost:8080"
export SECRET_KEY="test-secret-key-for-manual-testing"

# Start services
docker-compose up -d redis postgres
sleep 10  # Wait for services to be ready

# Start AI agent (in background or separate terminal)
cd ai-agent
python -m app.main &
AI_AGENT_PID=$!
sleep 5  # Wait for service to start
```

### Test 1: AI Agent Health Check

```bash
# Health check
curl -s "http://localhost:8000/health" \
     -w "\nHTTP Code: %{http_code}\n"
```

**Expected Response:**
```json
{
  "status": "ok",
  "database_healthy": true,
  "redis_healthy": true,
  "ai_service_healthy": true,
  "timestamp": 1642723200000
}
HTTP Code: 200
```

### Test 2: AI Agent Session Creation

```bash
# Create session in AI Agent
curl -s -H "Content-Type: application/json" \
     -X POST \
     "http://localhost:8000/api/v1/session/create" \
     -d '{
       "user_id": "admin",
       "user_token": "jenkins_token_admin_session123_'$(date +%s)'000",
       "permissions": ["Job.READ", "Job.BUILD"],
       "session_timeout": 900
     }' \
     -w "\nHTTP Code: %{http_code}\n"
```

### Test 3: Chat Message Processing

```bash
# First create session and get sessionId
AI_SESSION_RESPONSE=$(curl -s -H "Content-Type: application/json" \
     -X POST \
     "http://localhost:8000/api/v1/session/create" \
     -d '{
       "user_id": "admin",
       "user_token": "jenkins_token_admin_session123_'$(date +%s)'000",
       "permissions": ["Job.READ", "Job.BUILD"],
       "session_timeout": 900
     }')

AI_SESSION_ID=$(echo $AI_SESSION_RESPONSE | jq -r .session_id)
USER_TOKEN=$(echo $AI_SESSION_RESPONSE | jq -r .user_token)

echo "AI Session ID: $AI_SESSION_ID"

# Send chat message
curl -s -H "Content-Type: application/json" \
     -H "Authorization: Bearer $USER_TOKEN" \
     -X POST \
     "http://localhost:8000/api/v1/chat" \
     -d '{
       "session_id": "'$AI_SESSION_ID'",
       "user_id": "admin",
       "message": "Hello, what can you help me with?",
       "permissions": ["Job.READ", "Job.BUILD"],
       "context": {}
     }' \
     -w "\nHTTP Code: %{http_code}\n"
```

## Part 4: End-to-End Integration Testing

### Test Complete Jenkins → AI Agent Flow

```bash
#!/bin/bash
# Complete E2E test script

echo "=== End-to-End Jenkins Chatbot Test ==="

# Step 1: Create Jenkins session
echo "1. Creating Jenkins session..."
JENKINS_SESSION=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST \
     "$JENKINS_URL/plugin/jenkins-chatbot/api/session")

JENKINS_SESSION_ID=$(echo $JENKINS_SESSION | jq -r .sessionId)
echo "Jenkins Session ID: $JENKINS_SESSION_ID"

# Step 2: Simulate Jenkins plugin calling AI Agent
echo "2. Testing Jenkins → AI Agent communication..."

# This simulates what the Jenkins plugin would do
AI_REQUEST='{
  "session_id": "'$JENKINS_SESSION_ID'",
  "user_id": "admin", 
  "message": "Show me the status of all jobs",
  "user_token": "jenkins_token_admin_'$JENKINS_SESSION_ID'_'$(date +%s)'000",
  "permissions": ["Job.READ", "Job.BUILD"],
  "context": {
    "jenkins_url": "'$JENKINS_URL'",
    "current_user": "admin"
  }
}'

# First create AI session
curl -s -H "Content-Type: application/json" \
     -X POST \
     "http://localhost:8000/api/v1/session/create" \
     -d '{
       "user_id": "admin",
       "user_token": "jenkins_token_admin_'$JENKINS_SESSION_ID'_'$(date +%s)'000", 
       "permissions": ["Job.READ", "Job.BUILD"],
       "session_timeout": 900
     }' > /tmp/ai_session.json

AI_SESSION_ID=$(cat /tmp/ai_session.json | jq -r .session_id)
USER_TOKEN=$(cat /tmp/ai_session.json | jq -r .user_token)

echo "AI Session ID: $AI_SESSION_ID"

# Send message to AI Agent
echo "3. Sending chat message to AI Agent..."
AI_RESPONSE=$(curl -s -H "Content-Type: application/json" \
     -H "Authorization: Bearer $USER_TOKEN" \
     -X POST \
     "http://localhost:8000/api/v1/chat" \
     -d '{
       "session_id": "'$AI_SESSION_ID'",
       "user_id": "admin",
       "message": "Show me the status of all jobs", 
       "permissions": ["Job.READ", "Job.BUILD"],
       "context": {"jenkins_url": "'$JENKINS_URL'"}
     }')

echo "AI Response:"
echo $AI_RESPONSE | jq .

echo "✅ End-to-end test complete!"
```

## Part 5: Docker Environment Validation

### Start Full Environment

```bash
# Create environment file
cat > .env << EOF
GEMINI_API_KEY=your-gemini-api-key-here
JENKINS_URL=http://host.docker.internal:8080
SECRET_KEY=your-secret-key-change-this
REDIS_PASSWORD=chatbot_redis_pass
POSTGRES_PASSWORD=chatbot_db_pass
POSTGRES_USER=chatbot_user
POSTGRES_DB=jenkins_chatbot
EOF

# Start all services
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Check service health
echo "Checking service health..."

# Redis
docker-compose exec redis redis-cli -a chatbot_redis_pass ping

# PostgreSQL  
docker-compose exec postgres pg_isready -U chatbot_user -d jenkins_chatbot

# AI Agent
curl -s http://localhost:8000/health | jq .status

echo "✅ All services are running"
```

### Validate Service Integration

```bash
# Test AI Agent can connect to dependencies
curl -s http://localhost:8000/health | jq '{
  status: .status,
  database: .database_healthy,
  redis: .redis_healthy,
  ai_service: .ai_service_healthy
}'
```

## Part 6: Troubleshooting Common Issues

### Issue: Plugin Not Found (404 errors)

**Symptoms:** `curl` requests to `/plugin/jenkins-chatbot/*` return 404

**Check:**
```bash
# Verify plugin is installed
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     "$JENKINS_URL/pluginManager/api/json?depth=1" | \
     jq '.plugins[] | select(.shortName=="jenkins-chatbot") | {name: .shortName, version: .version, active: .active}'
```

**Solutions:**
1. Ensure plugin is built and installed: `cd jenkins-plugin && mvn clean package`
2. Copy `.hpi` file to Jenkins plugins directory
3. Restart Jenkins
4. Check Jenkins logs for plugin loading errors

### Issue: AI Agent Connection Failed

**Symptoms:** Jenkins plugin cannot reach AI Agent service

**Check:**
```bash
# Test AI Agent accessibility from Jenkins host
curl -s http://localhost:8000/health

# Check if running in Docker
docker-compose ps ai-agent

# Check logs
docker-compose logs ai-agent
```

**Solutions:**
1. Ensure AI Agent is running on correct port (8000)
2. Check firewall/network configuration
3. Update `JENKINS_URL` in AI Agent config
4. Verify environment variables are set correctly

### Issue: Authentication Failures

**Symptoms:** 401 Unauthorized errors

**Check:**
```bash
# Verify API token is correct
curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
     "$JENKINS_URL/me/api/json" | jq .id

# Check token format for AI Agent
echo "Token format should be: jenkins_token_userId_sessionId_expiry"
```

**Solutions:**
1. Regenerate Jenkins API token
2. Check token expiry timestamps
3. Verify user permissions in Jenkins
4. Update authentication headers

### Issue: Database Connection Errors

**Symptoms:** AI Agent fails to start, database connection errors

**Check:**
```bash
# Test PostgreSQL connection
docker-compose exec postgres psql -U chatbot_user -d jenkins_chatbot -c "SELECT 1;"

# Test Redis connection
docker-compose exec redis redis-cli -a chatbot_redis_pass ping

# Check AI Agent logs
docker-compose logs ai-agent | grep -i database
```

## Expected Results Summary

✅ **Jenkins Plugin:**
- Health check returns HTTP 200
- Session creation returns HTTP 201 with sessionId
- Chat interface accessible via web browser

✅ **AI Agent Service:**  
- Health check shows all services healthy
- Session creation successful
- Chat messages processed and return responses

✅ **Integration:**
- Jenkins can create sessions and communicate with AI Agent
- User authentication and permissions work correctly
- End-to-end message flow completes successfully

✅ **Docker Environment:**
- All services start and report healthy
- Database connections established
- Service-to-service communication working

## Next Steps After Validation

1. **Configure Production Settings**
   - Set proper secrets and passwords
   - Configure HTTPS and security headers
   - Set up monitoring and logging

2. **Performance Testing**
   - Load test with multiple concurrent users
   - Measure response times under load
   - Monitor resource usage

3. **Security Review**
   - Audit permissions and access controls
   - Test for common vulnerabilities
   - Review audit logging

4. **User Acceptance Testing**
   - Test with real Jenkins users
   - Validate common workflows work
   - Gather feedback for improvements