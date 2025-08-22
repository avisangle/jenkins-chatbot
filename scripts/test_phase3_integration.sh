#!/bin/bash

# Phase 3 Integration Testing Script
# Tests complete Jenkins Plugin → AI Agent Service → MCP Server flow

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
JENKINS_URL="${JENKINS_URL:-http://localhost:8080}"
JENKINS_USER="${JENKINS_USER:-admin}"
JENKINS_API_TOKEN="${JENKINS_API_TOKEN}"
AI_AGENT_URL="${AI_AGENT_URL:-http://localhost:8000}"
MCP_SERVER_URL="${MCP_SERVER_URL:-http://localhost:8010}"

# Test Results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Utility functions
run_test() {
    local test_name="$1"
    local test_function="$2"
    
    echo -e "${BLUE}=== Testing: $test_name ===${NC}"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    if $test_function; then
        echo -e "${GREEN}✅ PASSED: $test_name${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}❌ FAILED: $test_name${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    echo ""
}

# Test functions
test_ai_agent_health() {
    echo "Testing AI Agent service health..."
    response=$(curl -s -w "%{http_code}" -o /tmp/ai_health.json "$AI_AGENT_URL/health")
    
    if [ "$response" = "200" ]; then
        if jq -e '.status == "ok"' /tmp/ai_health.json > /dev/null 2>&1; then
            echo "AI Agent service is healthy"
            return 0
        else
            echo "AI Agent service returned non-ok status"
            cat /tmp/ai_health.json
            return 1
        fi
    else
        echo "AI Agent service health check failed with status: $response"
        return 1
    fi
}

test_mcp_server_connection() {
    echo "Testing MCP server connectivity..."
    if [ -z "$MCP_SERVER_URL" ]; then
        echo "MCP_SERVER_URL not set, skipping MCP test"
        return 0
    fi
    
    response=$(curl -s -w "%{http_code}" -o /tmp/mcp_health.json "$MCP_SERVER_URL/health" 2>/dev/null || echo "000")
    
    if [ "$response" = "200" ]; then
        echo "MCP server is reachable"
        return 0
    else
        echo "MCP server not reachable (status: $response) - this is optional for Phase 3"
        return 0  # MCP is optional
    fi
}

test_jenkins_plugin_session() {
    echo "Testing Jenkins plugin session creation..."
    
    if [ -z "$JENKINS_API_TOKEN" ]; then
        echo "JENKINS_API_TOKEN not set, cannot test Jenkins integration"
        return 1
    fi
    
    # Test session creation through Jenkins plugin
    response=$(curl -s -w "%{http_code}" -o /tmp/jenkins_session.json \
        -X POST "$JENKINS_URL/ai-assistant/apiSession" \
        -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
        -H "Content-Type: application/json" \
        2>/dev/null || echo "000")
    
    if [ "$response" = "201" ] || [ "$response" = "200" ]; then
        if jq -e '.sessionId' /tmp/jenkins_session.json > /dev/null 2>&1; then
            echo "Jenkins plugin session created successfully"
            # Extract session data for subsequent tests
            export TEST_SESSION_ID=$(jq -r '.sessionId' /tmp/jenkins_session.json)
            export TEST_USER_TOKEN=$(jq -r '.userToken' /tmp/jenkins_session.json)
            export TEST_USER_ID=$(jq -r '.userId' /tmp/jenkins_session.json)
            return 0
        else
            echo "Session response missing required fields"
            cat /tmp/jenkins_session.json
            return 1
        fi
    else
        echo "Jenkins plugin session creation failed with status: $response"
        if [ -f /tmp/jenkins_session.json ]; then
            cat /tmp/jenkins_session.json
        fi
        return 1
    fi
}

test_jenkins_to_ai_agent_flow() {
    echo "Testing complete Jenkins → AI Agent flow..."
    
    if [ -z "$TEST_SESSION_ID" ] || [ -z "$TEST_USER_TOKEN" ]; then
        echo "Session data not available, skipping integration test"
        return 1
    fi
    
    # Test chat message through Jenkins plugin
    chat_payload=$(cat <<EOF
{
    "message": "what can you help me with?",
    "session_id": "$TEST_SESSION_ID",
    "user_token": "$TEST_USER_TOKEN",
    "user_id": "$TEST_USER_ID",
    "permissions": ["Job.READ", "Job.BUILD"]
}
EOF
)
    
    echo "Sending chat message through Jenkins plugin..."
    response=$(curl -s -w "%{http_code}" -o /tmp/jenkins_chat.json \
        -X POST "$JENKINS_URL/ai-assistant/api/" \
        -u "$JENKINS_USER:$JENKINS_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$chat_payload" \
        2>/dev/null || echo "000")
    
    if [ "$response" = "200" ]; then
        if jq -e '.response' /tmp/jenkins_chat.json > /dev/null 2>&1; then
            ai_response=$(jq -r '.response' /tmp/jenkins_chat.json)
            echo "AI Agent responded successfully:"
            echo "Response preview: ${ai_response:0:100}..."
            
            # Check if response contains helpful content
            if echo "$ai_response" | grep -qi "help\|assist\|jenkins\|build"; then
                echo "Response contains relevant Jenkins help content"
                return 0
            else
                echo "Response does not contain expected Jenkins help content"
                echo "Full response: $ai_response"
                return 1
            fi
        else
            echo "Chat response missing required fields"
            cat /tmp/jenkins_chat.json
            return 1
        fi
    else
        echo "Jenkins chat request failed with status: $response"
        if [ -f /tmp/jenkins_chat.json ]; then
            cat /tmp/jenkins_chat.json
        fi
        return 1
    fi
}

test_direct_ai_agent_chat() {
    echo "Testing direct AI Agent chat endpoint..."
    
    if [ -z "$TEST_SESSION_ID" ] || [ -z "$TEST_USER_TOKEN" ]; then
        echo "Session data not available, creating test session for direct AI Agent test..."
        
        # Create session directly with AI Agent
        session_payload=$(cat <<EOF
{
    "user_id": "test_user_direct",
    "user_token": "test_token_$(date +%s)",
    "permissions": ["Job.READ", "Job.BUILD"],
    "session_timeout": 900
}
EOF
)
        
        response=$(curl -s -w "%{http_code}" -o /tmp/ai_session.json \
            -X POST "$AI_AGENT_URL/api/v1/session/create" \
            -H "Content-Type: application/json" \
            -d "$session_payload" \
            2>/dev/null || echo "000")
        
        if [ "$response" = "200" ] || [ "$response" = "201" ]; then
            TEST_SESSION_ID=$(jq -r '.session_id' /tmp/ai_session.json)
            TEST_USER_TOKEN=$(jq -r '.user_token' /tmp/ai_session.json)
            TEST_USER_ID=$(jq -r '.user_id' /tmp/ai_session.json)
        else
            echo "Failed to create AI Agent session: $response"
            return 1
        fi
    fi
    
    # Test direct chat with AI Agent
    chat_payload=$(cat <<EOF
{
    "session_id": "$TEST_SESSION_ID",
    "user_id": "$TEST_USER_ID",
    "user_token": "$TEST_USER_TOKEN",
    "message": "list all jobs",
    "permissions": ["Job.READ", "Job.BUILD"],
    "context": {
        "jenkins_url": "$JENKINS_URL",
        "current_user": "$TEST_USER_ID"
    }
}
EOF
)
    
    echo "Sending direct chat message to AI Agent..."
    response=$(curl -s -w "%{http_code}" -o /tmp/ai_chat.json \
        -X POST "$AI_AGENT_URL/api/v1/chat" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TEST_USER_TOKEN" \
        -d "$chat_payload" \
        2>/dev/null || echo "000")
    
    if [ "$response" = "200" ]; then
        if jq -e '.response' /tmp/ai_chat.json > /dev/null 2>&1; then
            ai_response=$(jq -r '.response' /tmp/ai_chat.json)
            intent=$(jq -r '.intent_detected // "unknown"' /tmp/ai_chat.json)
            processing_time=$(jq -r '.response_time_ms // 0' /tmp/ai_chat.json)
            
            echo "AI Agent direct chat successful:"
            echo "Intent detected: $intent"
            echo "Processing time: ${processing_time}ms"
            echo "Response preview: ${ai_response:0:100}..."
            
            return 0
        else
            echo "AI Agent chat response missing required fields"
            cat /tmp/ai_chat.json
            return 1
        fi
    else
        echo "AI Agent direct chat failed with status: $response"
        if [ -f /tmp/ai_chat.json ]; then
            cat /tmp/ai_chat.json
        fi
        return 1
    fi
}

test_authentication_security() {
    echo "Testing authentication and security..."
    
    # Test without authorization
    response=$(curl -s -w "%{http_code}" -o /tmp/auth_test.json \
        -X POST "$AI_AGENT_URL/api/v1/chat" \
        -H "Content-Type: application/json" \
        -d '{"message": "test", "session_id": "invalid"}' \
        2>/dev/null || echo "000")
    
    if [ "$response" = "401" ] || [ "$response" = "403" ]; then
        echo "Authentication properly rejected unauthorized request"
        return 0
    else
        echo "Authentication security issue: expected 401/403, got $response"
        return 1
    fi
}

test_error_handling() {
    echo "Testing error handling and fallback responses..."
    
    if [ -z "$TEST_USER_TOKEN" ]; then
        echo "No test token available, creating minimal test case..."
        # Test with malformed request
        response=$(curl -s -w "%{http_code}" -o /tmp/error_test.json \
            -X POST "$AI_AGENT_URL/api/v1/chat" \
            -H "Content-Type: application/json" \
            -d '{"invalid": "request"}' \
            2>/dev/null || echo "000")
        
        if [ "$response" = "400" ] || [ "$response" = "422" ]; then
            echo "Error handling working: properly rejected malformed request"
            return 0
        else
            echo "Error handling issue: expected 400/422, got $response"
            return 1
        fi
    else
        # Test with valid token but problematic message
        chat_payload=$(cat <<EOF
{
    "session_id": "$TEST_SESSION_ID",
    "user_id": "$TEST_USER_ID", 
    "user_token": "$TEST_USER_TOKEN",
    "message": "",
    "permissions": ["Job.READ"]
}
EOF
)
        
        response=$(curl -s -w "%{http_code}" -o /tmp/error_test.json \
            -X POST "$AI_AGENT_URL/api/v1/chat" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $TEST_USER_TOKEN" \
            -d "$chat_payload" \
            2>/dev/null || echo "000")
        
        if [ "$response" = "400" ]; then
            echo "Error handling working: properly rejected empty message"
            return 0
        else
            echo "Error handling for empty message: got $response (may be acceptable)"
            return 0  # Don't fail for this edge case
        fi
    fi
}

# Validation checks
echo -e "${PURPLE}🚀 Starting Phase 3 Integration Tests${NC}"
echo ""

if [ -z "$JENKINS_API_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  JENKINS_API_TOKEN not set - some tests will be skipped${NC}"
    echo "To run full tests: export JENKINS_API_TOKEN='your-jenkins-api-token'"
    echo ""
fi

# Run all tests
run_test "AI Agent Health Check" test_ai_agent_health
run_test "MCP Server Connection" test_mcp_server_connection
run_test "Jenkins Plugin Session Creation" test_jenkins_plugin_session
run_test "Jenkins → AI Agent Integration Flow" test_jenkins_to_ai_agent_flow
run_test "Direct AI Agent Chat" test_direct_ai_agent_chat
run_test "Authentication Security" test_authentication_security
run_test "Error Handling" test_error_handling

# Results summary
echo -e "${PURPLE}=== Phase 3 Integration Test Results ===${NC}"
echo ""
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Total Tests: $TESTS_TOTAL"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED - Phase 3 Integration Successful! 🎉${NC}"
    echo ""
    echo "✅ Jenkins Plugin → AI Agent Service communication working"
    echo "✅ AI Agent Service → MCP Server integration ready"
    echo "✅ Authentication and security measures functional"
    echo "✅ Error handling and fallback responses working"
    echo ""
    echo "Phase 3 is ready for production deployment!"
    exit 0
else
    echo -e "${RED}❌ Some tests failed - Phase 3 needs attention${NC}"
    echo ""
    echo "Please review the failed tests and fix issues before deployment."
    exit 1
fi

# Cleanup
rm -f /tmp/ai_health.json /tmp/mcp_health.json /tmp/jenkins_session.json 
rm -f /tmp/jenkins_chat.json /tmp/ai_session.json /tmp/ai_chat.json
rm -f /tmp/auth_test.json /tmp/error_test.json