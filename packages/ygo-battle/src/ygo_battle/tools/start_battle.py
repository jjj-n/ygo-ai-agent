"""Tool: start_battle - Start a new battle."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance


async def start_battle(
    deck_p1: list[int],
    deck_p2: list[int],
    ai_mode: str = "aggressive",
    seed: Optional[int] = None,
) -> dict:
    """创建一个新的对局。

    初始化游戏引擎，设置双方卡组，开始对战。

    Args:
        deck_p1: 玩家1的卡组 (卡牌ID列表)
        deck_p2: 玩家2的卡组 (卡牌ID列表)
        ai_mode: AI 策略模式 (aggressive/control/combo)
        seed: 随机种子 (不填则随机)

    Returns:
        对局信息，包含 game_id
    """
    valid_modes = ["aggressive", "control", "combo"]
    if ai_mode not in valid_modes:
        return {
            "success": False,
            "error": f"Invalid AI mode: {ai_mode}. Valid modes: {', '.join(valid_modes)}",
        }

    if len(deck_p1) < 40 or len(deck_p2) < 40:
        return {
            "success": False,
            "error": "Deck must contain at least 40 cards",
        }

    try:
        instance = GameInstance.create(
            deck_p1=deck_p1,
            deck_p2=deck_p2,
            seed=seed or 0,
        )

        return {
            "success": True,
            "game_id": instance.game_id,
            "ai_mode": ai_mode,
            "message": f"Battle started. Game ID: {instance.game_id}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
