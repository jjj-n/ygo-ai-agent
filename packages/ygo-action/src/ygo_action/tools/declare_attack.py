"""Tool: declare_attack - Declare an attack."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance, Move, MoveType, Zone


async def declare_attack(
    game_id: str,
    attacker_idx: int,
    target_idx: Optional[int] = None,
) -> dict:
    """宣言攻击。

    在战斗阶段，使用此工具宣言攻击。

    Args:
        game_id: 游戏实例 ID
        attacker_idx: 攻击怪兽的位置索引 (0-4)
        target_idx: 目标怪兽的位置索引 (0-4)。不填则为直接攻击。

    Returns:
        攻击宣言结果
    """
    try:
        instance = GameInstance.get(game_id)

        # Create attack move
        move = Move(
            move_type=MoveType.ATTACK,
            player=1,  # Will be determined by engine
            source_zone=Zone.MONSTER,
            source_idx=attacker_idx,
            target_zone=Zone.MONSTER if target_idx is not None else None,
            target_idx=target_idx,
        )

        result = instance.do_move(move)

        return {
            "success": result.success,
            "events": [
                {
                    "type": e.event_type,
                    "description": e.description,
                    "player": e.player,
                }
                for e in result.events
            ],
            "state": result.new_state.to_llm_dict() if result.new_state else None,
            "error": result.error,
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
