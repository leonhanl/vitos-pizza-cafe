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

        logger.info(f"MCP tools initialized: {len(tools)} tools available")
        return tools

    except Exception as e:
        logger.error(f"Error initializing MCP tools: {e}")
        return []
