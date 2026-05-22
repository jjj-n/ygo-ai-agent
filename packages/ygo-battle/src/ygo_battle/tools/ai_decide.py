"""Tool: ai_decide - AI decides the next move."""

from __future__ import annotations
from ygo_engine_bridge import GameInstance
from .auto_play import _pick_move_aggressive, _pick_move_control, _STRATEGIES


AI_STRATEGY_INFO = {
    "aggressive": "优先展开，快速削减对手 LP。召唤优先于设置陷阱。",
    "control": "优先互动，积累资源优势。设置陷阱优先于召唤。",
    "combo": "寻找 OTK/FTK 组合。优先特殊召唤展开。",
}


async def ai_decide(
    game_id: str,
    strategy: str = "aggressive",
    player: int = 1,
) -> dict:
    """AI 决策当前操作。

    根据指定的策略，分析当前局面并选择最优操作。

    Args:
        game_id: 游戏实例 ID
        strategy: AI 策略 (aggressive/control/combo)
        player: AI 控制的玩家 (1 或 2)

    Returns:
        AI 决策结果，包含推荐操作和分析
    """
    if strategy not in _STRATEGIES:
        return {
            "success": False,
            "error": f"Invalid strategy: {strategy}. Valid: {', '.join(_STRATEGIES.keys())}",
        }

    try:
        instance = GameInstance.get(game_id)

        state = instance.get_state(player_pov=player)
        legal_moves = instance.get_legal_moves()

        pick_fn = _STRATEGIES[strategy]
        recommended = pick_fn(legal_moves, player) if legal_moves else None

        # Build analysis
        if not legal_moves:
            analysis = "没有可用的操作"
        elif recommended:
            move_type = recommended.get("type", "unknown")
            analysis = f"策略 [{strategy}] 推荐操作: {move_type}"
        else:
            analysis = "无法确定操作"

        return {
            "success": True,
            "strategy": strategy,
            "strategy_description": AI_STRATEGY_INFO.get(strategy, ""),
            "recommended_move": recommended,
            "analysis": analysis,
            "legal_moves_count": len(legal_moves),
            "state": state,
        }

    except KeyError:
        return {
            "success": False,
            "error": f"Game instance not found: {game_id}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
