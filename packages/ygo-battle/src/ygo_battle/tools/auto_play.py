"""Tool: auto_play - Run a full auto-battle."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.cards import CardDatabase
from ygo_engine_bridge.process import _DEFAULT_CARD_DB


# Lazy-loaded card database
_card_db: Optional[CardDatabase] = None


def _get_card_db() -> CardDatabase:
    global _card_db
    if _card_db is None:
        _card_db = CardDatabase(str(_DEFAULT_CARD_DB))
        _card_db.connect()
    return _card_db


# Card type constants from ygopro-core
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_MONSTER = 0x1
TYPE_NORMAL = 0x10
TYPE_CONTINUOUS = 0x20000
TYPE_QUICKPLAY = 0x10000
TYPE_RITUAL = 0x80
TYPE_EQUIP = 0x40000


def _is_spell(code: int) -> bool:
    """Check if card is a spell card."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return bool(info["type"] & TYPE_SPELL)
    except Exception:
        pass
    return False


def _is_trap(code: int) -> bool:
    """Check if card is a trap card."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return bool(info["type"] & TYPE_TRAP)
    except Exception:
        pass
    return False


def _is_monster(code: int) -> bool:
    """Check if card is a monster card."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return bool(info["type"] & TYPE_MONSTER)
    except Exception:
        pass
    return True  # default to monster


def _card_level(code: int) -> int:
    """Get card's level."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("level", 4)
    except Exception:
        pass
    return 4


def _card_atk(code: int) -> int:
    """Get card's ATK value."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("atk", 0)
    except Exception:
        pass
    return 0


def _card_def(code: int) -> int:
    """Get card's DEF value."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("def", 0)
    except Exception:
        pass
    return 0


def _handle_prompts(moves: list[dict]) -> dict | None:
    """Handle non-idlecmd/battlecmd prompts (select_card, yes/no, etc.).

    Returns a move dict if a prompt is found, None otherwise.
    """
    for m in moves:
        t = m.get("type")
        if t == "select_chain":
            count = m.get("count", 0)
            if count > 0:
                return {"type": "chain", "index": 0}
            return {"type": "chain", "index": -1}
        if t == "select_card":
            min_count = m.get("min", 1)
            cards = m.get("cards", [])
            if cards:
                indices = list(range(min(min_count, len(cards))))
                return {"type": "select", "indices": indices}
        if t in ("effectyn", "yesno"):
            return {"type": "yes"}
        if t == "select_option":
            return {"type": "option", "option": 0}
        if t == "select_position":
            positions = m.get("positions", [1])
            return {"type": "position", "position": positions[0] if positions else 1}
        if t == "select_tribute":
            min_count = m.get("min", 1)
            cards = m.get("cards", [])
            indices = list(range(min(min_count, len(cards))))
            return {"type": "select", "indices": indices}
        if t == "select_unselect_card":
            return {"type": "select", "indices": [0]}
        if t == "select_counter":
            return {"type": "counter", "indices": [0]}
        if t == "sort_card":
            count = m.get("count", 1)
            return {"type": "sort", "indices": list(range(count))}
    return None


def _pick_best_summon_index(idlecmd: dict) -> int:
    """Pick the best monster to summon: prefer highest ATK among level<=4, then lowest level."""
    cards = idlecmd.get("summon_cards", [])
    if not cards:
        return 0
    # Among level<=4 (no tribute needed), pick highest ATK
    best_idx = 0
    best_atk = -1
    for i, c in enumerate(cards):
        code = c.get("code", 0)
        level = _card_level(code)
        atk = _card_atk(code)
        if level <= 4 and atk > best_atk:
            best_atk = atk
            best_idx = i
    if best_atk >= 0:
        return best_idx
    # All are level>=5, pick lowest level (fewer tributes needed)
    best_idx = 0
    best_level = 999
    for i, c in enumerate(cards):
        level = _card_level(c.get("code", 0))
        if level < best_level:
            best_level = level
            best_idx = i
    return best_idx


def _pick_best_sset_index(idlecmd: dict) -> int:
    """Pick the best card to set (prefer spells/traps over monsters)."""
    cards = idlecmd.get("sset_cards", [])
    if not cards:
        return 0
    # Prefer traps, then spells, then monsters
    for i, c in enumerate(cards):
        if _is_trap(c.get("code", 0)):
            return i
    for i, c in enumerate(cards):
        if _is_spell(c.get("code", 0)):
            return i
    return 0


def _pick_best_activate_index(idlecmd: dict) -> int:
    """Pick the best effect to activate (prefer hand spells > field spells > monster effects)."""
    cards = idlecmd.get("activate_cards", [])
    if not cards:
        return 0
    # Prefer spell from hand (location 2) over field (location 8) over monster effects
    hand_spells = []
    field_spells = []
    for i, c in enumerate(cards):
        loc = c.get("location", 0)
        code = c.get("code", 0)
        if loc == 2 and _is_spell(code):  # LOCATION_HAND
            hand_spells.append(i)
        elif loc == 8:  # LOCATION_SZONE
            field_spells.append(i)
    if hand_spells:
        return hand_spells[0]
    if field_spells:
        return field_spells[0]
    return 0


def _pick_best_attack_index(battlecmd: dict) -> int:
    """Pick the best monster to attack with (highest ATK)."""
    cards = battlecmd.get("attack_cards", [])
    if not cards:
        return 0
    best_idx = 0
    best_atk = -1
    for i, c in enumerate(cards):
        atk = _card_atk(c.get("code", 0))
        if atk > best_atk:
            best_atk = atk
            best_idx = i
    return best_idx


def _has_strong_monster(cards: list[dict]) -> bool:
    """Check if any monster has ATK > 0."""
    for c in cards:
        if _card_atk(c.get("code", 0)) > 0:
            return True
    return False


def _opponent_max_atk(state: dict, player: int) -> int:
    """Get the maximum ATK among opponent's face-up monsters."""
    opp_key = "opponent" if player == 1 else "player"
    opp = state.get(opp_key, {})
    monsters = opp.get("monster_zones", [])
    max_atk = 0
    for m in monsters:
        if m and m.get("is_faceup"):
            atk = m.get("atk", 0)
            if atk > max_atk:
                max_atk = atk
    return max_atk


def _should_enter_battle(state: dict | None, player: int, idlecmd: dict) -> bool:
    """Decide whether to enter battle phase based on threat assessment.

    Returns True if we should enter battle phase, False if we should
    continue setting up (summon/set spells/traps first).
    """
    if state is None:
        return True  # No state info, default to attacking

    # Get our best monster ATK from summonable cards or field
    my_max_atk = 0
    for c in idlecmd.get("summon_cards", []):
        atk = _card_atk(c.get("code", 0))
        if atk > my_max_atk:
            my_max_atk = atk

    # Also check monsters already on field
    my_key = "player" if player == 1 else "opponent"
    my_monsters = state.get(my_key, {}).get("monster_zones", [])
    for m in my_monsters:
        if m and m.get("is_faceup"):
            atk = m.get("atk", 0)
            if atk > my_max_atk:
                my_max_atk = atk

    opp_max_atk = _opponent_max_atk(state, player)

    # If opponent has no monsters or we have stronger monsters, enter battle
    if opp_max_atk == 0:
        return True
    if my_max_atk > opp_max_atk:
        return True

    # If opponent has stronger monsters, prefer setting up first
    # (unless we have no spells/traps to set)
    if idlecmd.get("sset_count", 0) > 0:
        return False  # Set traps first
    if idlecmd.get("activate_count", 0) > 0:
        return False  # Activate effects first

    # Nothing better to do, enter battle anyway
    return True


def _pick_move_aggressive(moves: list[dict], player: int, state: dict | None = None) -> dict | None:
    """Aggressive: summon > spsummon > activate > attack > sset > mset > end.

    Prioritizes getting monsters on the field and attacking. Enters battle
    phase as soon as there's a monster with ATK > 0.
    """
    if not moves:
        return None

    prompt = _handle_prompts(moves)
    if prompt:
        return prompt

    idlecmd = None
    battlecmd = None

    for m in moves:
        t = m.get("type")
        if t == "idlecmd":
            idlecmd = m
        elif t == "battlecmd":
            battlecmd = m

    # Battle phase: attack with highest ATK monster
    if battlecmd:
        if battlecmd.get("attack_count", 0) > 0:
            return {"type": "attack", "index": _pick_best_attack_index(battlecmd)}
        if battlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": 0}
        if battlecmd.get("to_m2", 0):
            return {"type": "to_m2"}
        if battlecmd.get("to_ep", 0):
            return {"type": "to_ep_battle"}

    # Main phase: summon > spsummon > battle > activate > sset > mset > end
    # Aggressive prioritizes dealing damage over setup, but considers threats
    if idlecmd:
        if idlecmd.get("summon_count", 0) > 0:
            return {"type": "summon", "index": _pick_best_summon_index(idlecmd)}
        if idlecmd.get("spsummon_count", 0) > 0:
            return {"type": "spsummon", "index": 0}
        # Enter battle phase if safe, otherwise set up first
        if idlecmd.get("to_bp", 0):
            if _should_enter_battle(state, player, idlecmd):
                return {"type": "to_bp"}
            # Threat detected: try to set traps/activate effects first
            if idlecmd.get("sset_count", 0) > 0:
                return {"type": "sset", "index": _pick_best_sset_index(idlecmd)}
            if idlecmd.get("activate_count", 0) > 0:
                return {"type": "activate", "index": _pick_best_activate_index(idlecmd)}
            # Nothing to set, enter battle anyway
            return {"type": "to_bp"}
        if idlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": _pick_best_activate_index(idlecmd)}
        if idlecmd.get("sset_count", 0) > 0:
            return {"type": "sset", "index": _pick_best_sset_index(idlecmd)}
        if idlecmd.get("mset_count", 0) > 0:
            return {"type": "mset", "index": 0}
        if idlecmd.get("to_ep", 0):
            return {"type": "to_ep"}

    return {"type": "to_ep"}


def _pick_move_control(moves: list[dict], player: int, state: dict | None = None) -> dict | None:
    """Control: set traps > activate > summon > attack > end.

    Sets up defensive spells/traps first, then summons and enters battle
    when the board is established.
    """
    if not moves:
        return None

    prompt = _handle_prompts(moves)
    if prompt:
        return prompt

    idlecmd = None
    battlecmd = None

    for m in moves:
        t = m.get("type")
        if t == "idlecmd":
            idlecmd = m
        elif t == "battlecmd":
            battlecmd = m

    # Battle phase: activate effects first, then attack
    if battlecmd:
        if battlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": 0}
        if battlecmd.get("attack_count", 0) > 0:
            return {"type": "attack", "index": _pick_best_attack_index(battlecmd)}
        if battlecmd.get("to_m2", 0):
            return {"type": "to_m2"}
        if battlecmd.get("to_ep", 0):
            return {"type": "to_ep_battle"}

    # Main phase: set traps > activate > summon > battle > end
    if idlecmd:
        if idlecmd.get("sset_count", 0) > 0:
            return {"type": "sset", "index": _pick_best_sset_index(idlecmd)}
        if idlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": _pick_best_activate_index(idlecmd)}
        if idlecmd.get("summon_count", 0) > 0:
            return {"type": "summon", "index": _pick_best_summon_index(idlecmd)}
        if idlecmd.get("spsummon_count", 0) > 0:
            return {"type": "spsummon", "index": 0}
        if idlecmd.get("mset_count", 0) > 0:
            return {"type": "mset", "index": 0}
        if idlecmd.get("to_bp", 0):
            return {"type": "to_bp"}
        if idlecmd.get("to_ep", 0):
            return {"type": "to_ep"}

    return {"type": "to_ep"}


def _pick_move_combo(moves: list[dict], player: int, state: dict | None = None) -> dict | None:
    """Combo: spsummon > activate > summon > attack > sset > mset > end.

    Prioritizes building board presence through special summons and effect
    activations, then enters battle phase for lethal damage.
    """
    if not moves:
        return None

    prompt = _handle_prompts(moves)
    if prompt:
        return prompt

    idlecmd = None
    battlecmd = None

    for m in moves:
        t = m.get("type")
        if t == "idlecmd":
            idlecmd = m
        elif t == "battlecmd":
            battlecmd = m

    # Battle phase: attack with highest ATK, then activate effects
    if battlecmd:
        if battlecmd.get("attack_count", 0) > 0:
            return {"type": "attack", "index": _pick_best_attack_index(battlecmd)}
        if battlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": 0}
        if battlecmd.get("to_m2", 0):
            return {"type": "to_m2"}
        if battlecmd.get("to_ep", 0):
            return {"type": "to_ep_battle"}

    # Main phase: spsummon > summon > battle > activate > set > end
    # Combo builds board then attacks for lethal
    if idlecmd:
        if idlecmd.get("spsummon_count", 0) > 0:
            return {"type": "spsummon", "index": 0}
        if idlecmd.get("summon_count", 0) > 0:
            return {"type": "summon", "index": _pick_best_summon_index(idlecmd)}
        if idlecmd.get("to_bp", 0):
            if _should_enter_battle(state, player, idlecmd):
                return {"type": "to_bp"}
            # Threat detected: set up first
            if idlecmd.get("activate_count", 0) > 0:
                return {"type": "activate", "index": _pick_best_activate_index(idlecmd)}
            if idlecmd.get("sset_count", 0) > 0:
                return {"type": "sset", "index": _pick_best_sset_index(idlecmd)}
            return {"type": "to_bp"}
        if idlecmd.get("activate_count", 0) > 0:
            return {"type": "activate", "index": _pick_best_activate_index(idlecmd)}
        if idlecmd.get("sset_count", 0) > 0:
            return {"type": "sset", "index": _pick_best_sset_index(idlecmd)}
        if idlecmd.get("mset_count", 0) > 0:
            return {"type": "mset", "index": 0}
        if idlecmd.get("to_ep", 0):
            return {"type": "to_ep"}

    return {"type": "to_ep"}


_STRATEGIES = {
    "aggressive": _pick_move_aggressive,
    "control": _pick_move_control,
    "combo": _pick_move_combo,
}


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

        pick_p1 = _STRATEGIES.get(strategy_p1, _pick_move_aggressive)
        pick_p2 = _STRATEGIES.get(strategy_p2, _pick_move_control)

        # Battle loop with safety limits
        max_moves = max_turns * 20  # ~20 moves per turn is reasonable
        move_count = 0

        while turn_count < max_turns and move_count < max_moves:
            move_count += 1
            moves = instance.get_legal_moves()
            if not moves:
                break

            current_move = moves[0]
            move_type = current_move.get("type", "")
            player = current_move.get("player", 0) + 1

            if instance._state and instance._state.is_game_over:
                break

            pick_fn = pick_p1 if player == 1 else pick_p2
            # Get game state for threat assessment
            try:
                game_state = instance.get_state()
            except Exception:
                game_state = None
            chosen = pick_fn(moves, player, game_state)

            if chosen is None:
                break

            # Track turn changes
            if move_type == "idlecmd" and chosen.get("type") == "to_ep":
                turn_count += 1

            # Execute move
            try:
                response = instance.do_move_raw(chosen)
            except RuntimeError as e:
                error_msg = str(e)
                battle_log.append({
                    "turn": turn_count,
                    "player": player,
                    "move": chosen,
                    "success": False,
                    "error": error_msg,
                })
                return {
                    "success": False,
                    "game_over": True,
                    "winner": -1,
                    "turns": turn_count,
                    "moves": move_count,
                    "log": battle_log,
                    "error": error_msg,
                }
            if not response.get("ok"):
                if chosen.get("type") not in ("to_ep", "to_ep_battle"):
                    fallback = {"type": "to_ep_battle"} if move_type == "battlecmd" else {"type": "to_ep"}
                    try:
                        response = instance.do_move_raw(fallback)
                    except RuntimeError as e:
                        error_msg = str(e)
                        battle_log.append({
                            "turn": turn_count,
                            "player": player,
                            "move": fallback,
                            "success": False,
                            "error": error_msg,
                        })
                        return {
                            "success": False,
                            "game_over": True,
                            "winner": -1,
                            "turns": turn_count,
                            "moves": move_count,
                            "log": battle_log,
                            "error": error_msg,
                        }
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
