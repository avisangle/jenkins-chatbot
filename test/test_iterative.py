#!/usr/bin/env python3
"""
Test LLM-First Iterative Tool Execution
"""

import asyncio
import httpx
import time

async def test_iterative_execution():
    """Test complex multi-step queries"""
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Create session
            print("📝 Creating session...")
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
            
            # Test 1: Simple job listing (should use list_jobs tool)
            print("\n🔍 Test 1: Simple job listing")
            test1_request = {
                "message": "List all Jenkins jobs",
                "session_id": session_id,
                "user_id": "test_user",
                "user_token": "testtoken123",
                "permissions": ["read", "build"],
                "context": {"jenkins_url": "http://localhost:8080"}
            }
            
            start = time.time()
            response1 = await client.post(
                "http://localhost:8000/api/v1/chat",
                json=test1_request,
                headers=headers
            )
            duration1 = int((time.time() - start) * 1000)
            
            if response1.status_code == 200:
                data1 = response1.json()
                print(f"✅ Success ({duration1}ms)")
                print(f"Response: {data1.get('response', '')}")
            else:
                print(f"❌ Failed: {response1.status_code}")
            
            # Test 2: Complex iterative query requiring multiple tools
            print("\n🔄 Test 2: Complex iterative query")
            test2_request = {
                "message": "What's the console output for the latest successful build of the OracleCCB-CICD-Pipeline Jenkins job?",
                "session_id": session_id,
                "user_id": "test_user", 
                "user_token": "testtoken123",
                "permissions": ["read", "build"],
                "context": {"jenkins_url": "http://localhost:8080"}
            }
            
            start = time.time()
            response2 = await client.post(
                "http://localhost:8000/api/v1/chat",
                json=test2_request,
                headers=headers
            )
            duration2 = int((time.time() - start) * 1000)
            
            if response2.status_code == 200:
                data2 = response2.json()
                print(f"✅ Success ({duration2}ms)")
                print(f"Response: {data2.get('response', '')[:300]}...")
                
                # Check for signs of iterative execution
                if "I need" in data2.get('response', '') or "first" in data2.get('response', '').lower():
                    print("🎯 Appears to show iterative reasoning")
                else:
                    print("⚠️  No clear signs of iterative execution")
                    
            else:
                print(f"❌ Failed: {response2.status_code}")
                print(response2.text)
                
            # Test 3: Job status query
            print("\n📊 Test 3: Job status query")
            test3_request = {
                "message": "Check the build status of my-test-job",
                "session_id": session_id,
                "user_id": "test_user",
                "user_token": "testtoken123", 
                "permissions": ["read", "build"],
                "context": {"jenkins_url": "http://localhost:8080"}
            }
            
            start = time.time()
            response3 = await client.post(
                "http://localhost:8000/api/v1/chat",
                json=test3_request,
                headers=headers
            )
            duration3 = int((time.time() - start) * 1000)
            
            if response3.status_code == 200:
                data3 = response3.json()
                print(f"✅ Success ({duration3}ms)")
                print(f"Response: {data3.get('response', '')}")
            else:
                print(f"❌ Failed: {response3.status_code}")
                
            print(f"\n📊 Summary:")
            print(f"   Test 1 (Simple): {'✅' if response1.status_code == 200 else '❌'}")
            print(f"   Test 2 (Complex): {'✅' if response2.status_code == 200 else '❌'}")  
            print(f"   Test 3 (Status): {'✅' if response3.status_code == 200 else '❌'}")
            
            return response1.status_code == 200 and response2.status_code == 200 and response3.status_code == 200
                
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_iterative_execution())
    print(f"\n🎯 Iterative execution test: {'✅ PASSED' if result else '❌ FAILED'}")