#!/usr/bin/env python3
"""
Test LLM-First AI Service Implementation
"""

import asyncio
import httpx
import time
import json

async def test_llm_first_service():
    """Test the LLM-First architecture via the API"""
    
    print("=== Testing LLM-First AI Service ===\n")
    
    # Create a test session first
    session_data = {
        "user_id": "test_user",
        "user_token": "test_token_123",
        "permissions": ["read", "build"],
        "session_timeout": 900
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Create session
            print("📝 Creating test session...")
            session_response = await client.post(
                "http://localhost:8000/api/v1/session/create",
                json=session_data
            )
            
            if session_response.status_code != 200:
                print(f"❌ Session creation failed: {session_response.status_code}")
                print(f"Response: {session_response.text}")
                return False
            
            session_info = session_response.json()
            session_id = session_info["session_id"]
            print(f"✅ Session created: {session_id}")
            
            # Step 2: Create authentication token (matching Jenkins plugin format)
            current_time_ms = int(time.time() * 1000)
            expiry_time = current_time_ms + (15 * 60 * 1000)  # 15 minutes
            auth_token = f"jenkins_token_test_user_{session_id}_{expiry_time}"
            
            # Step 3: Test simple job listing request
            print("\n🔍 Testing: 'List all Jenkins jobs'")
            chat_request = {
                "message": "List all Jenkins jobs for me",
                "session_id": session_id,
                "user_id": "test_user",
                "user_token": "test_token_123",
                "permissions": ["read", "build"],
                "context": {
                    "jenkins_url": "http://localhost:8080",
                    "source": "test"
                }
            }
            
            headers = {"Authorization": f"Bearer {auth_token}"}
            
            start_time = time.time()
            chat_response = await client.post(
                "http://localhost:8000/api/v1/chat",
                json=chat_request,
                headers=headers
            )
            processing_time = int((time.time() - start_time) * 1000)
            
            if chat_response.status_code != 200:
                print(f"❌ Chat request failed: {chat_response.status_code}")
                print(f"Response: {chat_response.text}")
                return False
            
            response_data = chat_response.json()
            
            print(f"✅ Response received ({processing_time}ms):")
            print(f"Intent: {response_data.get('intent_detected', 'unknown')}")
            print(f"Confidence: {response_data.get('confidence_score', 0.0)}")
            print(f"Response: {response_data.get('response', '')[:200]}...")
            
            # Step 4: Test complex iterative query
            print("\n🔄 Testing iterative query: 'What's the console output for the latest successful build?'")
            
            complex_request = {
                "message": "What's the console output for the latest successful build of the OracleCCB-CICD-Pipeline Jenkins job?",
                "session_id": session_id,
                "user_id": "test_user", 
                "user_token": "test_token_123",
                "permissions": ["read", "build"],
                "context": {
                    "jenkins_url": "http://localhost:8080",
                    "source": "test"
                }
            }
            
            start_time = time.time()
            complex_response = await client.post(
                "http://localhost:8000/api/v1/chat",
                json=complex_request,
                headers=headers
            )
            processing_time = int((time.time() - start_time) * 1000)
            
            if complex_response.status_code != 200:
                print(f"❌ Complex request failed: {complex_response.status_code}")
                print(f"Response: {complex_response.text}")
                return False
            
            complex_data = complex_response.json()
            
            print(f"✅ Complex response received ({processing_time}ms):")
            print(f"Intent: {complex_data.get('intent_detected', 'unknown')}")
            print(f"Response: {complex_data.get('response', '')[:300]}...")
            
            # Step 5: Check if responses show signs of LLM-First architecture
            is_llm_first = False
            if response_data.get('intent_detected') == 'llm_determined':
                is_llm_first = True
                print("\n🎯 LLM-First architecture detected!")
            elif "I'll list" in response_data.get('response', ''):
                print("\n🎯 Response format suggests LLM-First architecture")
                is_llm_first = True
            else:
                print("\n⚠️  Response format suggests legacy architecture")
            
            return is_llm_first
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_health_check():
    """Test health check endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/health")
            
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Health check passed: {health_data['status']}")
                print(f"   AI Service: {health_data.get('ai_service_healthy', False)}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Starting LLM-First Implementation Test\n")
    
    # Test health first
    print("🏥 Testing service health...")
    health_ok = await test_health_check()
    
    if not health_ok:
        print("❌ Service health check failed - aborting tests")
        return
    
    # Test LLM-First functionality
    success = await test_llm_first_service()
    
    print(f"\n📊 Test Results:")
    print(f"   Health Check: {'✅' if health_ok else '❌'}")
    print(f"   LLM-First Service: {'✅' if success else '❌'}")
    
    if success:
        print("\n🎉 LLM-First implementation is working!")
    else:
        print("\n⚠️  LLM-First implementation needs debugging")

if __name__ == "__main__":
    asyncio.run(main())