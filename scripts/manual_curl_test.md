# Manual Curl Testing for Jenkins Chatbot CSRF

## Prerequisites
- Jenkins running on `http://localhost:8080` (adjust URL as needed)
- Jenkins admin credentials
- `curl` and `jq` installed

## Step-by-Step Manual Testing

### 1. Set Environment Variables
```bash
export JENKINS_URL="http://localhost:8080"
export JENKINS_USER="admin"
export JENKINS_PASSWORD="your-admin-password"  # Replace with actual password
export COOKIE_JAR="/tmp/jenkins_cookies.txt"
```

### 2. Login and Get Session Cookies
```bash
curl -c $COOKIE_JAR \
     -d "j_username=$JENKINS_USER" \
     -d "j_password=$JENKINS_PASSWORD" \
     -d "from=" \
     -d "Submit=Sign in" \
     -L \
     "$JENKINS_URL/j_acegi_security_check" \
     -v
```

**Expected**: Should create cookies file, return 200, possibly redirect to dashboard

### 3. Fetch CSRF Crumb
```bash
curl -s -b $COOKIE_JAR \
     "$JENKINS_URL/crumbIssuer/api/json" | jq .
```

**Expected Output**:
```json
{
  "crumb": "72b2ee6c745952b7e4742d0229e2b43df1b4808cbdcc24e8c717561a19c253e0",
  "crumbRequestField": "Jenkins-Crumb"
}
```

### 4. Save Crumb Values
```bash
export CRUMB_DATA=$(curl -s -b $COOKIE_JAR "$JENKINS_URL/crumbIssuer/api/json")
export CRUMB_FIELD=$(echo $CRUMB_DATA | jq -r .crumbRequestField)
export CRUMB_VALUE=$(echo $CRUMB_DATA | jq -r .crumb)

echo "Crumb Field: $CRUMB_FIELD"
echo "Crumb Value: $CRUMB_VALUE"
```

### 5. Test Plugin Health (No CSRF needed)
```bash
curl -s -b $COOKIE_JAR \
     "$JENKINS_URL/plugin/jenkins-chatbot/health" \
     -w "\nHTTP Code: %{http_code}\n"
```

**Expected**: `{"status":"ok","version":"1.0.0"}` with HTTP 200

### 6. Test Session Creation WITH CSRF Token
```bash
curl -s -b $COOKIE_JAR \
     -H "Content-Type: application/json" \
     -H "$CRUMB_FIELD: $CRUMB_VALUE" \
     -X POST \
     "$JENKINS_URL/plugin/jenkins-chatbot/api/session" \
     -w "\nHTTP Code: %{http_code}\n" \
     -v
```

**Expected**: Should return session data with HTTP 201:
```json
{
  "sessionId": "uuid-here",
  "userId": "admin", 
  "permissions": ["..."],
  "createdAt": 1234567890,
  "expiresAt": 1234568790
}
```

### 7. Test Session Creation WITHOUT CSRF Token (Should Fail)
```bash
curl -s -b $COOKIE_JAR \
     -H "Content-Type: application/json" \
     -X POST \
     "$JENKINS_URL/plugin/jenkins-chatbot/api/session" \
     -w "\nHTTP Code: %{http_code}\n"
```

**Expected**: HTTP 403 with CSRF error

## Troubleshooting Common Issues

### Issue 1: "Found invalid crumb"
- **Cause**: Crumb was valid when fetched but became invalid
- **Solutions**: 
  - Ensure cookies are maintained between requests
  - Fetch fresh crumb immediately before use
  - Check if session expired

### Issue 2: "No valid crumb was included"
- **Cause**: CSRF header not sent or incorrect header name
- **Solutions**:
  - Verify `$CRUMB_FIELD` contains "Jenkins-Crumb"
  - Check header format: `-H "Jenkins-Crumb: value"`
  - Ensure no extra whitespace in header

### Issue 3: Plugin endpoints return 404
- **Cause**: Plugin not installed or not active
- **Solutions**:
  - Check plugin installation: Go to Manage Jenkins → Manage Plugins
  - Verify plugin is enabled and active
  - Restart Jenkins after plugin installation

### Issue 4: Login fails
- **Cause**: Wrong credentials or authentication method
- **Solutions**:
  - Verify admin password
  - Check if Jenkins uses different auth (LDAP, etc.)
  - Try API token instead of password

## Quick Debug Commands

### Check if plugin is loaded:
```bash
curl -s -b $COOKIE_JAR \
     "$JENKINS_URL/pluginManager/api/json?depth=1" | \
     jq '.plugins[] | select(.shortName=="jenkins-chatbot")'
```

### Check current user permissions:
```bash
curl -s -b $COOKIE_JAR \
     "$JENKINS_URL/me/api/json" | jq .
```

### Test CSRF protection is enabled:
```bash
curl -s -b $COOKIE_JAR \
     "$JENKINS_URL/configure" | grep -i csrf
```

## Cleanup
```bash
rm -f $COOKIE_JAR
```