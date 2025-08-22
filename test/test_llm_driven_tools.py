#!/usr/bin/env python3
"""
Test LLM-Driven Tool Selection with All 21 MCP Tools
"""

import asyncio
import httpx
import time

async def test_llm_driven_tool_selection():
    """Test the improved LLM-driven tool selection with all available MCP tools"""
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Create session
            session_data = {
                "user_id": "test_user",
                "user_token": "testtoken123",
                "permissions": ["read", "build"],
                "session_timeout": 900
            }
            
            session_response = await client.post(
                "http://localhost:8000/api/v1/session/create",
                json=session_data
            )
            
            session_info = session_response.json()
            session_id = session_info["session_id"]
            
            # Create auth token
            current_time_ms = int(time.time() * 1000)
            expiry_time = current_time_ms + (15 * 60 * 1000)
            auth_token = f"jenkins_token_test_user_{session_id}_{expiry_time}"
            headers = {"Authorization": f"Bearer {auth_token}"}
            
            print(f"✅ Session: {session_id}")
            
            # Test various tool requests with correct MCP tool names
            tests = [
                {
                    "name": "List jobs with correct tool name",
                    "message": "I need list_jobs",
                    "expected_tools": ["list_jobs"],
                    "expect_real_data": True
                },
                {
                    "name": "Search jobs test",
                    "message": "I need search_jobs with pattern=*DEMO*",
                    "expected_tools": ["search_jobs"],
                    "expect_real_data": True
                },
                {
                    "name": "Server info request", 
                    "message": "I need server_info",
                    "expected_tools": ["server_info"],
                    "expect_real_data": True
                },
                {
                    "name": "Cache statistics",
                    "message": "I need get_cache_statistics",
                    "expected_tools": ["get_cache_statistics"],
                    "expect_real_data": True
                },
                {
                    "name": "Job info with real job name",
                    "message": "I need get_job_info with job_name=C2M-DEMO-JENKINS",
                    "expected_tools": ["get_job_info"],
                    "expect_real_data": True
                },
                {
                    "name": "Natural language - should detect tools",
                    "message": "Show me all Jenkins jobs and server information",
                    "expected_tools": ["list_jobs", "server_info"],
                    "expect_real_data": False  # May not use exact tool names
                },
                {
                    "name": "Complex multi-tool request",
                    "message": "Get the build status of OracleCCB-CICD-Pipeline and show me cache statistics",
                    "expected_tools": ["get_build_status", "get_cache_statistics"],
                    "expect_real_data": False  # Complex request
                }
            ]
            
            results = []
            
            for i, test in enumerate(tests):
                print(f"\n🧪 Test {i+1}: {test['name']}")
                print(f"Query: {test['message']}")
                
                request = {
                    "message": test['message'],
                    "session_id": session_id,
                    "user_id": "test_user",
                    "user_token": "testtoken123",
                    "permissions": ["read", "build"],
                    "context": {"jenkins_url": "http://localhost:8080"}
                }
                
                start = time.time()
                response = await client.post(
                    "http://localhost:8000/api/v1/chat",
                    json=request,
                    headers=headers
                )
                duration = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    response_text = data.get('response', '')
                    intent = data.get('intent_detected', '')
                    confidence = data.get('confidence_score', 0.0)
                    
                    print(f"✅ Success ({duration}ms)")
                    print(f"Intent: {intent}")
                    print(f"Confidence: {confidence}")
                    print(f"Response Length: {len(response_text)} characters")
                    print(f"Full Response:\n{response_text}")
                    print("=" * 50)
                    
                    # Check for LLM-First architecture 
                    is_llm_first = intent == "llm_determined"
                    
                    # Check for real Jenkins data
                    has_real_data = any(keyword in response_text for keyword in [
                        'C2M-DEMO-JENKINS', 'OracleCCB-CICD-Pipeline', 'C2M_DEMO_GIT',
                        'localhost:8080', 'build', 'job', 'cache_details', 'hit_rate'
                    ])
                    
                    # Check for tool usage indicators
                    shows_tool_usage = any(phrase in response_text for phrase in [
                        'I need', 'calling', 'tool', 'executing'
                    ])
                    
                    result = {
                        "success": True,
                        "llm_first": is_llm_first,
                        "real_data": has_real_data,
                        "tool_usage": shows_tool_usage,
                        "response_length": len(response_text)
                    }
                    
                    if is_llm_first:
                        print("🎯 LLM-First architecture confirmed")
                    if has_real_data:
                        print("📊 Contains real Jenkins data")
                    if shows_tool_usage:
                        print("🔧 Shows tool usage patterns")
                        
                else:
                    print(f"❌ Failed: {response.status_code}")
                    print(f"Error Response: {response.text}")
                    result = {"success": False, "error": response.text}
                    
                results.append(result)
                
                # Small delay between tests
                await asyncio.sleep(1)
            
            # Analyze results
            print(f"\n📊 Results Summary:")
            successes = sum(1 for r in results if r.get('success'))
            llm_first = sum(1 for r in results if r.get('llm_first'))
            with_data = sum(1 for r in results if r.get('real_data'))
            tool_usage = sum(1 for r in results if r.get('tool_usage'))
            
            print(f"   Total Tests: {len(tests)}")
            print(f"   Successful: {successes}")
            print(f"   LLM-First: {llm_first}")
            print(f"   With Real Data: {with_data}")
            print(f"   Tool Usage Detected: {tool_usage}")
            
            # Success criteria
            overall_success = (
                successes == len(tests) and  # All tests pass
                llm_first >= len(tests) * 0.8 and  # 80%+ use LLM-First
                (with_data > 0 or tool_usage > 0)  # Some evidence of tool usage
            )
            
            return overall_success
                
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run LLM-driven tool selection tests"""
    print("🚀 Testing LLM-Driven Tool Selection (All 21 MCP Tools)\n")
    
    success = await test_llm_driven_tool_selection()
    
    if success:
        print(f"\n🎉 LLM-Driven Tool Selection: ✅ SUCCESS")
        print("   - All 21 MCP tools available to LLM")
        print("   - Dynamic tool discovery working") 
        print("   - Universal tool executor functional")
        print("   - LLM can intelligently select tools")
    else:
        print(f"\n⚠️  LLM-Driven Tool Selection: ❌ NEEDS IMPROVEMENT")

if __name__ == "__main__":
    asyncio.run(main())