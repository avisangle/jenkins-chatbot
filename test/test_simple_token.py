#!/usr/bin/env python3
"""
Simple token test - avoid UUID parsing issues
"""

import asyncio
import httpx
import time

async def test_with_simple_token():
    """Test with a simple token that avoids UUID parsing issues"""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create session with simple IDs
            print("📝 Creating simple session...")
            session_data = {
                "user_id": "testuser",  # No underscores
                "user_token": "testtoken123",
                "permissions": ["read", "build"],
                "session_timeout": 900
            }
            
            session_response = await client.post(
                "http://localhost:8000/api/v1/session/create",
                json=session_data
            )
            
            if session_response.status_code != 200:
                print(f"❌ Session failed: {session_response.status_code}")
                print(session_response.text)
                return
            
            session_info = session_response.json()
            session_id = session_info["session_id"]
            print(f"✅ Session: {session_id}")
            
            # Create token - use base64 encoding to avoid parsing issues
            import base64
            current_time_ms = int(time.time() * 1000)
            expiry_time = current_time_ms + (15 * 60 * 1000)
            
            # Alternative token format: jenkins_token_base64(userid|sessionid|expiry)
            token_data = f"testuser|{session_id}|{expiry_time}"
            encoded_data = base64.b64encode(token_data.encode()).decode()
            auth_token = f"jenkins_token_{encoded_data}"
            
            print(f"🔑 Token format: jenkins_token_[base64]")
            print(f"🔍 Token data: {token_data}")
            
            chat_request = {
                "message": "List all Jenkins jobs for me",
                "session_id": session_id,
                "user_id": "testuser",
                "user_token": "testtoken123", 
                "permissions": ["read", "build"],
                "context": {"jenkins_url": "http://localhost:8080"}
            }
            
            headers = {"Authorization": f"Bearer {auth_token}"}
            
            response = await client.post(
                "http://localhost:8000/api/v1/chat",
                json=chat_request,
                headers=headers
            )
            
            print(f"📡 Response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ SUCCESS! Response: {data.get('response', '')[:100]}...")
                print(f"Intent: {data.get('intent_detected')}")
            else:
                print(f"❌ Error: {response.text}")
                
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_with_simple_token())