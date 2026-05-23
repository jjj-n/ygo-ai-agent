"""Tool: explain_line - Explain a sequence of moves with analysis."""

from __future__ import annotations
from pathlib import Path
from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.cards import CardDatabase
from ygo_engine_bridge.instance import _DEFAULT_CARD_DB
from ygo_analysis.tools.find_best_line import (
    evaluate_position_sync,
    find_best_line,
    _extract_all_moves,
)

# Chinese card database path
_DEFAULT_ZH_CARD_DB = Path(_DEFAULT_CARD_DB).parent / "cards_zh.cdb"

# Lazy-loaded card database
_card_db = None


def _get_card_db() -> CardDatabase:
    global _card_db
    if _card_db is None:
        zh_path = str(_DEFAULT_ZH_CARD_DB) if _DEFAULT_ZH_CARD_DB.exists() else None
        _card_db = CardDatabase(str(_DEFAULT_CARD_DB), zh_db_path=zh_path)
        _card_db.connect()
    return _card_db


def _describe_move(move: dict, state_before: dict, state_after: dict) -> str:
    """Generate a human-readable description of a move."""
    move_type = move.get("type", "unknown")
    index = move.get("index", 0)

    descriptions = {
        "summon": f"通常召唤怪兽 #{index}",
        "spsummon": f"特殊召唤怪兽 #{index}",
        "activate": f"发动效果 #{index}",
        "sset": f"覆盖魔陷 #{index}",
        "mset": f"覆盖怪兽 #{index}",
        "attack": f"攻击 #{index}",
        "to_bp": "进入战斗阶段",
        "to_ep": "结束回合",
        "to_ep_battle": "结束战斗阶段",
        "to_m2": "进入主要阶段2",
    }

    desc = descriptions.get(move_type, f"执行操作: {move_type}")

    # Try to identify the card involved by comparing states
    if move_type in ("summon", "spsummon", "activate", "sset", "mset"):
        my_before = state_before.get("player", {})
        my_after = state_after.get("player", {})

        # Check monster zones for new cards
        before_monsters = [m for m in my_before.get("monster_zones", []) if m]
        after_monsters = [m for m in my_after.get("monster_zones", []) if m]

        if len(after_monsters) > len(before_monsters):
            new_cards = [m for m in after_monsters if m not in before_monsters]
            if new_cards:
                card_name = new_cards[0].get("name", "未知")
                desc = f"{desc} ({card_name})"

        # Check spell/trap zones for new cards
        before_st = [s for s in my_before.get("spell_trap_zones", []) if s]
        after_st = [s for s in my_after.get("spell_trap_zones", []) if s]

        if len(after_st) > len(before_st):
            new_cards = [s for s in after_st if s not in before_st]
            if new_cards:
                card_name = new_cards[0].get("name", "未知")
                desc = f"{desc} ({card_name})"

    return desc


async def explain_line(
    game_id: str,
    moves: list[dict] | None = None,
    player: int = 1,
    max_depth: int = 2,
) -> dict:
    """解释一个操作序列的意图和效果。

    如果未提供 moves，则使用 find_best_line 找到最优路线并解释。
    对每一步操作，分析其前后状态变化和战略意义。

    Args:
        game_id: 游戏实例 ID
        moves: 要解释的操作序列。None 则自动搜索最优路线。
        player: 评估哪个玩家 (1 或 2)
        max_depth: 自动搜索时的最大深度 (默认 2)

    Returns:
        操作序列的结构化解释
    """
    try:
        instance = GameInstance.get(game_id)

        # If no moves provided, find the best line first
        if moves is None:
            best_result = await find_best_line(
                game_id, player=player, max_depth=max_depth, top_k=1
            )
            if not best_result.get("success") or not best_result.get("lines"):
                return {
                    "success": True,
                    "line": [],
                    "message": "无法找到可用的操作路线",
                }
            moves = best_result["lines"][0].get("move_path", [])
            if not moves:
                return {
                    "success": True,
                    "line": [],
                    "message": "无可用操作",
                }

        # Get initial state
        initial_state = instance.get_state(player_pov=player)
        initial_score = evaluate_position_sync(initial_state, player)

        # Walk through each move using clones
        explanations = []
        current_instance = instance
        cumulative_score = initial_score

        for i, move in enumerate(moves):
            try:
                clone = current_instance.clone()
                state_before = current_instance.get_state(player_pov=player)
                score_before = evaluate_position_sync(state_before, player)

                result = clone.do_move_raw(move)
                success = result.get("success", False) or result.get("ok", False)

                if success:
                    state_after = clone.get_state(player_pov=player)
                    score_after = evaluate_position_sync(state_after, player)
                    description = _describe_move(move, state_before, state_after)

                    explanations.append({
                        "step": i + 1,
                        "move": move,
                        "description": description,
                        "score_before": round(score_before, 2),
                        "score_after": round(score_after, 2),
                        "score_change": round(score_after - score_before, 2),
                    })

                    cumulative_score = score_after

                    # Prepare for next step
                    next_instance = current_instance.clone()
                    next_instance.do_move_raw(move)
                    if i > 0:
                        current_instance.close()
                    current_instance = next_instance
                else:
                    explanations.append({
                        "step": i + 1,
                        "move": move,
                        "description": f"操作失败: {result.get('reason', '未知原因')}",
                        "score_before": round(score_before, 2),
                        "score_after": round(score_before, 2),
                        "score_change": 0,
                    })

                clone.close()
            except Exception as e:
                explanations.append({
                    "step": i + 1,
                    "move": move,
                    "description": f"模拟出错: {str(e)}",
                    "score_before": 0,
                    "score_after": 0,
                    "score_change": 0,
                })

        if len(moves) > 1 and current_instance != instance:
            current_instance.close()

        total_change = cumulative_score - initial_score

        return {
            "success": True,
            "line": explanations,
            "initial_score": round(initial_score, 2),
            "final_score": round(cumulative_score, 2),
            "total_score_change": round(total_change, 2),
            "move_count": len(explanations),
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
