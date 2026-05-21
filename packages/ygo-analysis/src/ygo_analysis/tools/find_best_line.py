"""Tool: find_best_line - Find the best move sequence."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance


async def find_best_line(
    game_id: str,
    player: int = 1,
    max_depth: int = 3,
    top_k: int = 3,
) -> dict:
    """自动搜索 N 步内的最优展开路线。

    返回 Top-K 路径及评估分数。
    用于帮助 LLM 找到最佳操作序列。

    Args:
        game_id: 游戏实例 ID
        player: 评估哪个玩家 (1 或 2)
        max_depth: 最大推演步数 (默认 3)
        top_k: 返回前 K 条路径 (默认 3)

    Returns:
        最优展开路线列表
    """
    try:
        instance = GameInstance.get(game_id)

        # Get current state and legal moves
        current_state = instance.get_state(player_pov=player)
        legal_moves = instance.get_legal_moves()

        if not legal_moves:
            return {
                "success": True,
                "lines": [],
                "message": "No legal moves available",
            }

        # For each legal move, evaluate the resulting position
        evaluated_moves = []

        for i, move_info in enumerate(legal_moves[:10]):  # Limit to first 10 moves
            # Create a move from the legal move info
            move_type = move_info.get("type", "unknown")

            # Evaluate the position after this move
            # In a full implementation, we would:
            # 1. Clone the game state
            # 2. Execute the move
            # 3. Evaluate the resulting position
            # 4. If depth > 1, continue searching

            # For now, use a simple heuristic based on the move type
            score = 50.0  # Base score

            # Simple heuristics
            if move_type == "summon":
                score += 5  # Summoning is generally good
            elif move_type == "special_summon":
                score += 8  # Special summon is better
            elif move_type == "activate_effect":
                score += 3  # Effects are situationally good
            elif move_type == "set_trap":
                score += 2  # Setting traps is defensive
            elif move_type == "phase_end":
                score -= 2  # Ending turn is less optimal

            evaluated_moves.append({
                "move": move_info,
                "score": score,
                "depth": 1,
            })

        # Sort by score (descending)
        evaluated_moves.sort(key=lambda x: x["score"], reverse=True)

        # Return top-k
        top_lines = evaluated_moves[:top_k]

        return {
            "success": True,
            "lines": top_lines,
            "current_state": current_state,
            "total_legal_moves": len(legal_moves),
            "searched_moves": min(len(legal_moves), 10),
            "max_depth": max_depth,
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
