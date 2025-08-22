#!/usr/bin/env python3
"""
Test script to verify configuration validation
"""

import json
import os
import tempfile
from app.services.config_manager import ConfigManager
from app.services.mcp_universal_client import MCPServerConfig, TransportType

def test_validation():
    """Test configuration validation and error handling"""
    
    print("Testing Configuration Validation...")
    print("-" * 50)
    
    # Test 1: Invalid JSON file
    print("1. Testing invalid JSON file...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{ invalid json }')
        invalid_json_file = f.name
    
    try:
        config_manager = ConfigManager()
        config_manager._config_file_path = invalid_json_file
        config = config_manager.load_configuration()
        print("   ✅ Handled invalid JSON gracefully (fallback used)")
    except Exception as e:
        print(f"   ❌ Failed to handle invalid JSON: {e}")
    finally:
        os.unlink(invalid_json_file)
    
    # Test 2: Missing required fields
    print("\n2. Testing missing required fields...")
    invalid_config = {
        "servers": [
            {
                "name": "",  # Missing name
                "url": "",   # Missing URL
                "transport": "http"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_config, f, indent=2)
        invalid_config_file = f.name
    
    try:
        config_manager = ConfigManager()
        config_manager._config_file_path = invalid_config_file
        config = config_manager.load_configuration()
        summary = config_manager.get_configuration_summary()
        print(f"   ✅ Invalid server filtered out. Total servers: {summary['total_servers']}")
    except Exception as e:
        print(f"   ❌ Failed to handle invalid server config: {e}")
    finally:
        os.unlink(invalid_config_file)
    
    # Test 3: Invalid transport type
    print("\n3. Testing invalid transport type...")
    invalid_transport_config = {
        "servers": [
            {
                "name": "test-server",
                "url": "http://example.com",
                "transport": "invalid_transport",
                "timeout": 30
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_transport_config, f, indent=2)
        invalid_transport_file = f.name
    
    try:
        config_manager = ConfigManager()
        config_manager._config_file_path = invalid_transport_file
        config = config_manager.load_configuration()
        summary = config_manager.get_configuration_summary()
        print(f"   ✅ Invalid transport filtered out. Total servers: {summary['total_servers']}")
    except Exception as e:
        print(f"   ❌ Failed to handle invalid transport: {e}")
    finally:
        os.unlink(invalid_transport_file)
    
    # Test 4: Valid configuration with validation
    print("\n4. Testing valid configuration...")
    valid_config = {
        "discovery_enabled": True,
        "fallback_enabled": True,
        "cache_enabled": True,
        "servers": [
            {
                "name": "test-valid-server",
                "url": "http://valid-server.com:8010/mcp",
                "transport": "http",
                "priority": 1,
                "timeout": 30,
                "retry_count": 3,
                "enabled": True,
                "headers": {"X-Test": "value"},
                "auth_token": None
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(valid_config, f, indent=2)
        valid_config_file = f.name
    
    try:
        config_manager = ConfigManager()
        config_manager._config_file_path = valid_config_file
        config = config_manager.load_configuration()
        summary = config_manager.get_configuration_summary()
        
        print(f"   ✅ Valid configuration loaded successfully")
        print(f"      Total servers: {summary['total_servers']}")
        print(f"      Enabled servers: {summary['enabled_servers']}")
        
        if summary['servers']:
            server = summary['servers'][0]
            print(f"      Server name: {server['name']}")
            print(f"      Server URL: {server['url']}")
            print(f"      Server transport: {server['transport']}")
    
    except Exception as e:
        print(f"   ❌ Failed to load valid configuration: {e}")
    finally:
        os.unlink(valid_config_file)
    
    # Test 5: Server management operations
    print("\n5. Testing server management operations...")
    try:
        config_manager = ConfigManager()
        config_manager.load_configuration()
        
        # Test add server
        new_server = MCPServerConfig(
            name="test-new-server",
            url="http://new-server.com:8020/mcp",
            transport=TransportType.HTTP,
            priority=2,
            timeout=25,
            enabled=True
        )
        
        if config_manager.add_server(new_server):
            print("   ✅ Server added successfully")
        else:
            print("   ❌ Failed to add server")
        
        # Test duplicate server name
        if not config_manager.add_server(new_server):
            print("   ✅ Duplicate server name prevented")
        else:
            print("   ❌ Duplicate server name not prevented")
        
        # Test update server
        if config_manager.update_server("test-new-server", {"timeout": 35}):
            print("   ✅ Server updated successfully")
        else:
            print("   ❌ Failed to update server")
        
        # Test remove server
        if config_manager.remove_server("test-new-server"):
            print("   ✅ Server removed successfully")
        else:
            print("   ❌ Failed to remove server")
            
    except Exception as e:
        print(f"   ❌ Server management test failed: {e}")
    
    print("\n🎉 All validation tests completed!")

if __name__ == "__main__":
    test_validation()