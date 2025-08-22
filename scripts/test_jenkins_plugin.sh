#!/bin/bash

# Jenkins Plugin API Testing Script
# Tests Jenkins chatbot plugin endpoints using API token authentication

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Update these values
JENKINS_URL="${JENKINS_URL:-http://localhost:8080}"
JENKINS_USER="${JENKINS_USER:-admin}"
JENKINS_API_TOKEN="${JENKINS_API_TOKEN}"

# Validation
if [ -z "$JENKINS_API_TOKEN" ]; then
    echo -e "${RED}❌ JENKINS_API_TOKEN environment variable is required${NC}"
    echo "Generate token: Jenkins → User → Configure → API Token → Add new Token"
    echo "Then run: export JENKINS_API_TOKEN=\"your-token-here\""
    exit 1
fi

echo -e "${BLUE}=== Jenkins Chatbot Plugin Testing ===${NC}"
echo "Jenkins URL: $JENKINS_URL"
echo "User: $JENKINS_USER"
echo "Token: ${JENKINS_API_TOKEN:0:10}..." 
echo ""

# Test 1: Verify Jenkins API Access
echo -e "${YELLOW}Test 1: Verify Jenkins API access...${NC}"
JENKINS_INFO=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
    "$JENKINS_URL/api/json" \
    -w "HTTP_CODE:%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$JENKINS_INFO" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    JENKINS_VERSION=$(echo "$JENKINS_INFO" | jq -r '.version' 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✅ Jenkins API access successful (version: $JENKINS_VERSION)${NC}"
else
    echo -e "${RED}❌ Jenkins API access failed (HTTP $HTTP_CODE)${NC}"
    echo "Check your Jenkins URL, username, and API token"
    exit 1
fi
echo ""

# Test 2: Plugin Health Check
echo -e "${YELLOW}Test 2: Plugin health check...${NC}"
HEALTH_RESPONSE=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
    "$JENKINS_URL/ai-assistant/health" \
    -w "HTTP_CODE:%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$HEALTH_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
HEALTH_DATA=$(echo "$HEALTH_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Plugin health check successful${NC}"
    echo "Response: $HEALTH_DATA"
else
    echo -e "${RED}❌ Plugin health check failed (HTTP $HTTP_CODE)${NC}"
    echo "This could mean:"
    echo "  - Plugin is not installed"
    echo "  - Plugin is not active"
    echo "  - Wrong plugin URL path"
    
    # Check if plugin is installed
    echo "Checking if plugin is installed..."
    PLUGIN_CHECK=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
        "$JENKINS_URL/pluginManager/api/json?depth=1" | \
        jq -r '.plugins[] | select(.shortName=="jenkins-chatbot") | "\(.shortName) v\(.version) - Active: \(.active)"' 2>/dev/null)
    
    if [ -n "$PLUGIN_CHECK" ]; then
        echo "Plugin status: $PLUGIN_CHECK"
    else
        echo -e "${RED}❌ jenkins-chatbot plugin not found in installed plugins${NC}"
        echo "Build and install the plugin:"
        echo "  cd jenkins-plugin && mvn clean package"
        echo "  Copy target/*.hpi to Jenkins plugins directory"
        echo "  Restart Jenkins"
    fi
    exit 1
fi
echo ""

# Test 3: Session Creation
echo -e "${YELLOW}Test 3: Create chat session...${NC}"
SESSION_RESPONSE=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
    -H "Content-Type: application/json" \
    -X POST \
    "$JENKINS_URL/ai-assistant/apiSession" \
    -w "HTTP_CODE:%{http_code}" 2>/dev/null)

HTTP_CODE=$(echo "$SESSION_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
SESSION_DATA=$(echo "$SESSION_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')

if [ "$HTTP_CODE" = "201" ]; then
    echo -e "${GREEN}✅ Session creation successful${NC}"
    
    # Parse session data
    SESSION_ID=$(echo "$SESSION_DATA" | jq -r '.sessionId' 2>/dev/null)
    USER_ID=$(echo "$SESSION_DATA" | jq -r '.userId' 2>/dev/null)
    
    if [ "$SESSION_ID" != "null" ] && [ -n "$SESSION_ID" ]; then
        echo "Session ID: $SESSION_ID"
        echo "User ID: $USER_ID"
        
        # Save session ID for next test
        echo "$SESSION_ID" > /tmp/jenkins_session_id.txt
    else
        echo -e "${YELLOW}⚠️  Session created but response format unexpected${NC}"
        echo "Response: $SESSION_DATA"
    fi
else
    echo -e "${RED}❌ Session creation failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $SESSION_DATA"
    echo "Check user permissions and plugin configuration"
    exit 1
fi
echo ""

# Test 4: Session State Retrieval (if session was created)
if [ -f /tmp/jenkins_session_id.txt ]; then
    SESSION_ID=$(cat /tmp/jenkins_session_id.txt)
    echo -e "${YELLOW}Test 4: Retrieve session state...${NC}"
    
    # Try the API route first
    STATE_RESPONSE=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
        "$JENKINS_URL/ai-assistant/api/session/$SESSION_ID" \
        -w "HTTP_CODE:%{http_code}" 2>/dev/null)
    
    HTTP_CODE=$(echo "$STATE_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    STATE_DATA=$(echo "$STATE_RESPONSE" | sed 's/HTTP_CODE:[0-9]*//g')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Session state retrieval successful${NC}"
        echo "Session data: $STATE_DATA"
    elif [ "$HTTP_CODE" = "404" ]; then
        echo -e "${YELLOW}⚠️  Session state endpoint not implemented yet (HTTP $HTTP_CODE)${NC}"
        echo "This is expected - session state retrieval is not critical for MVP"
    else
        echo -e "${RED}❌ Session state retrieval failed (HTTP $HTTP_CODE)${NC}"
        echo "Response: $STATE_DATA"
    fi
    echo ""
    
    # Cleanup
    rm -f /tmp/jenkins_session_id.txt
fi

# Test 5: Chat Interface Access
echo -e "${YELLOW}Test 5: Chat interface accessibility...${NC}"
INTERFACE_RESPONSE=$(curl -s -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
    "$JENKINS_URL/ai-assistant/" \
    -w "HTTP_CODE:%{http_code}" \
    -o /tmp/chat_interface.html 2>/dev/null)

HTTP_CODE=$(echo "$INTERFACE_RESPONSE" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)

if [ "$HTTP_CODE" = "200" ] && [ -f /tmp/chat_interface.html ] && [ -s /tmp/chat_interface.html ]; then
    echo -e "${GREEN}✅ Chat interface accessible${NC}"
    
    # Check if it looks like HTML
    if grep -q "<html\|<HTML" /tmp/chat_interface.html; then
        echo "Interface appears to be valid HTML"
        FILE_SIZE=$(wc -c < /tmp/chat_interface.html)
        echo "Page size: $FILE_SIZE bytes"
    else
        echo -e "${YELLOW}⚠️  Interface returned but may not be valid HTML${NC}"
        echo "First few lines:"
        head -n 3 /tmp/chat_interface.html
    fi
else
    echo -e "${RED}❌ Chat interface not accessible (HTTP $HTTP_CODE)${NC}"
    echo "Check if RootAction is properly configured"
fi

# Cleanup
rm -f /tmp/chat_interface.html

echo ""
echo -e "${BLUE}=== Jenkins Plugin Test Summary ===${NC}"
echo -e "${GREEN}✅ Passed tests indicate the Jenkins plugin is working correctly${NC}"
echo -e "${RED}❌ Failed tests need to be addressed before proceeding${NC}"
echo ""
echo "Next steps:"
echo "1. If all tests pass, proceed to test the AI Agent service"
echo "2. If tests fail, check the troubleshooting section in manual_testing_guide.md"
echo "3. Run the full end-to-end test after both components are working"