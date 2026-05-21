"""YGO State MCP Server - Main entry point.

This MCP Server provides tools for querying game state,
designed for LLM-based game analysis.
"""

from mcp.server.fastmcp import FastMCP

from .tools import get_game_state, get_legal_moves, get_zone_detail, get_card_info

# Create MCP Server
mcp = FastMCP("ygo-state")

# Register tools
mcp.tool()(get_game_state)
mcp.tool()(get_legal_moves)
mcp.tool()(get_zone_detail)
mcp.tool()(get_card_info)


if __name__ == "__main__":
    mcp.run()
