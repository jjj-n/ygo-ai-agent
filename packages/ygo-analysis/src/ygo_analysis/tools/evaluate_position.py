"""Tool: evaluate_position - Evaluate game position score."""

from __future__ import annotations
from ygo_engine_bridge import GameInstance


async def evaluate_position(
    game_id: str,
    player: int = 1,
) -> dict:
    """评估当前局面分数（0-100）。

    综合考虑场面、手牌、资源、LP等因素，给出局面评估分数。
    50分为均势，>50为优势，<50为劣势。

    评估维度：
    - LP 差距 (权重: 15%)
    - 场上怪兽价值 (权重: 30%)
    - 手牌数量 (权重: 15%)
    - 墓地资源 (权重: 10%)
    - 额外卡组资源 (权重: 10%)
    - 卡组余量 (权重: 10%)
    - 魔陷数量 (权重: 10%)

    Args:
        game_id: 游戏实例 ID
        player: 评估哪个玩家的局面 (1 或 2)

    Returns:
        局面评估分数和详细分析
    """
    try:
        instance = GameInstance.get(game_id)
        state = instance.get_state(player_pov=player, include_hidden=True)

        # Extract state information
        player_data = state.get("player", {})
        opponent_data = state.get("opponent", {})

        # Calculate score components
        score = 50.0
        details = {}

        # LP difference (weight: 15%)
        my_lp = player_data.get("lp", 8000)
        opp_lp = opponent_data.get("lp", 8000)
        lp_diff = my_lp - opp_lp
        lp_score = lp_diff / 8000 * 15
        score += lp_score
        details["lp"] = {
            "my": my_lp,
            "opponent": opp_lp,
            "diff": lp_diff,
            "score_impact": round(lp_score, 2),
        }

        # Monster value (weight: 30%)
        my_monsters = [m for m in player_data.get("monster_zones", []) if m is not None]
        opp_monsters = [m for m in opponent_data.get("monster_zones", []) if m is not None]

        def monster_value(m):
            atk = m.get("atk", 0) or 0
            return max(atk, 0)

        my_monster_total = sum(monster_value(m) for m in my_monsters)
        opp_monster_total = sum(monster_value(m) for m in opp_monsters)
        monster_diff = my_monster_total - opp_monster_total
        monster_score = monster_diff / 10000 * 30
        score += monster_score
        details["monsters"] = {
            "my_count": len(my_monsters),
            "opponent_count": len(opp_monsters),
            "my_total_atk": my_monster_total,
            "opponent_total_atk": opp_monster_total,
            "score_impact": round(monster_score, 2),
        }

        # Hand count (weight: 15%)
        my_hand = player_data.get("hand", [])
        opp_hand = opponent_data.get("hand", [])
        if isinstance(my_hand, dict):
            my_hand_count = my_hand.get("count", 0)
        else:
            my_hand_count = len(my_hand)
        if isinstance(opp_hand, dict):
            opp_hand_count = opp_hand.get("count", 0)
        else:
            opp_hand_count = len(opp_hand)

        hand_diff = my_hand_count - opp_hand_count
        hand_score = hand_diff * 3
        score += hand_score
        details["hand"] = {
            "my": my_hand_count,
            "opponent": opp_hand_count,
            "score_impact": round(hand_score, 2),
        }

        # Graveyard resources (weight: 10%)
        my_gy = player_data.get("graveyard", [])
        opp_gy = opponent_data.get("graveyard", [])
        gy_diff = len(my_gy) - len(opp_gy)
        gy_score = gy_diff * 1
        score += gy_score
        details["graveyard"] = {
            "my": len(my_gy),
            "opponent": len(opp_gy),
            "score_impact": round(gy_score, 2),
        }

        # Extra deck (weight: 10%)
        my_extra = player_data.get("extra_deck_count", 0)
        opp_extra = opponent_data.get("extra_deck_count", 0)
        extra_diff = my_extra - opp_extra
        extra_score = extra_diff * 0.5
        score += extra_score
        details["extra_deck"] = {
            "my": my_extra,
            "opponent": opp_extra,
            "score_impact": round(extra_score, 2),
        }

        # Deck count (weight: 10%)
        my_deck = player_data.get("deck_count", 0)
        opp_deck = opponent_data.get("deck_count", 0)
        deck_diff = my_deck - opp_deck
        deck_score = deck_diff * 0.3
        score += deck_score
        details["deck"] = {
            "my": my_deck,
            "opponent": opp_deck,
            "score_impact": round(deck_score, 2),
        }

        # Spell/Trap count (weight: 10%)
        my_st = sum(1 for s in player_data.get("spell_trap_zones", []) if s is not None)
        opp_st = sum(1 for s in opponent_data.get("spell_trap_zones", []) if s is not None)
        st_diff = my_st - opp_st
        st_score = st_diff * 2
        score += st_score
        details["spell_traps"] = {
            "my": my_st,
            "opponent": opp_st,
            "score_impact": round(st_score, 2),
        }

        # Clamp score to 0-100
        final_score = max(0, min(100, score))

        # Determine advantage
        if final_score > 60:
            advantage = "strong"
        elif final_score > 55:
            advantage = "slight"
        elif final_score > 45:
            advantage = "even"
        elif final_score > 40:
            advantage = "slight_disadvantage"
        else:
            advantage = "strong_disadvantage"

        return {
            "success": True,
            "score": round(final_score, 2),
            "advantage": advantage,
            "player": player,
            "details": details,
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
