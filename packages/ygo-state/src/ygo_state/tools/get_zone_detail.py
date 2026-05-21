"""Tool: get_zone_detail - Get detailed information about a specific zone."""

from ygo_engine_bridge import GameInstance


async def get_zone_detail(
    game_id: str,
    zone: str,
    player: int,
) -> dict:
    """获取指定区域的详细信息，包含卡牌效果文本。

    可查询区域: monster, spell_trap, graveyard, banished, extra, hand, field_spell

    Args:
        game_id: 游戏实例 ID
        zone: 要查询的区域
        player: 查询哪个玩家的区域 (1 或 2)

    Returns:
        区域内卡牌的详细信息列表
    """
    valid_zones = ["monster", "spell_trap", "graveyard", "banished", "extra", "hand", "field_spell"]
    if zone not in valid_zones:
        return {
            "success": False,
            "error": f"Invalid zone: {zone}. Valid zones: {', '.join(valid_zones)}",
        }

    try:
        instance = GameInstance.get(game_id)
        state = instance.get_state(player_pov=player, include_hidden=True)

        # Extract the specific zone
        player_data = state.get("player" if player == 1 else "opponent", {})

        if zone == "monster":
            cards = player_data.get("monster_zones", [])
        elif zone == "spell_trap":
            cards = player_data.get("spell_trap_zones", [])
        elif zone == "graveyard":
            cards = player_data.get("graveyard", [])
        elif zone == "banished":
            cards = player_data.get("banished", [])
        elif zone == "extra":
            cards = player_data.get("extra_deck", [])
        elif zone == "hand":
            hand = player_data.get("hand", {})
            if isinstance(hand, dict) and hand.get("cards") == "hidden":
                return {
                    "success": True,
                    "zone": zone,
                    "player": player,
                    "cards": [],
                    "count": hand.get("count", 0),
                    "note": "Hand is hidden from this perspective",
                }
            cards = hand if isinstance(hand, list) else []
        elif zone == "field_spell":
            card = player_data.get("field_spell")
            cards = [card] if card else []
        else:
            cards = []

        return {
            "success": True,
            "zone": zone,
            "player": player,
            "cards": [c for c in cards if c is not None],
            "count": len([c for c in cards if c is not None]),
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
