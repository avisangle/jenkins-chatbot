#!/usr/bin/env python3
"""
Detailed LLM-First Test with Real Jenkins Data
"""

import asyncio
import httpx
import time

async def test_real_jenkins_data():
    """Test LLM-First with actual Jenkins jobs"""
    
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
            
            # Test with actual Jenkins job names we know exist
            tests = [
                {
                    "name": "List jobs explicitly",
                    "message": "I need list_jobs",
                    "expect_tools": True
                },
                {
                    "name": "Real job info request",
                    "message": "I need get_job_info for C2M-DEMO-JENKINS", 
                    "expect_tools": True
                },
                {
                    "name": "Natural language job listing",
                    "message": "Show me all the Jenkins jobs available",
                    "expect_tools": True
                },
                {
                    "name": "Specific job status",
                    "message": "What's the status of OracleCCB-CICD-Pipeline?",
                    "expect_tools": True
                },
                {
                    "name": "Complex query with real job",
                    "message": "Get the console log for the latest build of C2M-DEMO-JENKINS",
                    "expect_tools": True
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
                    
                    # Check if it actually called tools vs just gave a generic response
                    has_real_data = any(job in response_text for job in [
                        'C2M-DEMO-JENKINS', 'OracleCCB-CICD-Pipeline', 'C2M_DEMO_GIT'
                    ])
                    
                    shows_tool_calls = any(phrase in response_text for phrase in [
                        'I need', 'list_jobs', 'get_job_info', 'calling', 'tool', 'executing'
                    ])
                    
                    if has_real_data:
                        print("🎯 Contains real Jenkins job data!")
                        results.append("success_with_data")
                    elif shows_tool_calls:
                        print("🔧 Shows tool calling intent")
                        results.append("success_with_tools")
                    else:
                        print("⚠️  Generic response - may not be calling tools")
                        results.append("success_generic")
                        
                else:
                    print(f"❌ Failed: {response.status_code}")
                    print(f"Error Response: {response.text}")
                    results.append("failed")
                    
                # Small delay between tests
                await asyncio.sleep(1)
            
            print(f"\n📊 Results Summary:")
            for i, (test, result) in enumerate(zip(tests, results)):
                status_emoji = {
                    "success_with_data": "🎯",
                    "success_with_tools": "🔧", 
                    "success_generic": "⚠️",
                    "failed": "❌"
                }[result]
                print(f"   {i+1}. {test['name']}: {status_emoji}")
            
            # Count successes
            successes = sum(1 for r in results if r.startswith("success"))
            with_data = sum(1 for r in results if r == "success_with_data")
            
            print(f"\n🎯 Overall: {successes}/{len(tests)} successful")
            print(f"🎯 With real data: {with_data}/{len(tests)}")
            
            return successes == len(tests) and with_data > 0
                
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_real_jenkins_data())
    print(f"\n🎯 LLM-First detailed test: {'✅ PASSED' if result else '❌ NEEDS WORK'}")