"""YGO Unified MCP Server — all tools in one process.

Consolidates ygo-state, ygo-action, ygo-analysis, ygo-battle into
a single MCP server so tools share the same GameInstance registry.
"""

from mcp.server.fastmcp import FastMCP

# Import tools from existing packages
from ygo_state.tools.get_game_state import get_game_state
from ygo_state.tools.get_legal_moves import get_legal_moves
from ygo_state.tools.get_zone_detail import get_zone_detail
from ygo_state.tools.get_card_info import get_card_info

from ygo_action.tools.execute_move import execute_move
from ygo_action.tools.respond_chain import respond_chain
from ygo_action.tools.declare_attack import declare_attack

from ygo_analysis.tools.simulate_move import simulate_move
from ygo_analysis.tools.evaluate_position import evaluate_position
from ygo_analysis.tools.find_best_line import find_best_line
from ygo_analysis.tools.explain_line import explain_line

from ygo_battle.tools.start_battle import start_battle
from ygo_battle.tools.ai_decide import ai_decide
from ygo_battle.tools.auto_play import auto_play
from ygo_battle.tools.get_battle_log import get_battle_log

# Import teaching tools
from ygo_mcp.tools.teaching import explain_card, explain_move, quiz_position, check_answer

# Import replay tools
from ygo_mcp.tools.replay import (
    save_replay,
    load_replay,
    get_turn_state,
    analyze_mistakes,
    suggest_improvement,
)

# Import prompts
from ygo_mcp.prompts import (
    ANALYSIS_PROMPT,
    BATTLE_PROMPT,
    TEACHING_PROMPT,
    AGENT_PROFILES,
)

mcp = FastMCP("ygo")

# State tools
mcp.tool()(get_game_state)
mcp.tool()(get_legal_moves)
mcp.tool()(get_zone_detail)
mcp.tool()(get_card_info)

# Action tools
mcp.tool()(execute_move)
mcp.tool()(respond_chain)
mcp.tool()(declare_attack)

# Analysis tools
mcp.tool()(simulate_move)
mcp.tool()(evaluate_position)
mcp.tool()(find_best_line)
mcp.tool()(explain_line)

# Battle tools
mcp.tool()(start_battle)
mcp.tool()(ai_decide)
mcp.tool()(auto_play)
mcp.tool()(get_battle_log)

# Teaching tools
mcp.tool()(explain_card)
mcp.tool()(explain_move)
mcp.tool()(quiz_position)
mcp.tool()(check_answer)

# Replay tools
mcp.tool()(save_replay)
mcp.tool()(load_replay)
mcp.tool()(get_turn_state)
mcp.tool()(analyze_mistakes)
mcp.tool()(suggest_improvement)


# Prompts
@mcp.prompt()
def ygo_analysis_prompt() -> str:
    """游戏王局面分析专家提示词"""
    return ANALYSIS_PROMPT


@mcp.prompt()
def ygo_battle_prompt(strategy: str = "aggressive") -> str:
    """游戏王对战 Agent 提示词"""
    profile = AGENT_PROFILES.get(strategy, AGENT_PROFILES["aggressive"])
    return BATTLE_PROMPT.format(strategy=profile["strategy"], prompt=profile["prompt"])


@mcp.prompt()
def ygo_teaching_prompt() -> str:
    """游戏王教学 Agent 提示词"""
    return TEACHING_PROMPT


if __name__ == "__main__":
    mcp.run()
