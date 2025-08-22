#!/usr/bin/env python3
"""Test script for Jenkins AI Agent Service API endpoints."""

import asyncio
import aiohttp
import json
import uuid
from datetime import datetime
import os
import sys

# Base URL for the service
BASE_URL = os.getenv('AI_AGENT_URL', 'http://localhost:8000')


class AIAgentTestClient:
    """Test client for AI Agent API."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def health_check(self):
        """Test health check endpoint."""
        print("🏥 Testing health check...")
        async with self.session.get(f"{self.base_url}/health") as resp:
            if resp.status == 200:
                health = await resp.json()
                print(f"✅ Health check passed: {health['status']}")
                print(f"   Services: {health['services']}")
                return True
            else:
                print(f"❌ Health check failed: {resp.status}")
                return False
    
    async def create_session(self):
        """Test session creation."""
        print("🔐 Creating test session...")
        
        payload = {
            "user_id": "test_user_123",
            "user_token": "test_token_" + str(uuid.uuid4()),
            "permissions": ["Job.READ", "Job.BUILD", "Item.CREATE"],
            "session_timeout": 900
        }
        
        async with self.session.post(
            f"{self.base_url}/api/v1/session/create",
            json=payload
        ) as resp:
            if resp.status == 200:
                session_data = await resp.json()
                self.session_id = session_data['session_id']
                print(f"✅ Session created: {self.session_id}")
                print(f"   Expires at: {session_data['expires_at']}")
                return True
            else:
                error = await resp.text()
                print(f"❌ Session creation failed: {resp.status} - {error}")
                return False
    
    async def test_chat_message(self, message: str, expected_intent: str = None):
        """Test chat message processing."""
        print(f"💬 Testing message: '{message}'")
        
        if not self.session_id:
            print("❌ No active session for chat test")
            return False
        
        payload = {
            "session_id": self.session_id,
            "user_token": "test_token_" + str(uuid.uuid4()),
            "user_id": "test_user_123",
            "permissions": ["Job.READ", "Job.BUILD", "Item.CREATE"],
            "message": message,
            "context": {
                "current_job": "frontend-build",
                "last_build_status": "SUCCESS"
            }
        }
        
        async with self.session.post(
            f"{self.base_url}/api/v1/chat",
            json=payload
        ) as resp:
            if resp.status == 200:
                response_data = await resp.json()
                print(f"✅ Chat response received")
                print(f"   Response: {response_data['response'][:100]}...")
                print(f"   Intent detected: {response_data.get('intent_detected')}")
                print(f"   Confidence: {response_data.get('confidence_score')}")
                print(f"   Actions: {len(response_data.get('actions', []))}")
                print(f"   Response time: {response_data.get('response_time_ms')}ms")
                
                if expected_intent and response_data.get('intent_detected') == expected_intent:
                    print(f"✅ Expected intent '{expected_intent}' detected correctly")
                
                return True
            else:
                error = await resp.text()
                print(f"❌ Chat message failed: {resp.status} - {error}")
                return False
    
    async def get_session_state(self):
        """Test session state retrieval."""
        print("📋 Getting session state...")
        
        if not self.session_id:
            print("❌ No active session for state test")
            return False
        
        async with self.session.get(
            f"{self.base_url}/api/v1/session/{self.session_id}/state"
        ) as resp:
            if resp.status == 200:
                state_data = await resp.json()
                print(f"✅ Session state retrieved")
                print(f"   User ID: {state_data['user_id']}")
                print(f"   Messages: {len(state_data['conversation_history'])}")
                print(f"   Pending actions: {len(state_data['pending_actions'])}")
                return True
            else:
                error = await resp.text()
                print(f"❌ Session state retrieval failed: {resp.status} - {error}")
                return False
    
    async def test_metrics(self):
        """Test metrics endpoint."""
        print("📊 Testing metrics...")
        
        async with self.session.get(f"{self.base_url}/api/v1/metrics?hours=1") as resp:
            if resp.status == 200:
                metrics = await resp.json()
                print("✅ Metrics retrieved")
                print(f"   Interactions: {metrics.get('interactions', {})}")
                print(f"   API calls: {metrics.get('api_calls', {})}")
                return True
            else:
                error = await resp.text()
                print(f"❌ Metrics retrieval failed: {resp.status} - {error}")
                return False
    
    async def cleanup_session(self):
        """Clean up test session."""
        if self.session_id:
            print(f"🧹 Cleaning up session {self.session_id}...")
            async with self.session.delete(
                f"{self.base_url}/api/v1/session/{self.session_id}"
            ) as resp:
                if resp.status == 200:
                    print("✅ Session cleaned up")
                    return True
                else:
                    print(f"⚠️  Session cleanup failed: {resp.status}")
                    return False
        return True


async def run_tests():
    """Run all API tests."""
    print(f"🧪 Starting API tests for {BASE_URL}")
    print("=" * 60)
    
    async with AIAgentTestClient(BASE_URL) as client:
        # Test 1: Health Check
        if not await client.health_check():
            print("❌ Health check failed - service may not be running")
            return False
        
        print()
        
        # Test 2: Session Creation
        if not await client.create_session():
            print("❌ Session creation failed - cannot continue with other tests")
            return False
        
        print()
        
        # Test 3: Chat Messages with different intents
        test_messages = [
            ("help", "help"),
            ("list all jobs", "list_jobs"),
            ("trigger the frontend build", "trigger_build"),
            ("what's the status of my build?", "build_status"),
            ("show me the log for build #123", "build_log"),
            ("why did the deploy job fail?", "build_analysis")
        ]
        
        for message, expected_intent in test_messages:
            await client.test_chat_message(message, expected_intent)
            print()
        
        # Test 4: Session State
        await client.get_session_state()
        print()
        
        # Test 5: Metrics
        await client.test_metrics()
        print()
        
        # Test 6: Cleanup
        await client.cleanup_session()
        
    print("=" * 60)
    print("🎉 All tests completed!")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    
    print(f"Testing AI Agent Service at: {BASE_URL}")
    
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        sys.exit(1)