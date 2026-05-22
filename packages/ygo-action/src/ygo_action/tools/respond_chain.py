"""Tool: respond_chain - Respond to a chain prompt."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance


async def respond_chain(
    game_id: str,
    action: str,
    card_idx: Optional[int] = None,
) -> dict:
    """响应连锁提示。

    当引擎要求玩家决定是否连锁时，使用此工具响应。

    Args:
        game_id: 游戏实例 ID
        action: 响应动作 (activate=发动, negate=无效, pass=跳过)
        card_idx: 卡牌索引 (activate/negate 时需要)

    Returns:
        连锁响应结果
    """
    valid_actions = ["activate", "negate", "pass"]
    if action not in valid_actions:
        return {
            "success": False,
            "error": f"Invalid action: {action}. Valid actions: {', '.join(valid_actions)}",
        }

    try:
        instance = GameInstance.get(game_id)
        result = instance.respond_chain(action, card_idx)

        if not result.success:
            return {
                "success": False,
                "error": result.error or "Chain response failed",
            }

        return {
            "success": True,
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
