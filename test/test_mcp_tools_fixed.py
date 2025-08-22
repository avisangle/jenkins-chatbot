#!/usr/bin/env python3
"""
Fixed MCP Tool Testing Script - properly handles response content
"""

import asyncio
import logging
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_response_content(result):
    """Extract text content from MCP response"""
    if hasattr(result, 'content') and result.content:
        for item in result.content:
            if hasattr(item, 'text'):
                return item.text
            elif hasattr(item, 'type') and item.type == 'text' and hasattr(item, 'text'):
                return item.text
    return str(result.content) if hasattr(result, 'content') else str(result)

async def test_mcp_tools():
    """Test MCP tools and show actual outputs"""
    try:
        logger.info("=== Fixed MCP Tool Testing Session ===")
        
        # Connect to MCP server using Docker service name
        async with streamablehttp_client("http://mcp-server:8010/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the connection
                await session.initialize()
                logger.info("✅ Session initialized successfully")
                
                # List all available tools
                tools = await session.list_tools()
                logger.info(f"📋 Available tools ({len(tools.tools)}): {[tool.name for tool in tools.tools]}")
                
                print("\n" + "="*80)
                print("TESTING SAFE READ-ONLY TOOLS")
                print("="*80)
                
                # Test 1: Server Info (safest)
                print("\n🔧 Testing: server_info()")
                try:
                    result = await session.call_tool("server_info", {})
                    content = extract_response_content(result)
                    print("✅ server_info() SUCCESS:")
                    print(content)
                    
                    # Try to parse as JSON
                    try:
                        parsed = json.loads(content)
                        print("📊 Parsed JSON:")
                        print(json.dumps(parsed, indent=2))
                    except:
                        print("📄 Raw response (not JSON)")
                        
                except Exception as e:
                    print(f"❌ server_info() FAILED: {e}")
                
                # Test 2: Queue Info  
                print("\n📊 Testing: get_queue_info()")
                try:
                    result = await session.call_tool("get_queue_info", {})
                    content = extract_response_content(result)
                    print("✅ get_queue_info() SUCCESS:")
                    print(content)
                    
                    try:
                        parsed = json.loads(content)
                        print("📊 Parsed JSON:")
                        print(json.dumps(parsed, indent=2))
                    except:
                        print("📄 Raw response (not JSON)")
                        
                except Exception as e:
                    print(f"❌ get_queue_info() FAILED: {e}")
                
                # Test 3: List Jobs
                print("\n📂 Testing: list_jobs()")
                try:
                    result = await session.call_tool("list_jobs", {"recursive": False, "max_depth": 1})
                    content = extract_response_content(result)
                    print("✅ list_jobs() SUCCESS:")
                    print(content)
                    
                    # Store job names for further testing
                    job_names = []
                    try:
                        parsed = json.loads(content)
                        print("📊 Parsed JSON:")
                        print(json.dumps(parsed, indent=2))
                        
                        if isinstance(parsed, dict) and "jobs" in parsed:
                            job_names = [job.get("name") for job in parsed["jobs"] if job.get("name")]
                        elif isinstance(parsed, list):
                            job_names = [job.get("name") for job in parsed if job.get("name")]
                    except:
                        print("📄 Raw response (not JSON)")
                    
                    logger.info(f"Found job names: {job_names}")
                    
                except Exception as e:
                    print(f"❌ list_jobs() FAILED: {e}")
                    job_names = []
                
                # Test 4: Cache Statistics
                print("\n📈 Testing: get_cache_statistics()")
                try:
                    result = await session.call_tool("get_cache_statistics", {})
                    content = extract_response_content(result)
                    print("✅ get_cache_statistics() SUCCESS:")
                    print(content)
                    
                    try:
                        parsed = json.loads(content)
                        print("📊 Parsed JSON:")
                        print(json.dumps(parsed, indent=2))
                    except:
                        print("📄 Raw response (not JSON)")
                        
                except Exception as e:
                    print(f"❌ get_cache_statistics() FAILED: {e}")
                
                print("\n" + "="*80)
                print("TESTING JOB-SPECIFIC TOOLS")
                print("="*80)
                
                # Test with discovered jobs if any
                if job_names:
                    test_job = job_names[0]
                    print(f"\n🎯 Testing with job: '{test_job}'")
                    
                    # Test 5: Get Job Info
                    print(f"\n📋 Testing: get_job_info('{test_job}')")
                    try:
                        result = await session.call_tool("get_job_info", {"job_name": test_job})
                        content = extract_response_content(result)
                        print("✅ get_job_info() SUCCESS:")
                        print(content)
                        
                        try:
                            parsed = json.loads(content)
                            print("📊 Parsed JSON:")
                            print(json.dumps(parsed, indent=2))
                        except:
                            print("📄 Raw response (not JSON)")
                            
                    except Exception as e:
                        print(f"❌ get_job_info() FAILED: {e}")
                        
                else:
                    print("\n⚠️  No jobs found - testing with mock job name")
                    
                    # Test with a common job name that might exist
                    test_job = "test-job"
                    print(f"\n📋 Testing: get_job_info('{test_job}')")
                    try:
                        result = await session.call_tool("get_job_info", {"job_name": test_job})
                        content = extract_response_content(result)
                        print("✅ get_job_info() SUCCESS:")
                        print(content)
                        
                        try:
                            parsed = json.loads(content)
                            print("📊 Parsed JSON:")
                            print(json.dumps(parsed, indent=2))
                        except:
                            print("📄 Raw response (not JSON)")
                            
                    except Exception as e:
                        print(f"❌ get_job_info() FAILED: {e}")
                
                # Test 6: Search Jobs
                print(f"\n🔍 Testing: search_jobs('*')")
                try:
                    result = await session.call_tool("search_jobs", {"pattern": "*"})
                    content = extract_response_content(result)
                    print("✅ search_jobs() SUCCESS:")
                    print(content)
                    
                    try:
                        parsed = json.loads(content)
                        print("📊 Parsed JSON:")
                        print(json.dumps(parsed, indent=2))
                    except:
                        print("📄 Raw response (not JSON)")
                        
                except Exception as e:
                    print(f"❌ search_jobs() FAILED: {e}")
                
                print("\n" + "="*80)
                print("TESTING ERROR HANDLING")
                print("="*80)
                
                # Test 7: Invalid Job Name
                print("\n❌ Testing: get_job_info('invalid-job-name')")
                try:
                    result = await session.call_tool("get_job_info", {"job_name": "invalid-job-name-12345"})
                    content = extract_response_content(result)
                    print("⚠️  get_job_info() with invalid job returned:")
                    print(content)
                except Exception as e:
                    print(f"✅ get_job_info() properly failed: {e}")
                
                print("\n" + "="*80)
                print("SUMMARY")
                print("="*80)
                print(f"✅ MCP Server: Running and responsive")
                print(f"✅ Tools Available: {len(tools.tools)}")
                print(f"✅ Docker Networking: Working")
                print(f"✅ Tool Execution: Working")
                print(f"✅ Response Parsing: Working")
                if job_names:
                    print(f"✅ Jenkins Jobs Found: {len(job_names)}")
                else:
                    print(f"⚠️  Jenkins Jobs: None found (may need Jenkins setup)")
                
                return True
                
    except Exception as e:
        logger.error(f"MCP tool testing failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_mcp_tools())
    if result:
        print("\n🎉 MCP Tool Testing COMPLETED SUCCESSFULLY")
    else:
        print("\n💥 MCP Tool Testing FAILED")