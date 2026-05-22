"""Tool: execute_move - Execute a game move."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance


async def execute_move(
    game_id: str,
    move: dict,
) -> dict:
    """执行一个游戏操作。

    Args:
        game_id: 游戏实例 ID
        move: 操作字典，包含 type 字段和操作参数。格式:
            {"type": "summon", "index": 0}
            {"type": "sset", "index": 0}
            {"type": "place", "location": 8, "sequence": 0}
            {"type": "to_ep"}
            {"type": "activate", "index": 0}

    Returns:
        操作执行结果，包含 success、next_prompt 等信息
    """
    try:
        instance = GameInstance.get(game_id)
        response = instance.do_move_raw(move)

        if not response.get("ok"):
            return {
                "success": False,
                "error": response.get("error", "Move failed"),
            }

        data = response.get("data", {})
        next_moves = data.get("next_moves", [])
        game_over = data.get("game_over", False)

        result = {
            "success": True,
            "game_over": game_over,
        }

        if game_over:
            result["winner"] = data.get("winner", -1)

        # Describe what the engine is waiting for next
        if next_moves:
            prompt_type = next_moves[0].get("type", "unknown")
            prompt_player = next_moves[0].get("player", 0)
            result["next_prompt"] = {
                "type": prompt_type,
                "player": prompt_player + 1,  # 1-based
            }
            # Include chain info if it's a chain prompt
            if prompt_type == "select_chain":
                result["next_prompt"]["chain_count"] = next_moves[0].get("count", 0)
                result["next_prompt"]["chains"] = next_moves[0].get("chains", [])
        else:
            result["next_prompt"] = None

        return result

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
