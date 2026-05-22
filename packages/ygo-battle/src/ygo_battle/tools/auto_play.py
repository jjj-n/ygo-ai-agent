"""Tool: auto_play - Run a full auto-battle."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance


def _pick_move_aggressive(moves: list[dict], player: int) -> dict | None:
    """Pick the best move for an aggressive strategy.

    Priority: summon > spsummon > activate > sset > mset > to_bp > to_ep
    """
    if not moves:
        return None

    idlecmd = None
    battlecmd = None
    other = []

    for m in moves:
        t = m.get("type")
        if t == "idlecmd":
            idlecmd = m
        elif t == "battlecmd":
            battlecmd = m
        else:
            other.append(m)

    # Battle phase: attack if possible
    if battlecmd:
        if battlecmd.get("attack_count", 0) > 0:
            return {"type": "attack", "index": 0}
        if battlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": 0}
        if battlecmd.get("to_m2", 0):
            return {"type": "to_m2"}
        if battlecmd.get("to_ep", 0):
            return {"type": "to_ep_battle"}

    # Main phase: summon > set > end
    if idlecmd:
        if idlecmd.get("summon_count", 0) > 0:
            return {"type": "summon", "index": 0}
        if idlecmd.get("spsummon_count", 0) > 0:
            return {"type": "spsummon", "index": 0}
        if idlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": 0}
        if idlecmd.get("sset_count", 0) > 0:
            return {"type": "sset", "index": 0}
        if idlecmd.get("mset_count", 0) > 0:
            return {"type": "mset", "index": 0}
        if idlecmd.get("to_bp", 0):
            return {"type": "to_bp"}
        if idlecmd.get("to_ep", 0):
            return {"type": "to_ep"}

    # Handle other prompt types
    for m in other:
        t = m.get("type")
        if t == "select_chain":
            count = m.get("count", 0)
            if count > 0:
                return {"type": "chain", "index": 0}
            return {"type": "chain", "index": -1}  # pass
        if t == "select_card":
            # Select first available card (e.g., attack target)
            cards = m.get("cards", [])
            if cards:
                return {"type": "select", "indices": [0]}
        if t == "select_effectyn" or t == "select_yesno":
            return {"type": "yes"}
        if t == "select_option":
            return {"type": "option", "option": 0}
        if t == "select_position":
            # Pick first available position
            positions = m.get("positions", [1])
            return {"type": "position", "position": positions[0] if positions else 1}
        if t == "select_tribute":
            # Select first available tribute
            return {"type": "select", "indices": [0]}

    return {"type": "to_ep"}  # fallback


async def auto_play(
    game_id: str,
    max_turns: int = 50,
    strategy_p1: str = "aggressive",
    strategy_p2: str = "control",
) -> dict:
    """全自动对战。

    自动执行对战直到游戏结束或达到最大回合数。

    Args:
        game_id: 游戏实例 ID
        max_turns: 最大回合数 (默认 50)
        strategy_p1: 玩家1的策略
        strategy_p2: 玩家2的策略

    Returns:
        对战结果和日志
    """
    try:
        instance = GameInstance.get(game_id)

        battle_log = []
        turn_count = 0

        battle_log.append({
            "turn": 0,
            "event": "battle_started",
            "game_id": game_id,
            "strategies": {
                "player1": strategy_p1,
                "player2": strategy_p2,
            },
        })

        # Battle loop
        while turn_count < max_turns:
            # Get legal moves
            moves = instance.get_legal_moves()
            if not moves:
                break

            current_move = moves[0]
            move_type = current_move.get("type", "")
            player = current_move.get("player", 0) + 1

            # Check game over
            if instance._state and instance._state.is_game_over:
                break

            # Pick move based on strategy
            strategy = strategy_p1 if player == 1 else strategy_p2
            chosen = _pick_move_aggressive(moves, player)

            if chosen is None:
                break

            # Track turn changes
            if move_type == "idlecmd" and chosen.get("type") == "to_ep":
                turn_count += 1

            # Execute move
            response = instance.do_move_raw(chosen)
            if not response.get("ok"):
                # If move failed, try end turn as fallback
                if chosen.get("type") not in ("to_ep", "to_ep_battle"):
                    # Try the correct end-phase command
                    fallback = {"type": "to_ep_battle"} if move_type == "battlecmd" else {"type": "to_ep"}
                    response = instance.do_move_raw(fallback)
                    if not response.get("ok"):
                        break

            battle_log.append({
                "turn": turn_count,
                "player": player,
                "move": chosen,
                "success": response.get("ok", False),
            })

        # Final state
        winner = -1
        if instance._state:
            winner = instance._state.winner

        battle_log.append({
            "turn": turn_count,
            "event": "game_over",
            "winner": winner,
        })

        return {
            "success": True,
            "game_over": True,
            "winner": winner,
            "turns": turn_count,
            "log": battle_log,
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
