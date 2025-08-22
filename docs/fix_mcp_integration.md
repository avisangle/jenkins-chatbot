# MCP Integration Fix

## Problem
AI Agent Service expects HTTP endpoints but MCP Server uses MCP protocol.

## Solution Options

### Option 1: Update AI Agent to use MCP Client (Recommended)

Replace HTTP calls in `mcp_service.py` with MCP client:

```python
from mcp import Client
import asyncio

class MCPService:
    def __init__(self):
        self.mcp_client = None
    
    async def _get_mcp_client(self):
        if not self.mcp_client:
            # Connect to MCP server
            self.mcp_client = Client()
            await self.mcp_client.connect("stdio", command=["python", "jenkins_mcp_server_enhanced.py"])
        return self.mcp_client
    
    async def get_jenkins_recommendations(self, user_context, query):
        client = await self._get_mcp_client()
        
        # Use available MCP tools
        jobs = await client.call_tool("list_jobs", {"recursive": True})
        job_info = await client.call_tool("get_job_info", {"job_name": "some-job"})
        
        # Generate recommendations based on available tools
        return self._generate_recommendations(jobs, job_info, query)
```

### Option 2: Add HTTP Wrapper to MCP Server

Add HTTP endpoints to MCP server that wrap MCP tools:

```python
from fastapi import FastAPI

# Add to jenkins_mcp_server_enhanced.py
app = FastAPI()

@app.post("/tools/recommend")
async def recommend_endpoint(request: dict):
    # Use existing MCP tools
    jobs = await list_jobs(recursive=True)
    return {"recommendations": generate_recommendations(jobs)}

# Run both MCP and HTTP server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
```

### Option 3: Update AI Agent to Use Jenkins API Directly

Simplify by removing MCP dependency and use Jenkins API directly in AI Agent.

## Recommended Approach

**Option 1** is cleanest - update AI Agent Service to use MCP client protocol instead of HTTP calls.