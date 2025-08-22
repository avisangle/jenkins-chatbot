#!/usr/bin/env python3
"""
Test script for Google Gemini API integration
Run this to verify your Gemini API key and basic functionality
"""

import os
import asyncio
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.ai_service import AIService

async def test_gemini_integration():
    """Test basic Gemini API functionality"""
    
    print("🤖 Testing Google Gemini API Integration...")
    print("=" * 50)
    
    # Check API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        print("Please set your Google Gemini API key in the .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Initialize AI service
        ai_service = AIService()
        print("✅ AI Service initialized successfully")
        
        # Test health check
        print("\n🔍 Testing health check...")
        is_healthy = await ai_service.health_check()
        if is_healthy:
            print("✅ Health check passed")
        else:
            print("❌ Health check failed")
            return False
        
        # Test basic message processing
        print("\n💬 Testing message processing...")
        
        # Mock user context for testing
        user_context = {
            "user_id": "test_user",
            "session_id": "test_session",
            "permissions": ["Job.READ", "Job.BUILD"],
            "context": {
                "current_job": "test-job",
                "workspace": "/tmp/test"
            }
        }
        
        test_message = "What can you help me with?"
        
        response = await ai_service.process_message(test_message, user_context)
        
        print(f"✅ Message processed successfully")
        print(f"📝 Response: {response.response[:100]}...")
        print(f"🎯 Intent detected: {response.intent_detected}")
        print(f"⏱️  Response time: {response.response_time_ms}ms")
        print(f"📊 Confidence: {response.confidence_score}")
        
        # Test another message type
        print("\n🔧 Testing build trigger intent...")
        build_message = "trigger the frontend build"
        
        build_response = await ai_service.process_message(build_message, user_context)
        print(f"✅ Build message processed")
        print(f"📝 Response: {build_response.response[:100]}...")
        print(f"🎯 Intent detected: {build_response.intent_detected}")
        
        if build_response.actions:
            print(f"⚡ Actions planned: {len(build_response.actions)}")
            for i, action in enumerate(build_response.actions):
                print(f"   {i+1}. {action.type}: {action.description}")
        
        print("\n✅ All tests passed! Gemini integration is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return False

def check_environment():
    """Check if all required environment variables are set"""
    print("🔍 Checking environment setup...")
    
    required_vars = [
        'GEMINI_API_KEY',
        'GEMINI_MODEL'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask API key for security
            if 'API_KEY' in var:
                display_value = f"{value[:10]}...{value[-4:]}"
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file and ensure all required variables are set.")
        return False
    
    return True

async def main():
    """Main test function"""
    print("🚀 Jenkins AI Chatbot - Gemini Integration Test")
    print("=" * 60)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    print()
    
    # Test Gemini integration
    success = await test_gemini_integration()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests completed successfully!")
        print("Your Gemini integration is ready for use.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())