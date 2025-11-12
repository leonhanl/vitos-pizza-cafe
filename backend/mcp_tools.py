"""MCP tool integration for Vito's Pizza Cafe application."""

import logging
from typing import List
from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import Config

logger = logging.getLogger(__name__)


async def get_mcp_tools() -> List:
    """Get MCP tools from configured servers.

    Returns:
        list: MCP tools from all configured servers
    """
    if not Config.MCP_SERVERS:
        logger.info("No MCP servers configured, returning empty tool list")
        return []

    try:
        # Initialize MCP client with configured servers
        client = MultiServerMCPClient(Config.MCP_SERVERS)

        # Get tools asynchronously
        tools = await client.get_tools()

        # Sanitize tool names to comply with OpenAI-compatible API requirements
        # Pattern requirement: ^[a-zA-Z0-9_-]{1,128}$
        # Replace colons with underscores (e.g., "None:maps_geo" -> "None_maps_geo")
        # Normally there's no need to do that, but there's a bug in the current pan-mcp-relay implementation
        for tool in tools:
            if ':' in tool.name:
                original_name = tool.name
                tool.name = tool.name.replace(':', '_')
                logger.info(f"Sanitized tool name: {original_name} -> {tool.name}")

        logger.info(f"MCP tools initialized: {len(tools)} tools available")
        return tools

    except Exception as e:
        logger.error(f"Error initializing MCP tools: {e}")
        return []
