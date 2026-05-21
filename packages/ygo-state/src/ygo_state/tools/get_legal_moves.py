"""Tool: get_legal_moves - Get all legal moves in current position."""

from ygo_engine_bridge import GameInstance


async def get_legal_moves(game_id: str) -> dict:
    """获取当前所有合法操作。

    返回操作列表，每个操作包含类型、目标、时点等信息。
    用于让 LLM 了解当前可以执行哪些操作。

    Args:
        game_id: 游戏实例 ID

    Returns:
        合法操作列表
    """
    try:
        instance = GameInstance.get(game_id)
        moves = instance.get_legal_moves()
        return {
            "success": True,
            "moves": moves,
            "count": len(moves),
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
