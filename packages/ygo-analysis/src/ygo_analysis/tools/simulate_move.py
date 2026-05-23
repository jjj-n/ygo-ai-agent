"""Tool: simulate_move - Simulate a move without modifying actual game state."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance
from ygo_analysis.tools.find_best_line import evaluate_position_sync, _extract_all_moves


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
        depth: 推演深度 (1=只看直接结果, 2+=看多步展开)

    Returns:
        模拟结果，包含模拟后的状态和深度推演结果
    """
    clone = None
    try:
        instance = GameInstance.get(game_id)

        # Get state before simulation
        current_state = instance.get_state(player_pov=player)
        current_score = evaluate_position_sync(current_state, player)

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
        new_score = evaluate_position_sync(new_state, player)

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
            "score_before": round(current_score, 2),
            "score_after": round(new_score, 2),
            "score_change": round(new_score - current_score, 2),
            "depth": depth,
        }

        # If depth > 1, simulate further moves using beam search
        if depth > 1:
            best_continuation = _simulate_deeper(clone, player, depth - 1)
            if best_continuation:
                simulation_result["best_continuation"] = best_continuation

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


def _simulate_deeper(instance: GameInstance, player: int, remaining_depth: int) -> dict | None:
    """Simulate deeper moves from the current state using limited beam search.

    Args:
        instance: The cloned game instance
        player: The player to evaluate for
        remaining_depth: How many more depths to search

    Returns:
        Best continuation path with scores, or None if no moves available
    """
    try:
        legal_moves = instance.get_legal_moves()
        if not legal_moves:
            return None

        all_moves = _extract_all_moves(legal_moves)
        if not all_moves:
            return None

        # Try each move and find the best one
        best_move = None
        best_score = -1
        best_state = None

        # Limit to top 3 moves to keep simulation fast
        for move in all_moves[:3]:
            try:
                sub_clone = instance.clone()
                result = sub_clone.execute_move(move)

                if result.get("success", False) or result.get("ok", False):
                    sub_state = sub_clone.get_state(player_pov=player)
                    sub_score = evaluate_position_sync(sub_state, player)

                    if sub_score > best_score:
                        best_score = sub_score
                        best_move = move
                        best_state = sub_state

                sub_clone.close()
            except Exception:
                continue

        if best_move is None:
            return None

        continuation = {
            "move": best_move,
            "score": round(best_score, 2),
            "depth": remaining_depth,
        }

        # Recursively simulate deeper if needed
        if remaining_depth > 1 and best_state is not None:
            # Create a new clone from the best state to continue
            try:
                deeper_clone = instance.clone()
                deeper_clone.execute_move(best_move)
                deeper_result = _simulate_deeper(deeper_clone, player, remaining_depth - 1)
                deeper_clone.close()

                if deeper_result:
                    continuation["next"] = deeper_result
            except Exception:
                pass

        return continuation

    except Exception:
        return None
