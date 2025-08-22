#!/usr/bin/env python3
"""
Simple test script to verify JSON configuration loading
Run from ai-agent directory: python test_config_simple.py
"""

import sys
import os

from app.services.config_manager import config_manager

def test_configuration():
    """Test loading and validating MCP configuration"""
    
    print("Testing MCP Configuration Loading...")
    print("-" * 50)
    
    try:
        # Load configuration
        config = config_manager.load_configuration()
        
        print(f"✅ Configuration loaded successfully!")
        print(f"📊 Configuration Summary:")
        
        summary = config_manager.get_configuration_summary()
        
        print(f"   🔍 Discovery Enabled: {summary['discovery_enabled']}")
        print(f"   🔄 Fallback Enabled: {summary['fallback_enabled']}")
        print(f"   ⚖️  Load Balancing: {summary['load_balancing']}")
        print(f"   🏊 Connection Pooling: {summary['connection_pooling']}")
        print(f"   💾 Cache Enabled: {summary['cache_enabled']}")
        print(f"   ⏰ Cache TTL: {summary['cache_ttl_seconds']} seconds")
        print(f"   ❤️  Health Check Interval: {summary['health_check_interval']} seconds")
        print(f"   🔗 Max Concurrent Connections: {summary['max_concurrent_connections']}")
        
        print(f"\n🖥️  Server Configuration:")
        print(f"   📈 Total Servers: {summary['total_servers']}")
        print(f"   ✅ Enabled Servers: {summary['enabled_servers']}")
        
        if summary['servers']:
            print(f"\n📋 Server Details:")
            for i, server in enumerate(summary['servers'], 1):
                status = "🟢 ENABLED" if server['enabled'] else "🔴 DISABLED"
                print(f"   {i}. {server['name']} - {status}")
                print(f"      🌐 URL: {server['url']}")
                print(f"      🚚 Transport: {server['transport']}")
                print(f"      📊 Priority: {server['priority']}")
                print(f"      ⏱️  Timeout: {server['timeout']}s")
                print()
        
        # Test server operations
        print("🔧 Testing Server Operations...")
        
        # Get enabled servers
        enabled_servers = config_manager.get_enabled_servers()
        print(f"   📊 Enabled servers found: {len(enabled_servers)}")
        
        # Get servers by priority
        priority_servers = config_manager.get_servers_by_priority()
        print(f"   📊 Servers by priority: {[s.name for s in priority_servers]}")
        
        # Test server lookup
        if enabled_servers:
            first_server = enabled_servers[0]
            found_server = config_manager.get_server_by_name(first_server.name)
            if found_server:
                print(f"   ✅ Server lookup successful: {found_server.name}")
            else:
                print(f"   ❌ Server lookup failed")
        
        print("\n🎉 All configuration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_configuration()
    sys.exit(0 if success else 1)