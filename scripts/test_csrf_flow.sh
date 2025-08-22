#!/bin/bash

# Jenkins Chatbot CSRF Testing Script
# Tests the CSRF token flow manually to diagnose issues

set -e

# Configuration
JENKINS_URL="http://12.0.0.85:8080"
JENKINS_USER="admin"
JENKINS_PASSWORD="y:b1og<z4y3gC_2"  # Set this to your Jenkins admin password
COOKIE_JAR="/tmp/jenkins_cookies.txt"

echo "=== Jenkins Chatbot CSRF Flow Test ==="
echo "Jenkins URL: $JENKINS_URL"
echo "User: $JENKINS_USER"
echo ""

# Clean up any existing cookies
rm -f $COOKIE_JAR

echo "Step 1: Login to Jenkins and get session cookies..."
curl -c $COOKIE_JAR \
     -d "j_username=$JENKINS_USER" \
     -d "j_password=$JENKINS_PASSWORD" \
     -d "from=" \
     -d "Submit=Sign in" \
     -L \
     "$JENKINS_URL/j_acegi_security_check" \
     -o /dev/null \
     -s

if [ ! -f $COOKIE_JAR ]; then
    echo "❌ Failed to create cookies - login may have failed"
    exit 1
fi

echo "✅ Login successful - cookies saved"
echo ""

echo "Step 2: Fetch CSRF crumb..."
CRUMB_RESPONSE=$(curl -s -b $COOKIE_JAR "$JENKINS_URL/crumbIssuer/api/json")
echo "Crumb response: $CRUMB_RESPONSE"

if [ -z "$CRUMB_RESPONSE" ] || [[ "$CRUMB_RESPONSE" == *"error"* ]]; then
    echo "❌ Failed to fetch CSRF crumb"
    echo "This might mean CSRF protection is disabled or there's an authentication issue"
    exit 1
fi

# Parse crumb data
CRUMB_FIELD=$(echo $CRUMB_RESPONSE | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['crumbRequestField'])")
CRUMB_VALUE=$(echo $CRUMB_RESPONSE | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['crumb'])")

echo "✅ CSRF crumb fetched successfully"
echo "   Field: $CRUMB_FIELD"
echo "   Value: $CRUMB_VALUE"
echo ""

echo "Step 3: Test chatbot session creation with CSRF token..."
SESSION_RESPONSE=$(curl -s -b $COOKIE_JAR \
     -H "Content-Type: application/json" \
     -H "$CRUMB_FIELD: $CRUMB_VALUE" \
     -X POST \
     "$JENKINS_URL/plugin/jenkins-chatbot/api/session" \
     -w "\nHTTP_CODE: %{http_code}\n")

echo "Session creation response:"
echo "$SESSION_RESPONSE"
echo ""

# Check if session creation was successful
if [[ "$SESSION_RESPONSE" == *"HTTP_CODE: 201"* ]] || [[ "$SESSION_RESPONSE" == *"sessionId"* ]]; then
    echo "✅ Session creation successful!"
else
    echo "❌ Session creation failed"
    echo "Checking what happens without CSRF token..."
    
    echo ""
    echo "Step 4: Test without CSRF token (should fail)..."
    NO_CSRF_RESPONSE=$(curl -s -b $COOKIE_JAR \
         -H "Content-Type: application/json" \
         -X POST \
         "$JENKINS_URL/plugin/jenkins-chatbot/api/session" \
         -w "\nHTTP_CODE: %{http_code}\n")
    
    echo "Response without CSRF:"
    echo "$NO_CSRF_RESPONSE"
fi

echo ""
echo "Step 5: Test health endpoint (should work without CSRF)..."
HEALTH_RESPONSE=$(curl -s -b $COOKIE_JAR \
     "$JENKINS_URL/plugin/jenkins-chatbot/health" \
     -w "\nHTTP_CODE: %{http_code}\n")

echo "Health check response:"
echo "$HEALTH_RESPONSE"

echo ""
echo "Step 6: Check if plugin is properly loaded..."
PLUGIN_CHECK=$(curl -s -b $COOKIE_JAR \
     "$JENKINS_URL/pluginManager/api/json?depth=1" | \
     python3 -c "
import sys, json
data = json.load(sys.stdin)
chatbot_plugin = next((p for p in data['plugins'] if p['shortName'] == 'jenkins-chatbot'), None)
if chatbot_plugin:
    print(f\"Plugin found: {chatbot_plugin['shortName']} v{chatbot_plugin['version']} - Active: {chatbot_plugin['active']}\")
else:
    print('❌ jenkins-chatbot plugin not found')
")

echo "Plugin status: $PLUGIN_CHECK"

# Cleanup
rm -f $COOKIE_JAR

echo ""
echo "=== Test Complete ==="
echo ""
echo "If session creation failed, check:"
echo "1. Jenkins admin password is correct"
echo "2. Plugin is properly installed and active"
echo "3. User has chatbot permissions"
echo "4. CSRF protection is enabled (should be by default)"