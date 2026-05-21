"""Tool: get_battle_log - Get battle log for a game."""

from __future__ import annotations
from ygo_engine_bridge import GameInstance


async def get_battle_log(game_id: str) -> dict:
    """获取对战日志。

    返回对局的完整操作记录，用于复盘分析。

    Args:
        game_id: 游戏实例 ID

    Returns:
        对战日志
    """
    try:
        instance = GameInstance.get(game_id)

        # Get current state
        state = instance.get_state()

        # In a full implementation, this would return the complete
        # move history stored in the game instance
        # For now, return the current state as a snapshot

        return {
            "success": True,
            "game_id": game_id,
            "current_state": state,
            "is_game_over": state.get("is_game_over", False),
            "winner": state.get("winner", -1),
            "log": [
                {
                    "type": "snapshot",
                    "description": "Current game state snapshot",
                    "state": state,
                }
            ],
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
