#!/bin/bash
# Fixed MCP Server Curl Testing Script
# Tests MCP protocol directly using HTTP requests with proper headers

set -e

MCP_URL="http://localhost:8010/mcp"
echo "=== MCP Server Curl Testing (Fixed) ==="
echo "Target: $MCP_URL"

# Note: MCP streamable-http requires Accept headers for both JSON and SSE
HEADERS=(
  -H "Content-Type: application/json"
  -H "Accept: application/json, text/event-stream"
)

echo -e "\n🔧 Testing: List Available Tools"
curl -X POST "$MCP_URL" \
  "${HEADERS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
  }' | jq . || echo "Failed to parse JSON response"

echo -e "\n📊 Testing: server_info() tool"
curl -X POST "$MCP_URL" \
  "${HEADERS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "server_info",
      "arguments": {}
    },
    "id": 2
  }' | jq . || echo "Failed to parse JSON response"

echo -e "\n📂 Testing: list_jobs() tool"
curl -X POST "$MCP_URL" \
  "${HEADERS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "list_jobs",
      "arguments": {
        "recursive": false,
        "max_depth": 1
      }
    },
    "id": 3
  }' | jq . || echo "Failed to parse JSON response"

echo -e "\n📊 Testing: get_queue_info() tool"
curl -X POST "$MCP_URL" \
  "${HEADERS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_queue_info",
      "arguments": {}
    },
    "id": 4
  }' | jq . || echo "Failed to parse JSON response"

echo -e "\n🎯 Testing: get_job_info() with real job"
curl -X POST "$MCP_URL" \
  "${HEADERS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_job_info",
      "arguments": {
        "job_name": "C2M-DEMO-JENKINS"
      }
    },
    "id": 5
  }' | jq . || echo "Failed to parse JSON response"

echo -e "\n📈 Testing: get_build_status() with real build"
curl -X POST "$MCP_URL" \
  "${HEADERS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_build_status",
      "arguments": {
        "job_name": "C2M-DEMO-JENKINS",
        "build_number": 20
      }
    },
    "id": 6
  }' | jq . || echo "Failed to parse JSON response"

echo -e "\n❌ Testing: Invalid tool name (should return error)"
curl -X POST "$MCP_URL" \
  "${HEADERS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "invalid_tool_name",
      "arguments": {}
    },
    "id": 7
  }' | jq . || echo "Failed to parse JSON response"

# Alternative simple test - just check if server responds
echo -e "\n🔍 Simple connectivity test"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\nResponse Time: %{time_total}s\n" "$MCP_URL" || echo "Connection failed"

echo -e "\n✅ Fixed MCP Curl Testing Complete!"
echo -e "\nNote: For full MCP protocol testing, use the Python client scripts which handle"
echo -e "the streamable HTTP protocol correctly with proper session management."