"""Tool: find_best_line - Find the best move sequence using beam search."""

from __future__ import annotations
import time
from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.instance import _format_card


# Card type constants for extra deck identification
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000
EXTRA_DECK_TYPES = TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK


def evaluate_position_sync(state: dict, player: int) -> float:
    """Synchronous position evaluation for tree search.

    Returns score 0-100. Called directly by tree search without MCP overhead.
    """
    my_key = "player" if player == 1 else "player"  # state is already from player's POV
    opp_key = "opponent"

    player_data = state.get(my_key, {})
    opponent_data = state.get(opp_key, {})

    score = 50.0

    # LP difference (weight: 15%)
    my_lp = player_data.get("lp", 8000)
    opp_lp = opponent_data.get("lp", 8000)
    lp_diff = my_lp - opp_lp
    score += lp_diff / 8000 * 15

    # Monster value (weight: 30%)
    my_monsters = [m for m in player_data.get("monster_zones", []) if m is not None]
    opp_monsters = [m for m in opponent_data.get("monster_zones", []) if m is not None]

    def monster_value(m):
        atk = m.get("atk", 0) or 0
        return max(atk, 0)

    my_monster_total = sum(monster_value(m) for m in my_monsters)
    opp_monster_total = sum(monster_value(m) for m in opp_monsters)
    monster_diff = my_monster_total - opp_monster_total
    score += monster_diff / 10000 * 30

    # Hand count (weight: 15%)
    my_hand = player_data.get("hand", [])
    opp_hand = opponent_data.get("hand", [])
    my_hand_count = len(my_hand) if isinstance(my_hand, list) else my_hand.get("count", 0)
    opp_hand_count = len(opp_hand) if isinstance(opp_hand, list) else opp_hand.get("count", 0)
    hand_diff = my_hand_count - opp_hand_count
    score += hand_diff * 3

    # Graveyard resources (weight: 10%)
    my_gy = player_data.get("graveyard", [])
    opp_gy = opponent_data.get("graveyard", [])
    gy_diff = len(my_gy) - len(opp_gy)
    score += gy_diff * 1

    # Extra deck (weight: 10%)
    my_extra = player_data.get("extra_deck_count", 0)
    opp_extra = opponent_data.get("extra_deck_count", 0)
    extra_diff = my_extra - opp_extra
    score += extra_diff * 0.5

    # Deck count (weight: 10%)
    my_deck = player_data.get("deck_count", 0)
    opp_deck = opponent_data.get("deck_count", 0)
    deck_diff = my_deck - opp_deck
    score += deck_diff * 0.3

    # Spell/Trap count (weight: 10%)
    my_st = sum(1 for s in player_data.get("spell_trap_zones", []) if s is not None)
    opp_st = sum(1 for s in opponent_data.get("spell_trap_zones", []) if s is not None)
    st_diff = my_st - opp_st
    score += st_diff * 2

    return max(0, min(100, score))


def _extract_all_moves(legal_moves: list[dict]) -> list[dict]:
    """Extract all concrete moves from legal moves, including multiple indices."""
    candidates = []

    for move_info in legal_moves:
        t = move_info.get("type")
        if t == "idlecmd":
            # Summon - try all available indices
            summon_count = move_info.get("summon_count", 0)
            for i in range(summon_count):
                candidates.append({"type": "summon", "index": i, "desc": f"Summon monster #{i}"})

            # Special summon - try all available indices
            spsummon_count = move_info.get("spsummon_count", 0)
            for i in range(spsummon_count):
                cards = move_info.get("spsummon_cards", [])
                if i < len(cards):
                    code = cards[i].get("code", 0)
                    desc = f"Special summon #{i}"
                    candidates.append({"type": "spsummon", "index": i, "desc": desc})
                else:
                    candidates.append({"type": "spsummon", "index": i, "desc": f"Special summon #{i}"})

            # Activate - try all available indices
            activate_count = move_info.get("activate_count", 0)
            for i in range(activate_count):
                candidates.append({"type": "activate", "index": i, "desc": f"Activate effect #{i}"})

            # Set spell/trap
            sset_count = move_info.get("sset_count", 0)
            for i in range(sset_count):
                candidates.append({"type": "sset", "index": i, "desc": f"Set spell/trap #{i}"})

            # Set monster
            mset_count = move_info.get("mset_count", 0)
            for i in range(mset_count):
                candidates.append({"type": "mset", "index": i, "desc": f"Set monster #{i}"})

            # Phase transitions
            if move_info.get("to_bp", 0):
                candidates.append({"type": "to_bp", "desc": "Enter battle phase"})
            if move_info.get("to_ep", 0):
                candidates.append({"type": "to_ep", "desc": "End phase"})

        elif t == "battlecmd":
            # Attack - try all available indices
            attack_count = move_info.get("attack_count", 0)
            for i in range(attack_count):
                candidates.append({"type": "attack", "index": i, "desc": f"Attack #{i}"})

            # Battle phase activate
            activate_count = move_info.get("activate_count", 0)
            for i in range(activate_count):
                candidates.append({"type": "activate", "index": i, "desc": f"Battle activate #{i}"})

            if move_info.get("to_m2", 0):
                candidates.append({"type": "to_m2", "desc": "To main phase 2"})
            if move_info.get("to_ep", 0):
                candidates.append({"type": "to_ep_battle", "desc": "End battle phase"})

    return candidates


async def find_best_line(
    game_id: str,
    player: int = 1,
    max_depth: int = 3,
    top_k: int = 3,
    beam_width: int = 5,
    timeout_seconds: float = 10.0,
) -> dict:
    """自动搜索 N 步内的最优展开路线 (Beam Search)。

    使用 beam search 在游戏状态空间中搜索最优操作序列。
    在每个深度，保留评估分数最高的 beam_width 个状态，
    然后从这些状态继续搜索。

    Args:
        game_id: 游戏实例 ID
        player: 评估哪个玩家 (1 或 2)
        max_depth: 最大推演步数 (默认 3)
        top_k: 返回前 K 条路径 (默认 3)
        beam_width: 每层保留的状态数 (默认 5)
        timeout_seconds: 搜索超时时间 (默认 10 秒)

    Returns:
        最优展开路线列表
    """
    try:
        instance = GameInstance.get(game_id)
        start_time = time.time()

        # Get initial state and moves
        current_state = instance.get_state(player_pov=player)
        initial_score = evaluate_position_sync(current_state, player)

        legal_moves = instance.get_legal_moves()
        if not legal_moves:
            return {
                "success": True,
                "lines": [],
                "message": "No legal moves available",
            }

        # Extract all concrete moves
        all_moves = _extract_all_moves(legal_moves)
        if not all_moves:
            return {
                "success": True,
                "lines": [],
                "message": "No concrete moves available",
            }

        # Beam search: each entry is (score, move_path, state)
        # Start with the current state
        beam = [(initial_score, [], current_state)]

        best_lines = []

        for depth in range(max_depth):
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                break

            candidates = []

            for current_score, path, state in beam:
                # Get legal moves from this state
                try:
                    moves = instance.get_legal_moves()
                except Exception:
                    continue

                if not moves:
                    # No moves available - this is a terminal state
                    best_lines.append({
                        "move_path": path,
                        "score": round(current_score, 2),
                        "depth": len(path),
                    })
                    continue

                concrete_moves = _extract_all_moves(moves)

                # Try each move (limit to beam_width to control explosion)
                for move in concrete_moves[:beam_width]:
                    # Check timeout
                    if time.time() - start_time > timeout_seconds:
                        break

                    # Clone the instance and execute the move
                    try:
                        clone = instance.clone()
                        result = clone.execute_move(move)

                        if result.get("success", False) or result.get("ok", False):
                            # Get the new state
                            new_state = clone.get_state(player_pov=player)
                            new_score = evaluate_position_sync(new_state, player)

                            new_path = path + [move]
                            candidates.append((new_score, new_path, new_state))

                            # Also track complete lines
                            best_lines.append({
                                "move_path": new_path,
                                "score": round(new_score, 2),
                                "depth": len(new_path),
                            })

                        clone.close()
                    except Exception:
                        continue

            # Keep top beam_width candidates for next iteration
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                beam = candidates[:beam_width]
            else:
                break

        # Sort all found lines by score
        best_lines.sort(key=lambda x: x["score"], reverse=True)

        # Deduplicate lines (same move path)
        seen = set()
        unique_lines = []
        for line in best_lines:
            path_key = str(line["move_path"])
            if path_key not in seen:
                seen.add(path_key)
                unique_lines.append(line)

        top_lines = unique_lines[:top_k]

        # Add summary info to each line
        for line in top_lines:
            line["move_descriptions"] = [
                m.get("desc", m.get("type", "unknown")) for m in line["move_path"]
            ]

        return {
            "success": True,
            "lines": top_lines,
            "current_state_summary": {
                "score": round(initial_score, 2),
                "player": player,
            },
            "search_stats": {
                "total_lines_found": len(unique_lines),
                "max_depth_used": max((l["depth"] for l in unique_lines), default=0),
                "beam_width": beam_width,
                "elapsed_seconds": round(time.time() - start_time, 2),
            },
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
