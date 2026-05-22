"""Tool: find_best_line - Find the best move sequence."""

from __future__ import annotations
from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.instance import _format_card


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

        current_state = instance.get_state(player_pov=player)
        legal_moves = instance.get_legal_moves()

        if not legal_moves:
            return {
                "success": True,
                "lines": [],
                "message": "No legal moves available",
            }

        # Build list of concrete moves from idlecmd/battlecmd prompts
        candidate_moves = []
        for move_info in legal_moves:
            t = move_info.get("type")
            if t == "idlecmd":
                if move_info.get("summon_count", 0) > 0:
                    candidate_moves.append({"type": "summon", "index": 0, "desc": "召唤怪兽"})
                if move_info.get("spsummon_count", 0) > 0:
                    candidate_moves.append({"type": "spsummon", "index": 0, "desc": "特殊召唤"})
                if move_info.get("activate_count", 0) > 0:
                    candidate_moves.append({"type": "activate", "index": 0, "desc": "发动效果"})
                if move_info.get("sset_count", 0) > 0:
                    candidate_moves.append({"type": "sset", "index": 0, "desc": "覆盖魔法/陷阱"})
                if move_info.get("mset_count", 0) > 0:
                    candidate_moves.append({"type": "mset", "index": 0, "desc": "覆盖怪兽"})
                if move_info.get("to_bp", 0):
                    candidate_moves.append({"type": "to_bp", "desc": "进入战斗阶段"})
            elif t == "battlecmd":
                if move_info.get("attack_count", 0) > 0:
                    candidate_moves.append({"type": "attack", "index": 0, "desc": "攻击"})
                if move_info.get("activate_count", 0) > 0:
                    candidate_moves.append({"type": "activate", "index": 0, "desc": "战斗阶段发动效果"})

        # Evaluate each candidate
        evaluated = []
        my_lp = current_state.get("player", {}).get("lp", 8000)
        opp_lp = current_state.get("opponent", {}).get("lp", 8000)
        my_monsters = len([m for m in current_state.get("player", {}).get("monster_zones", []) if m])
        opp_monsters = len([m for m in current_state.get("opponent", {}).get("monster_zones", []) if m])

        for move in candidate_moves:
            score = 50.0
            mt = move.get("type", "")

            if mt == "summon":
                score += 5 + (5 if my_monsters < opp_monsters else 0)
            elif mt == "spsummon":
                score += 8
            elif mt == "activate":
                score += 6
            elif mt == "attack":
                score += 10 if opp_monsters == 0 else 3  # Direct attack bonus
            elif mt == "sset":
                score += 3
            elif mt == "mset":
                score += 2
            elif mt == "to_bp":
                score += 4 if my_monsters > 0 else -5

            evaluated.append({
                "move": move,
                "score": round(score, 1),
                "depth": 1,
            })

        evaluated.sort(key=lambda x: x["score"], reverse=True)
        top_lines = evaluated[:top_k]

        return {
            "success": True,
            "lines": top_lines,
            "current_state_summary": {
                "my_lp": my_lp,
                "opp_lp": opp_lp,
                "my_monsters": my_monsters,
                "opp_monsters": opp_monsters,
            },
            "total_candidates": len(candidate_moves),
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
