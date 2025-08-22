#!/usr/bin/env python3
"""
Test MCP enhancement in isolation to debug why AI service isn't getting Jenkins data
"""

import asyncio
import sys
import os
sys.path.append('/app')

from app.services.mcp_service import MCPService
from app.config import settings

async def test_mcp_enhancement():
    """Test MCP enhancement for job listing query"""
    
    print("🧪 Testing MCP Enhancement in Isolation")
    print("="*60)
    
    # Initialize MCP service
    mcp_service = MCPService()
    
    # Test case: "List jenkins job" query
    user_query = "List jenkins job"
    ai_response = "I can help you list Jenkins jobs. Here's how to access them..."
    jenkins_context = {
        "jenkins_url": "http://12.0.0.85:8080",
        "user_permissions": ["Job.READ", "Job.BUILD"]
    }
    
    print(f"🔤 User Query: {user_query}")
    print(f"🤖 AI Response: {ai_response[:100]}...")
    print(f"⚙️  Context: {jenkins_context}")
    print()
    
    try:
        print("🚀 Calling enhance_ai_response()...")
        enhanced = await mcp_service.enhance_ai_response(user_query, ai_response, jenkins_context)
        
        if enhanced:
            print("✅ Enhancement succeeded!")
            print(f"📝 Enhanced Response: {enhanced.get('enhanced_response', 'No enhanced response')[:200]}...")
            print(f"📊 MCP Data Included: {enhanced.get('mcp_data_included', False)}")
            print(f"🔧 Enhancement Details: {enhanced.get('enhancement_details', {})}")
        else:
            print("❌ Enhancement returned None")
            
    except Exception as e:
        print(f"❌ Enhancement failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_enhancement())