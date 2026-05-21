# YGO AI Agent

Yu-Gi-Oh! AI Agent system: Claude Code + MCP + ygopro-core.

## Architecture

Four-layer MCP plugin architecture:

- **Agent Layer**: Claude Code (ReAct loop)
- **MCP Tool Layer**: ygo-state, ygo-action, ygo-analysis, ygo-battle
- **Engine Bridge**: Python library wrapping ygopro-engine subprocess
- **Rule Engine**: ygopro-core (C++) via JSON stdin/stdout

## Key Principle

LLM thinks. Rule engine validates. MCP connects them.

## Project Structure

- `libs/ygopro-engine/` — C++ wrapper around ocgcore (JSON stdin/stdout)
- `libs/ygopro-core/` — edo9300/ygopro-core source (git submodule)
- `packages/ygo-engine-bridge/` — Python shared library for engine communication
- `packages/ygo-state/` — Phase 1: situation analysis MCP Server
- `packages/ygo-action/` — Phase 2: move execution MCP Server
- `packages/ygo-analysis/` — Phase 3: simulation & evaluation MCP Server
- `packages/ygo-battle/` — Phase 4: auto-battle MCP Server
- `data/` — card database (CDB), replays

## MCP Servers

Each server is a standalone Python process. Register in `.mcp.json`.

New feature = new MCP Server directory + register. Zero existing code changes.

## Running

```bash
# Build C++ engine
cd libs/ygopro-engine && cmake -B build && cmake --build build

# Run MCP server
python -m ygo_state.server
```
