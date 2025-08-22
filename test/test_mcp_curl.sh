#!/bin/bash
# MCP Server Curl Testing Script
# Tests MCP protocol directly using HTTP requests

set -e

MCP_URL="http://localhost:8010/mcp"
echo "=== MCP Server Curl Testing ==="
echo "Target: $MCP_URL"

# Test 1: List Tools
echo -e "\n🔧 Testing: List Available Tools"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
  }' | jq .

# Test 2: Server Info Tool
echo -e "\n📊 Testing: server_info() tool"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "server_info",
      "arguments": {}
    },
    "id": 2
  }' | jq .

# Test 3: List Jobs Tool
echo -e "\n📂 Testing: list_jobs() tool"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
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
  }' | jq .

# Test 4: Get Queue Info
echo -e "\n📊 Testing: get_queue_info() tool"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_queue_info",
      "arguments": {}
    },
    "id": 4
  }' | jq .

# Test 5: Get Job Info (with known job)
echo -e "\n🎯 Testing: get_job_info() with real job"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
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
  }' | jq .

# Test 6: Get Build Status (with known build)
echo -e "\n📈 Testing: get_build_status() with real build"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
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
  }' | jq .

# Test 7: Cache Statistics
echo -e "\n📊 Testing: get_cache_statistics() tool"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_cache_statistics",
      "arguments": {}
    },
    "id": 7
  }' | jq .

# Test 8: Error Handling - Invalid Tool
echo -e "\n❌ Testing: Invalid tool name (should fail)"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "invalid_tool_name",
      "arguments": {}
    },
    "id": 8
  }' | jq .

# Test 9: Error Handling - Invalid Job
echo -e "\n❌ Testing: get_job_info() with invalid job"
curl -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_job_info",
      "arguments": {
        "job_name": "invalid-job-name-12345"
      }
    },
    "id": 9
  }' | jq .

echo -e "\n✅ MCP Curl Testing Complete!"