#!/usr/bin/env python3
"""
Test MCP connection through Docker container networking
"""

import asyncio
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_docker_connection():
    """Test MCP connection using Docker service name"""
    try:
        logger.info("Testing MCP connection to http://mcp-server:8010/mcp")
        
        # Connect to MCP server using Docker service name
        async with streamablehttp_client("http://mcp-server:8010/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            logger.info("Successfully connected to MCP server via Docker network")
            
            # Create a session using the client streams
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("Created ClientSession")
                
                # Initialize the connection
                await session.initialize()
                logger.info("Session initialized")
                
                # List available tools
                tools = await session.list_tools()
                logger.info(f"Available tools: {[tool.name for tool in tools.tools]}")
                logger.info(f"Total tools available: {len(tools.tools)}")
                
                return True
                
    except Exception as e:
        logger.error(f"MCP Docker connection test failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_mcp_docker_connection())
    if result:
        print("✅ MCP Docker connection test PASSED")
    else:
        print("❌ MCP Docker connection test FAILED")