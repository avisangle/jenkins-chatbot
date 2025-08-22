#!/usr/bin/env python3
"""
Test MCP enhancement with detailed output to see what's being returned
"""

import asyncio
import sys
import os
sys.path.append('/app')

from app.services.mcp_service import MCPService
from app.config import settings

async def test_mcp_enhancement_detailed():
    """Test MCP enhancement for job listing query with full output"""
    
    print("🧪 Testing MCP Enhancement - DETAILED OUTPUT")
    print("="*70)
    
    # Initialize MCP service
    mcp_service = MCPService()
    
    # Test case: "List jenkins job" query
    user_query = "List jenkins job"
    ai_response = "I can help you list Jenkins jobs."
    jenkins_context = {
        "jenkins_url": "http://12.0.0.85:8080",
        "user_permissions": ["Job.READ", "Job.BUILD"]
    }
    
    try:
        enhanced = await mcp_service.enhance_ai_response(user_query, ai_response, jenkins_context)
        
        if enhanced:
            print("✅ ENHANCEMENT RESULT:")
            print("-" * 50)
            
            # Print full enhanced response
            enhanced_response = enhanced.get('enhanced_response', '')
            print(f"📝 FULL Enhanced Response:")
            print(enhanced_response)
            print("-" * 50)
            
            print(f"📊 MCP Data Included: {enhanced.get('mcp_data_included', False)}")
            print(f"🔧 Enhancement Details: {enhanced.get('enhancement_details', {})}")
            
            # Check if actual job data is included
            if 'C2M-DEMO-JENKINS' in enhanced_response:
                print("✅ Found actual Jenkins job data!")
            else:
                print("❌ No actual Jenkins job data found in response")
                print("🔍 Checking what keywords are present:")
                keywords = ['job', 'jenkins', 'build', 'server', 'C2M', 'Demo']
                for keyword in keywords:
                    if keyword.lower() in enhanced_response.lower():
                        print(f"  - Found: '{keyword}'")
        else:
            print("❌ Enhancement returned None")
            
    except Exception as e:
        print(f"❌ Enhancement failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_enhancement_detailed())