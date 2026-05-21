"""YGO Battle MCP Server - Main entry point.

This MCP Server provides tools for auto-battling,
designed for LLM-based game automation.
"""

from mcp.server.fastmcp import FastMCP

from .tools import start_battle, ai_decide, auto_play, get_battle_log

# Create MCP Server
mcp = FastMCP("ygo-battle")

# Register tools
mcp.tool()(start_battle)
mcp.tool()(ai_decide)
mcp.tool()(auto_play)
mcp.tool()(get_battle_log)


if __name__ == "__main__":
    mcp.run()
