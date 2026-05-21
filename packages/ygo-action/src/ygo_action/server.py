"""YGO Action MCP Server - Main entry point.

This MCP Server provides tools for executing game moves,
designed for LLM-based game control.
"""

from mcp.server.fastmcp import FastMCP

from .tools import execute_move, respond_chain, declare_attack

# Create MCP Server
mcp = FastMCP("ygo-action")

# Register tools
mcp.tool()(execute_move)
mcp.tool()(respond_chain)
mcp.tool()(declare_attack)


if __name__ == "__main__":
    mcp.run()
