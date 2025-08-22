#!/usr/bin/env python3
"""
Test LLM-First AI Service Implementation - Fixed Authentication
"""

import asyncio
import httpx
import time
import json

async def test_llm_first_service():
    """Test the LLM-First architecture via the API"""
    
    print("=== Testing LLM-First AI Service ===\n")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Create session without authentication first
            print("📝 Creating test session...")
            session_data = {
                "user_id": "test_user",
                "user_token": "test_token_123",
                "permissions": ["read", "build"],
                "session_timeout": 900
            }
            
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
            
            # Step 2: Create proper authentication token
            current_time_ms = int(time.time() * 1000)
            expiry_time = current_time_ms + (15 * 60 * 1000)  # 15 minutes from now
            
            # Format: jenkins_token_{userId}_{sessionId}_{expiry}
            auth_token = f"jenkins_token_test_user_{session_id}_{expiry_time}"
            print(f"🔑 Auth token: {auth_token[:50]}...")
            
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
            
            print(f"📡 Chat response status: {chat_response.status_code}")
            
            if chat_response.status_code != 200:
                print(f"❌ Chat request failed: {chat_response.status_code}")
                print(f"Response: {chat_response.text}")
                # Try to parse error details
                try:
                    error_data = chat_response.json()
                    print(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    pass
                return False
            
            response_data = chat_response.json()
            
            print(f"✅ Response received ({processing_time}ms):")
            print(f"Intent: {response_data.get('intent_detected', 'unknown')}")
            print(f"Confidence: {response_data.get('confidence_score', 0.0)}")
            print(f"Response Time: {response_data.get('response_time_ms', 0)}ms")
            print(f"Response: {response_data.get('response', '')}")
            
            # Check for LLM-First indicators
            is_llm_first = False
            if response_data.get('intent_detected') == 'llm_determined':
                is_llm_first = True
                print("\n🎯 LLM-First architecture confirmed!")
            elif "I'll list" in response_data.get('response', '') or "I'll " in response_data.get('response', ''):
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
                print(f"   Database: {health_data.get('database_healthy', False)}")
                print(f"   Redis: {health_data.get('redis_healthy', False)}")
                print(f"   AI Service: {health_data.get('ai_service_healthy', False)}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

async def test_architecture_detection():
    """Test which architecture is currently active"""
    try:
        # Check Docker container environment
        import os
        use_llm_first = os.getenv('USE_LLM_FIRST_ARCHITECTURE', 'false').lower() == 'true'
        print(f"🏗️  Environment flag USE_LLM_FIRST_ARCHITECTURE: {use_llm_first}")
        
        # Try to import and check the config directly
        import sys
        sys.path.append('/app')
        
        try:
            from app.config import settings
            print(f"🔧 Config USE_LLM_FIRST_ARCHITECTURE: {settings.USE_LLM_FIRST_ARCHITECTURE}")
            return settings.USE_LLM_FIRST_ARCHITECTURE
        except Exception as e:
            print(f"⚠️  Could not check config: {e}")
            return use_llm_first
            
    except Exception as e:
        print(f"❌ Architecture detection error: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Starting LLM-First Implementation Test\n")
    
    # Test architecture detection
    print("🔍 Detecting current architecture...")
    is_llm_first_enabled = await test_architecture_detection()
    
    # Test health first
    print("\n🏥 Testing service health...")
    health_ok = await test_health_check()
    
    if not health_ok:
        print("❌ Service health check failed - aborting tests")
        return
    
    # Test LLM-First functionality
    print(f"\n🚀 Testing {'LLM-First' if is_llm_first_enabled else 'Legacy'} architecture...")
    success = await test_llm_first_service()
    
    print(f"\n📊 Test Results:")
    print(f"   Architecture: {'LLM-First' if is_llm_first_enabled else 'Legacy'}")
    print(f"   Health Check: {'✅' if health_ok else '❌'}")
    print(f"   Service Test: {'✅' if success else '❌'}")
    
    if success and is_llm_first_enabled:
        print("\n🎉 LLM-First implementation is working!")
    elif success and not is_llm_first_enabled:
        print("\n✅ Legacy implementation is working")
    else:
        print("\n⚠️  Implementation needs debugging")

if __name__ == "__main__":
    asyncio.run(main())