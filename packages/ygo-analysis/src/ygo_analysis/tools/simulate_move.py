"""Tool: simulate_move - Simulate a move without modifying actual game state."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance


async def simulate_move(
    game_id: str,
    move_type: str,
    player: int,
    source_zone: Optional[str] = None,
    source_idx: Optional[int] = None,
    target_zone: Optional[str] = None,
    target_idx: Optional[int] = None,
    materials: Optional[list[int]] = None,
    depth: int = 1,
) -> dict:
    """在沙盒中模拟执行一个操作，返回模拟后状态。

    不修改实际游戏状态，用于推演展开路线。
    可以指定推演深度来查看多步后的结果。

    Args:
        game_id: 游戏实例 ID
        move_type: 操作类型
        player: 执行操作的玩家 (1 或 2)
        source_zone: 来源区域
        source_idx: 来源位置索引
        target_zone: 目标区域
        target_idx: 目标位置索引
        materials: 素材列表
        depth: 推演深度 (1=只看直接结果, 2=看对手可能的应对)

    Returns:
        模拟结果，包含模拟后的状态
    """
    clone = None
    try:
        instance = GameInstance.get(game_id)

        # Get state before simulation
        current_state = instance.get_state(player_pov=player)

        # Build move dict
        move = {"type": move_type, "player": player}
        if source_zone:
            move["source"] = source_zone
        if source_idx is not None:
            move["source_idx"] = source_idx
        if target_zone:
            move["target"] = target_zone
        if target_idx is not None:
            move["target_idx"] = target_idx
        if materials:
            move["materials"] = materials

        # Create sandboxed clone
        clone = instance.clone()

        # Execute on clone (does not affect real instance)
        result = clone.do_move_raw(move)

        if not result.get("ok"):
            return {
                "success": False,
                "error": result.get("reason", "Move execution failed"),
                "current_state": current_state,
            }

        # Get new state from clone
        new_state = clone.get_state(player_pov=player)

        simulation_result = {
            "success": True,
            "move": {
                "type": move_type,
                "player": player,
                "source": source_zone,
                "target": target_zone,
            },
            "state_before": current_state,
            "state_after": new_state,
            "depth": depth,
        }

        # TODO: If depth > 1, simulate opponent responses on a sub-clone

        return simulation_result

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
    finally:
        if clone is not None:
            clone.close()
