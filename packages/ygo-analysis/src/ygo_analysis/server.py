"""YGO Analysis MCP Server - Main entry point.

This MCP Server provides tools for game simulation and evaluation,
designed for LLM-based strategic analysis.
"""

from mcp.server.fastmcp import FastMCP

from .tools import simulate_move, evaluate_position, find_best_line

# Create MCP Server
mcp = FastMCP("ygo-analysis")

# Register tools
mcp.tool()(simulate_move)
mcp.tool()(evaluate_position)
mcp.tool()(find_best_line)


if __name__ == "__main__":
    mcp.run()
