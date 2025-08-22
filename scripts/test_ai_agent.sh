#!/bin/bash

# AI Agent Service Testing Script
# Tests the FastAPI AI Agent service endpoints

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AI_AGENT_URL="${AI_AGENT_URL:-http://localhost:8000}"
TEST_USER_ID="${TEST_USER_ID:-admin}"
TEST_SESSION_TIMEOUT="${TEST_SESSION_TIMEOUT:-900}"

echo -e "${BLUE}=== AI Agent Service Testing ===${NC}"
echo "AI Agent URL: $AI_AGENT_URL"
echo "Test User: $TEST_USER_ID"
echo ""

# Test 1: Service Health Check
echo -e "${YELLOW}Test 1: AI Agent health check...${NC}"
HEALTH_RESPONSE=$(curl -s "$AI_AGENT_URL/health" \
    -w "HTTP_CODE:%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$HEALTH_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
HEALTH_DATA=$(echo "$HEALTH_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ AI Agent health check successful${NC}"
    
    # Parse health data
    STATUS=$(echo "$HEALTH_DATA" | jq -r '.status' 2>/dev/null)
    DB_HEALTHY=$(echo "$HEALTH_DATA" | jq -r '.database_healthy' 2>/dev/null)
    REDIS_HEALTHY=$(echo "$HEALTH_DATA" | jq -r '.redis_healthy' 2>/dev/null)
    AI_HEALTHY=$(echo "$HEALTH_DATA" | jq -r '.ai_service_healthy' 2>/dev/null)
    
    echo "Status: $STATUS"
    echo "Database: $DB_HEALTHY"
    echo "Redis: $REDIS_HEALTHY" 
    echo "AI Service: $AI_HEALTHY"
    
    # Check if any components are unhealthy
    if [ "$DB_HEALTHY" != "true" ] || [ "$REDIS_HEALTHY" != "true" ] || [ "$AI_HEALTHY" != "true" ]; then
        echo -e "${YELLOW}⚠️  Some components are unhealthy - this may affect functionality${NC}"
    fi
else
    echo -e "${RED}❌ AI Agent health check failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $HEALTH_DATA"
    echo "Make sure the AI Agent service is running on $AI_AGENT_URL"
    echo "Start with: cd ai-agent && python -m app.main"
    exit 1
fi
echo ""

# Test 2: Session Creation
echo -e "${YELLOW}Test 2: Create AI Agent session...${NC}"

# Generate a predictable session ID and token for session creation
CURRENT_TIME=$(date +%s)
EXPIRY_TIME=$((CURRENT_TIME * 1000 + 900000))  # 15 minutes from now
PREDICTED_SESSION_ID="test-$(uuidgen 2>/dev/null || echo "session-$CURRENT_TIME")"
PREDICTED_TOKEN="jenkins_token_${TEST_USER_ID}_${PREDICTED_SESSION_ID}_${EXPIRY_TIME}"

SESSION_REQUEST='{
  "user_id": "'$TEST_USER_ID'",
  "user_token": "'$PREDICTED_TOKEN'",
  "permissions": ["Job.READ", "Job.BUILD", "Job.CREATE"],
  "session_timeout": '$TEST_SESSION_TIMEOUT'
}'

SESSION_RESPONSE=$(curl -s -H "Content-Type: application/json" \
    -X POST \
    "$AI_AGENT_URL/api/v1/session/create" \
    -d "$SESSION_REQUEST" \
    -w "HTTP_CODE:%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$SESSION_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
SESSION_DATA=$(echo "$SESSION_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ AI Agent session creation successful${NC}"
    
    # Parse session data
    AI_SESSION_ID=$(echo "$SESSION_DATA" | jq -r '.session_id' 2>/dev/null)
    USER_TOKEN=$(echo "$SESSION_DATA" | jq -r '.user_token' 2>/dev/null)
    PERMISSIONS=$(echo "$SESSION_DATA" | jq -r '.permissions[]' 2>/dev/null | tr '\n' ',' | sed 's/,$//')
    
    echo "Session ID: $AI_SESSION_ID"
    echo "User Token: ${USER_TOKEN:0:20}..."
    echo "Permissions: $PERMISSIONS"
    
    # Always generate proper token using actual session ID for subsequent requests
    # The returned user_token might be the one from the request, but we need one with real session ID
    PROPER_TOKEN="jenkins_token_${TEST_USER_ID}_${AI_SESSION_ID}_${EXPIRY_TIME}"
    echo "Using proper token with actual session ID: ${PROPER_TOKEN:0:40}..."
    
    # Verify the original token is included
    if [ "$USER_TOKEN" = "null" ] || [ -z "$USER_TOKEN" ]; then
        echo -e "${YELLOW}⚠️  Warning: Original user token is null or empty${NC}"
    else
        echo "Original token from response: ${USER_TOKEN:0:40}..."
    fi
    
    # Use the proper token for subsequent tests
    USER_TOKEN="$PROPER_TOKEN"
    
    # Save session data for next tests
    echo "$AI_SESSION_ID" > /tmp/ai_session_id.txt
    echo "$USER_TOKEN" > /tmp/ai_user_token.txt
else
    echo -e "${RED}❌ AI Agent session creation failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $SESSION_DATA"
    echo "Check AI Agent logs and database connectivity"
    exit 1
fi
echo ""

# Test 3: Session State Retrieval (if session was created)
if [ -f /tmp/ai_session_id.txt ] && [ -f /tmp/ai_user_token.txt ]; then
    AI_SESSION_ID=$(cat /tmp/ai_session_id.txt)
    USER_TOKEN=$(cat /tmp/ai_user_token.txt)
    
    echo -e "${YELLOW}Test 3: Retrieve AI Agent session state...${NC}"
    
    STATE_RESPONSE=$(curl -s -H "Authorization: Bearer $USER_TOKEN" \
        "$AI_AGENT_URL/api/v1/session/$AI_SESSION_ID/state" \
        -w "HTTP_CODE:%{http_code}" 2>/dev/null)
    
    HTTP_CODE=$(echo "$STATE_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    STATE_DATA=$(echo "$STATE_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Session state retrieval successful${NC}"
        echo "Session data: $STATE_DATA"
    else
        echo -e "${RED}❌ Session state retrieval failed (HTTP $HTTP_CODE)${NC}"
        echo "Response: $STATE_DATA"
    fi
    echo ""
fi

# Test 4: Chat Message Processing
if [ -f /tmp/ai_session_id.txt ] && [ -f /tmp/ai_user_token.txt ]; then
    AI_SESSION_ID=$(cat /tmp/ai_session_id.txt)
    USER_TOKEN=$(cat /tmp/ai_user_token.txt)
    
    echo -e "${YELLOW}Test 4: Send chat message...${NC}"
    
    CHAT_REQUEST='{
      "session_id": "'$AI_SESSION_ID'",
      "user_id": "'$TEST_USER_ID'",
      "user_token": "'$USER_TOKEN'",
      "message": "Hello! What can you help me with in Jenkins?",
      "permissions": ["Job.READ", "Job.BUILD", "Job.CREATE"],
      "context": {
        "jenkins_url": "http://localhost:8080",
        "current_user": "'$TEST_USER_ID'"
      }
    }'
    
    CHAT_RESPONSE=$(curl -s -H "Content-Type: application/json" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -X POST \
        "$AI_AGENT_URL/api/v1/chat" \
        -d "$CHAT_REQUEST" \
        -w "HTTP_CODE:%{http_code}" 2>/dev/null)
    
    HTTP_CODE=$(echo "$CHAT_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    CHAT_DATA=$(echo "$CHAT_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Chat message processing successful${NC}"
        
        # Parse chat response
        AI_RESPONSE=$(echo "$CHAT_DATA" | jq -r '.response' 2>/dev/null)
        ACTIONS=$(echo "$CHAT_DATA" | jq -r '.actions' 2>/dev/null)
        
        echo "AI Response: $AI_RESPONSE"
        if [ "$ACTIONS" != "null" ] && [ "$ACTIONS" != "[]" ]; then
            echo "Planned Actions: $ACTIONS"
        fi
    else
        echo -e "${RED}❌ Chat message processing failed (HTTP $HTTP_CODE)${NC}"
        echo "Response: $CHAT_DATA"
        
        # Check for common errors
        if [[ "$CHAT_DATA" == *"GEMINI_API_KEY"* ]]; then
            echo -e "${YELLOW}💡 This looks like a Gemini API key error${NC}"
            echo "Set your Gemini API key: export GEMINI_API_KEY=\"your-key-here\""
        elif [[ "$CHAT_DATA" == *"token"* ]]; then
            echo -e "${YELLOW}💡 This looks like a token validation error${NC}"
            echo "Check token format and expiry time"
        fi
    fi
    echo ""
fi

# Test 5: Permission Validation
if [ -f /tmp/ai_user_token.txt ]; then
    USER_TOKEN=$(cat /tmp/ai_user_token.txt)
    
    echo -e "${YELLOW}Test 5: Permission validation...${NC}"
    
    PERMISSION_REQUEST='{
      "action": "Job.BUILD",
      "resource": "test-job"
    }'
    
    PERMISSION_RESPONSE=$(curl -s -H "Content-Type: application/json" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -X POST \
        "$AI_AGENT_URL/api/v1/permissions/validate" \
        -d "$PERMISSION_REQUEST" \
        -w "HTTP_CODE:%{http_code}" 2>/dev/null)
    
    HTTP_CODE=$(echo "$PERMISSION_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    PERMISSION_DATA=$(echo "$PERMISSION_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Permission validation successful${NC}"
        echo "Validation result: $PERMISSION_DATA"
    else
        echo -e "${RED}❌ Permission validation failed (HTTP $HTTP_CODE)${NC}"
        echo "Response: $PERMISSION_DATA"
    fi
    echo ""
fi

# Test 6: Error Handling (invalid requests)
echo -e "${YELLOW}Test 6: Error handling (invalid token)...${NC}"

INVALID_CHAT_REQUEST='{
  "session_id": "invalid-session",
  "user_id": "'$TEST_USER_ID'",
  "message": "This should fail",
  "permissions": ["Job.READ"],
  "context": {}
}'

ERROR_RESPONSE=$(curl -s -H "Content-Type: application/json" \
    -H "Authorization: Bearer invalid-token-here" \
    -X POST \
    "$AI_AGENT_URL/api/v1/chat" \
    -d "$INVALID_CHAT_REQUEST" \
    -w "HTTP_CODE:%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$ERROR_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✅ Error handling working correctly (returned 401 for invalid token)${NC}"
else
    echo -e "${YELLOW}⚠️  Expected 401 for invalid token, got HTTP $HTTP_CODE${NC}"
    echo "Response: $(echo "$ERROR_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')"
fi
echo ""

# Cleanup temporary files
rm -f /tmp/ai_session_id.txt /tmp/ai_user_token.txt

echo -e "${BLUE}=== AI Agent Service Test Summary ===${NC}"
echo -e "${GREEN}✅ Passed tests indicate the AI Agent service is working correctly${NC}"
echo -e "${RED}❌ Failed tests need to be addressed before proceeding${NC}"
echo ""
echo "Common issues and solutions:"
echo "1. Health check fails → Check if service is running and dependencies are available"
echo "2. Session creation fails → Check database connectivity and environment variables"
echo "3. Chat processing fails → Check Gemini API key and MCP server connectivity"
echo "4. Permission validation fails → Check token format and user permissions"
echo ""
echo "Next steps:"
echo "1. If all tests pass, proceed to end-to-end integration testing"
echo "2. If tests fail, check logs and troubleshooting guide"
echo "3. Ensure all required environment variables are set correctly"