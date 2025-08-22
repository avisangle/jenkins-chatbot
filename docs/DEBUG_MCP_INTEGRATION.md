# MCP Integration Debug Steps

## Problem Summary
- MCP server starts successfully when run manually 
- MCP client connection via AI Agent fails with timeouts
- Suspected protocol mismatch between FastMCP (server) and official MCP SDK (client)
- STDIO communication appears to hang during session initialization

## Root Cause Analysis
- **Server**: Uses FastMCP library with STDIO transport
- **Client**: Uses official MCP Python SDK with stdio_client
- **Issue**: Protocol incompatibility causing communication deadlock

## Debug Steps (Execute in Order)

### Step 1: Verify Current State
```bash
# Check if containers are running
docker ps | grep jenkins-chatbot

# Check current health status
curl -s http://12.0.0.85:8000/health | jq

# Check container logs for MCP errors
docker logs jenkins-chatbot-ai-agent --tail 50 | grep -i mcp
```

### Step 2: Test MCP Server Standalone
```bash
# Enter container
docker exec -it jenkins-chatbot-ai-agent bash

# Test MCP server standalone (should work)
python3 /app/jenkins_mcp_server_enhanced.py --help

# Test MCP server with specific transport
python3 /app/jenkins_mcp_server_enhanced.py --transport stdio
# (This should start and show duplicate log messages, then hang waiting for input)
```

### Step 3: Test Protocol Compatibility
```bash
# Inside container - test if FastMCP and MCP SDK are compatible
python3 -c "
from fastmcp import FastMCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
print('Both libraries imported successfully')
"
```

### Step 4: Fix Option A - Switch to HTTP Transport
This avoids STDIO protocol mismatch by using HTTP communication.

**4a. Modify MCP Server to Use HTTP**
```bash
# Edit the MCP service to start server in HTTP mode
# Update: /app/app/services/mcp_service.py
# Change server startup args from --transport stdio to --transport http --port 8011
```

**4b. Update MCP Client to Use HTTP**
```python
# Replace stdio_client with HTTP client in mcp_service.py
# Use requests or httpx to call HTTP endpoints instead of STDIO
```

### Step 5: Fix Option B - Use Official MCP Server
Replace FastMCP with official MCP SDK server implementation.

**5a. Check Official MCP Server Example**
```bash
# Look at official MCP Python SDK examples
# https://github.com/modelcontextprotocol/python-sdk/tree/main/examples
```

**5b. Rewrite MCP Server Using Official SDK**
```python
# Replace FastMCP with official MCP server implementation
# This ensures protocol compatibility
```

### Step 6: Fix Option C - Use FastMCP Client
Keep FastMCP server but switch client to FastMCP's client library.

**6a. Check FastMCP Client Documentation**
```bash
# Check if FastMCP provides a client library
pip3 show fastmcp
```

### Step 7: Test Simple Protocol Communication
```bash
# Create minimal test to isolate the issue
# Test basic JSON-RPC communication between client and server
```

## Recommended Fix (Option A - HTTP Transport)

### Step A1: Update MCP Service Configuration
```python
# File: ai-agent/app/config.py
# Add HTTP transport settings
MCP_SERVER_HTTP_PORT: int = 8011
MCP_USE_HTTP_TRANSPORT: bool = True
```

### Step A2: Modify MCP Service
```python
# File: ai-agent/app/services/mcp_service.py
# Replace STDIO client with HTTP client

import httpx
from typing import Dict, Any

class MCPService:
    def __init__(self):
        self.base_url = f"http://localhost:{settings.MCP_SERVER_HTTP_PORT}"
        self.server_process = None
        
    async def _ensure_connection(self):
        if not self.server_process:
            # Start MCP server in HTTP mode
            self.server_process = subprocess.Popen([
                "python3", "/app/jenkins_mcp_server_enhanced.py",
                "--transport", "http", 
                "--port", str(settings.MCP_SERVER_HTTP_PORT)
            ])
            # Wait for server to start
            await asyncio.sleep(2)
    
    async def health_check(self) -> bool:
        try:
            await self._ensure_connection()
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.error("HTTP MCP health check failed", error=str(e))
            return False
```

### Step A3: Update Docker Configuration
```yaml
# File: docker-compose.yml
# Add port mapping for MCP HTTP server
ai-agent:
  ports:
    - "8000:8000"
    - "8011:8011"  # MCP HTTP server port
```

### Step A4: Test HTTP Transport
```bash
# Rebuild container
docker-compose build ai-agent

# Restart container
docker-compose up -d ai-agent

# Test MCP HTTP endpoint
curl http://12.0.0.85:8011/health

# Test AI Agent health with MCP
curl http://12.0.0.85:8000/health
```

## Testing Commands

### Basic Health Check
```bash
curl -s http://12.0.0.85:8000/health | jq '.mcp_server_healthy'
```

### MCP Integration Test
```bash
docker exec jenkins-chatbot-ai-agent python3 /app/test_mcp_docker_integration.py
```

### Manual MCP Client Test
```bash
docker exec -it jenkins-chatbot-ai-agent python3 /app/test_mcp_direct.py
```

## Expected Results After Fix

### Health Endpoint Response
```json
{
  "status": "ok",
  "database_healthy": true,
  "redis_healthy": true, 
  "ai_service_healthy": true,
  "mcp_server_healthy": true,  // ← Should be true
  "timestamp": 1234567890
}
```

### MCP Integration Test Output
```
🚀 Testing MCP Integration in Docker Environment

1. Testing AI Agent health...
✅ AI Agent health: OK
   Database: ✅
   Redis: ✅
   AI Service: ✅
   MCP Server: ✅  // ← Should be ✅

2. Testing chat endpoint with MCP integration...
✅ Chat endpoint: OK
   Response: Enhanced AI response with MCP integration...
✅ MCP Integration: Working correctly

3. Testing MCP server availability in container...
✅ MCP Server: Healthy and accessible

🎯 Test Summary:
✅ AI Agent service is running in Docker
✅ Chat endpoint is accessible  
✅ MCP integration is working correctly

🎉 All tests passed! MCP integration is working correctly.
```

## Troubleshooting Common Issues

### Issue: Port Conflicts
```bash
# Check if port 8011 is available
netstat -tulpn | grep 8011
```

### Issue: FastMCP HTTP Mode Not Working
```bash
# Check FastMCP documentation for HTTP transport
python3 -c "from fastmcp import FastMCP; help(FastMCP.run)"
```

### Issue: Server Still Not Responsive
```bash
# Check server logs
docker logs jenkins-chatbot-ai-agent | grep -A5 -B5 "MCP server"

# Test server directly
curl -v http://localhost:8011/
```

## Success Criteria
1. ✅ MCP server starts without hanging
2. ✅ MCP client can connect and communicate  
3. ✅ Health endpoint shows `mcp_server_healthy: true`
4. ✅ Chat endpoint uses MCP for enhanced responses
5. ✅ No more timeout errors in logs
6. ✅ Integration test passes all checks

## Files to Modify
1. `ai-agent/app/config.py` - Add HTTP transport config
2. `ai-agent/app/services/mcp_service.py` - Replace STDIO with HTTP client
3. `docker-compose.yml` - Add port mapping
4. Test and verify changes work

This systematic approach should resolve the MCP integration issues by eliminating the STDIO protocol mismatch.