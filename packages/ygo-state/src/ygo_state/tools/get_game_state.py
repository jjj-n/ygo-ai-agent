"""Tool: get_game_state - Get complete game state snapshot."""

from ygo_engine_bridge import GameInstance


async def get_game_state(
    game_id: str,
    player_pov: int = 1,
    include_hidden: bool = False,
) -> dict:
    """获取完整游戏状态快照。

    返回场上/手牌/墓地/除外/额外/卡组/LP/回合/阶段等全部信息。
    默认返回当前玩家视角（对手手牌为隐藏状态）。

    Args:
        game_id: 游戏实例 ID
        player_pov: 视角玩家 (1=玩家1, 2=玩家2)。默认为当前行动玩家。
        include_hidden: 是否包含对手隐藏信息（手牌/覆盖卡）。调试用。

    Returns:
        完整游戏状态字典
    """
    try:
        instance = GameInstance.get(game_id)
        state = instance.get_state(player_pov, include_hidden)
        return {
            "success": True,
            "state": state,
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
