"""Tool: get_battle_log - Get battle log for a game."""

from __future__ import annotations
from pathlib import Path
from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.cards import CardDatabase
from ygo_engine_bridge.instance import _DEFAULT_CARD_DB

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


def _resolve_move_card(move: dict) -> str:
    """Try to resolve card name from a move dict."""
    # Moves from auto_play have raw types like "summon", "activate", etc.
    # The actual card code is not in the move dict, so we describe by type
    move_type = move.get("type", "unknown")
    index = move.get("index", 0)

    type_names = {
        "summon": f"通常召唤 #{index}",
        "spsummon": f"特殊召唤 #{index}",
        "activate": f"发动效果 #{index}",
        "sset": f"覆盖魔陷 #{index}",
        "mset": f"覆盖怪兽 #{index}",
        "attack": f"攻击 #{index}",
        "to_bp": "进入战斗阶段",
        "to_ep": "结束回合",
        "to_ep_battle": "结束战斗阶段",
        "to_m2": "进入主要阶段2",
    }

    return type_names.get(move_type, f"{move_type} #{index}")


async def get_battle_log(game_id: str) -> dict:
    """获取对战日志。

    返回对局的完整操作记录，用于复盘分析。

    Args:
        game_id: 游戏实例 ID

    Returns:
        对战日志，包含所有操作记录和当前状态
    """
    try:
        instance = GameInstance.get(game_id)

        # Get current state
        state = instance.get_state()

        # Build annotated move history from _move_history
        annotated_moves = []
        for i, cmd in enumerate(instance._move_history):
            entry = {
                "index": i,
                "command": cmd.get("cmd", "unknown"),
            }

            # Extract move info if present
            if "move" in cmd:
                move = cmd["move"]
                entry["move"] = move
                entry["description"] = _resolve_move_card(move)
            elif "action" in cmd:
                entry["action"] = cmd["action"]
                entry["description"] = f"连锁响应: {cmd['action']}"

            annotated_moves.append(entry)

        return {
            "success": True,
            "game_id": game_id,
            "current_state": state,
            "is_game_over": state.get("is_game_over", False),
            "winner": state.get("winner", -1),
            "turn": state.get("turn", 0),
            "move_count": len(instance._move_history),
            "log": annotated_moves,
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
