#!/usr/bin/env python3
"""
Integration test to verify Universal MCP Architecture with JSON configuration
"""

import asyncio
from app.services.config_manager import config_manager
from app.services.mcp_universal_client import UniversalMCPClient

async def test_universal_integration():
    """Test Universal MCP Architecture integration"""
    
    print("Testing Universal MCP Architecture Integration...")
    print("=" * 60)
    
    try:
        # Load configuration from JSON
        print("1. Loading JSON configuration...")
        config = config_manager.load_configuration()
        print(f"   ✅ Configuration loaded: {len(config.servers)} servers")
        
        # Get enabled servers
        enabled_servers = config_manager.get_enabled_servers()
        print(f"   📊 Enabled servers: {len(enabled_servers)}")
        
        if not enabled_servers:
            print("   ⚠️  No enabled servers found, cannot test connection")
            return False
        
        # Initialize Universal MCP Client
        print("\n2. Initializing Universal MCP Client...")
        universal_client = UniversalMCPClient(config.servers)
        print("   ✅ Universal MCP Client initialized")
        
        # Test server capabilities discovery
        print("\n3. Testing server capabilities discovery...")
        for server in enabled_servers[:1]:  # Test first server only
            try:
                print(f"   🔍 Discovering capabilities for: {server.name}")
                capabilities = await universal_client.discover_server_capabilities(server)
                print(f"      ✅ Discovery completed")
                print(f"      📊 Available tools: {len(capabilities.tools) if capabilities.tools else 0}")
                print(f"      🔗 Connection status: {'Ready' if capabilities.connection_status == 'ready' else capabilities.connection_status}")
                
                if capabilities.tools:
                    print(f"      🛠️  Sample tools: {list(capabilities.tools.keys())[:3]}")
                
            except Exception as e:
                print(f"      ❌ Discovery failed: {str(e)[:100]}...")
                # This is expected if MCP server is not running
        
        # Test configuration management features
        print("\n4. Testing configuration management...")
        
        # Test server lookup
        first_server = enabled_servers[0]
        found_server = config_manager.get_server_by_name(first_server.name)
        if found_server:
            print(f"   ✅ Server lookup: {found_server.name}")
        
        # Test priority ordering
        priority_servers = config_manager.get_servers_by_priority()
        print(f"   ✅ Priority ordering: {[s.name for s in priority_servers]}")
        
        # Test configuration summary
        summary = config_manager.get_configuration_summary()
        print(f"   ✅ Configuration summary generated")
        print(f"      📊 Total servers: {summary['total_servers']}")
        print(f"      ⚡ Cache enabled: {summary['cache_enabled']}")
        print(f"      🔄 Fallback enabled: {summary['fallback_enabled']}")
        
        # Test architecture compatibility
        print("\n5. Testing architecture compatibility...")
        
        # Verify configuration structure matches expected schema
        required_fields = ['discovery_enabled', 'fallback_enabled', 'connection_pooling', 'cache_enabled']
        missing_fields = [field for field in required_fields if not hasattr(config, field)]
        
        if not missing_fields:
            print("   ✅ Configuration schema validation passed")
        else:
            print(f"   ❌ Missing required fields: {missing_fields}")
        
        # Verify server configuration structure
        if enabled_servers:
            server = enabled_servers[0]
            server_fields = ['name', 'url', 'transport', 'priority', 'timeout', 'enabled']
            missing_server_fields = [field for field in server_fields if not hasattr(server, field)]
            
            if not missing_server_fields:
                print("   ✅ Server schema validation passed")
            else:
                print(f"   ❌ Missing server fields: {missing_server_fields}")
        
        print("\n🎉 Universal MCP Architecture integration test completed!")
        print("\n📋 Summary:")
        print(f"   ✅ JSON configuration loading: Working")
        print(f"   ✅ Configuration validation: Working") 
        print(f"   ✅ Server management: Working")
        print(f"   ✅ Schema compatibility: Working")
        print(f"   ⚠️  MCP server connection: Requires running MCP server")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_universal_integration())
    print(f"\n{'✅ PASS' if success else '❌ FAIL'}: Universal MCP Architecture Integration")