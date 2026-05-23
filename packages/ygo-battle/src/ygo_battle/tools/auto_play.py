"""Tool: auto_play - Run a full auto-battle."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.cards import CardDatabase
from ygo_engine_bridge.instance import _DEFAULT_CARD_DB
from ygo_engine_bridge.effects import estimate_card_value, get_effect_priority
from ygo_battle.opening_book import is_opening_turn, get_opening_sequence

# Chinese card database path
_DEFAULT_ZH_CARD_DB = Path(_DEFAULT_CARD_DB).parent / "cards_zh.cdb"

# Lazy-loaded card database
_card_db: Optional[CardDatabase] = None


def _get_card_db() -> CardDatabase:
    global _card_db
    if _card_db is None:
        zh_path = str(_DEFAULT_ZH_CARD_DB) if _DEFAULT_ZH_CARD_DB.exists() else None
        _card_db = CardDatabase(str(_DEFAULT_CARD_DB), zh_db_path=zh_path)
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
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000
TYPE_PENDULUM = 0x1000000
EXTRA_DECK_TYPES = TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK


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


def _card_type(code: int) -> int:
    """Get card's type flags."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("type", 0)
    except Exception:
        pass
    return 0


def _is_extra_deck_card(code: int) -> bool:
    """Check if a card is an extra deck monster (Fusion/Synchro/XYZ/Link)."""
    return bool(_card_type(code) & EXTRA_DECK_TYPES)


def _get_extra_deck_type_name(code: int) -> str:
    """Get the extra deck type name for a card."""
    t = _card_type(code)
    types = []
    if t & TYPE_FUSION:
        types.append("Fusion")
    if t & TYPE_SYNCHRO:
        types.append("Synchro")
    if t & TYPE_XYZ:
        types.append("XYZ")
    if t & TYPE_LINK:
        types.append("Link")
    return "/".join(types) if types else "Normal"


def _pick_best_spsummon_index(idlecmd: dict) -> int:
    """Pick the best special summon option.

    Prioritizes:
    1. Extra deck summons (Fusion/Synchro/XYZ/Link) with highest ATK
    2. Effect monsters with high ATK
    3. Highest ATK among remaining options
    """
    cards = idlecmd.get("spsummon_cards", [])
    if not cards:
        return 0

    # Separate extra deck summons from regular special summons
    extra_deck_indices = []
    regular_indices = []

    for i, c in enumerate(cards):
        code = c.get("code", 0)
        if _is_extra_deck_card(code):
            extra_deck_indices.append(i)
        else:
            regular_indices.append(i)

    # Among extra deck summons, pick highest ATK
    if extra_deck_indices:
        best_idx = extra_deck_indices[0]
        best_atk = -1
        for i in extra_deck_indices:
            atk = _card_atk(cards[i].get("code", 0))
            if atk > best_atk:
                best_atk = atk
                best_idx = i
        return best_idx

    # Among regular summons, pick highest ATK
    if regular_indices:
        best_idx = regular_indices[0]
        best_atk = -1
        for i in regular_indices:
            atk = _card_atk(cards[i].get("code", 0))
            if atk > best_atk:
                best_atk = atk
                best_idx = i
        return best_idx

    return 0


def _card_effect_value(code: int) -> float:
    """Get the strategic value of a card based on its effect text."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            effect_text = info.get("desc", "")
            card_type = info.get("type", 0)
            return estimate_card_value(effect_text, card_type)
    except Exception:
        pass
    return 0.0


def _card_effect_priority(code: int) -> int:
    """Get the activation priority for a card based on its effect text."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            effect_text = info.get("desc", "")
            return get_effect_priority(effect_text)
    except Exception:
        pass
    return 0


def _calc_chain_thresholds(state: dict | None, player: int) -> tuple[int, int]:
    """Calculate dynamic chain activation thresholds based on game state.

    Returns (chain_threshold, yesno_threshold) — lower means more aggressive activation.
    """
    base_chain = 60
    base_yesno = 40

    if state is None:
        return base_chain, base_yesno

    my_key = "player" if player == 1 else "opponent"
    opp_key = "opponent" if player == 1 else "player"
    my_data = state.get(my_key, {})
    opp_data = state.get(opp_key, {})

    my_lp = my_data.get("lp", 8000)
    opp_lp = opp_data.get("lp", 8000)
    my_hand = len(my_data.get("hand", []))
    opp_monsters = [m for m in opp_data.get("monster_zones", []) if m]

    # LP disadvantage: be more aggressive (lower threshold)
    lp_diff = my_lp - opp_lp
    if lp_diff < -2000:
        base_chain -= 15
        base_yesno -= 10
    elif lp_diff < -1000:
        base_chain -= 10
        base_yesno -= 5
    # LP advantage: be slightly more conservative
    elif lp_diff > 3000:
        base_chain += 5
        base_yesno += 5

    # Few hand cards: be more conservative (save resources)
    if my_hand <= 2:
        base_chain += 10
        base_yesno += 10
    # Many hand cards: can afford to be aggressive
    elif my_hand >= 5:
        base_chain -= 5
        base_yesno -= 5

    # Opponent has strong monsters: be more aggressive with interaction
    if opp_monsters:
        max_opp_atk = max((m.get("atk", 0) or 0) for m in opp_monsters)
        if max_opp_atk >= 2500:
            base_chain -= 10
            base_yesno -= 5

    # Clamp thresholds
    base_chain = max(30, min(80, base_chain))
    base_yesno = max(20, min(60, base_yesno))

    return base_chain, base_yesno


def _estimate_chain_risk(chain_card: dict, state: dict | None, player: int) -> float:
    """Estimate the risk of activating a chain card.

    Considers:
    - Whether the opponent might have counter traps
    - Whether the effect is mandatory or optional
    - Whether we're in a winning or losing position

    Returns a risk score (0-1, higher = more risky).
    """
    risk = 0.3  # Base risk

    if state is None:
        return risk

    my_key = "player" if player == 1 else "opponent"
    opp_key = "opponent" if player == 1 else "player"
    my_data = state.get(my_key, {})
    opp_data = state.get(opp_key, {})

    # Check if opponent has set traps (potential counter traps)
    opp_traps = [s for s in opp_data.get("spell_trap_zones", []) if s and s.get("is_set")]
    if opp_traps:
        risk += 0.2  # Higher risk if opponent has set cards

    # Check LP situation
    my_lp = my_data.get("lp", 8000)
    opp_lp = opp_data.get("lp", 8000)
    if my_lp < opp_lp:
        risk -= 0.1  # Lower risk when behind (more desperate)

    # Check hand size
    my_hand = len(my_data.get("hand", []))
    if my_hand <= 2:
        risk += 0.1  # Higher risk with few cards

    return max(0.0, min(1.0, risk))


def _should_chain_for_multi_step(
    chain_card: dict,
    chain_level: int,
    state: dict | None,
    player: int,
) -> bool:
    """Decide whether to activate a chain considering multi-step chains.

    Args:
        chain_card: The card being considered for chaining
        chain_level: Current chain level (1, 2, 3, etc.)
        state: Current game state
        player: Current player

    Returns:
        True if we should activate the chain, False otherwise.
    """
    # For chain level 1, use normal priority
    if chain_level <= 1:
        return True

    # For higher chain levels, be more conservative
    # The risk of opponent responding increases with chain level
    risk = _estimate_chain_risk(chain_card, state, player)

    # Get card priority
    code = chain_card.get("code", 0)
    priority = _card_effect_priority(code)

    # Higher chain levels require higher priority to be worth the risk
    # Chain 2: need priority >= 70
    # Chain 3: need priority >= 80
    # Chain 4+: need priority >= 90
    required_priority = 60 + (chain_level * 10)

    # Adjust for risk
    if risk > 0.5:
        required_priority += 10

    return priority >= required_priority


def _decide_chain(moves: list[dict], state: dict | None = None, player: int = 1) -> dict | None:
    """Decide whether to activate a chain response based on card effect priority.

    For select_chain: evaluates each chainable card's effect priority.
    Activates the highest-priority card if priority >= dynamic threshold.
    Otherwise passes.

    For effectyn/yesno: activates if card priority >= dynamic threshold.

    Supports multi-step chain decisions (chain 2/3/4+) with increasing
    conservatism for higher chain levels.

    Args:
        moves: List of legal moves/prompts
        state: Current game state for dynamic threshold calculation
        player: Current player (1 or 2)

    Returns:
        A move dict if a chain/yesno prompt is found, None otherwise.
    """
    chain_threshold, yesno_threshold = _calc_chain_thresholds(state, player)

    for m in moves:
        t = m.get("type")

        if t == "select_chain":
            count = m.get("count", 0)
            if count == 0:
                return {"type": "chain", "index": -1}

            # Get chain level (if provided by engine)
            chain_level = m.get("chain_level", 1)

            # Evaluate chainable cards by effect priority
            chains = m.get("chains", [])
            best_idx = 0
            best_priority = -1

            for i, chain_card in enumerate(chains):
                code = chain_card.get("code", 0)
                priority = _card_effect_priority(code)

                # Apply multi-step chain logic for higher levels
                if chain_level > 1:
                    if not _should_chain_for_multi_step(chain_card, chain_level, state, player):
                        continue

                if priority > best_priority:
                    best_priority = priority
                    best_idx = i

            # Activate if priority meets dynamic threshold
            if best_priority >= chain_threshold:
                return {"type": "chain", "index": best_idx}
            return {"type": "chain", "index": -1}

        if t in ("effectyn", "yesno"):
            # Get card code from the prompt
            code = m.get("code", 0)
            if not code:
                # Try to extract from description or other fields
                cards = m.get("cards", [])
                if cards:
                    code = cards[0].get("code", 0) if isinstance(cards[0], dict) else 0

            if code:
                priority = _card_effect_priority(code)
                # Activate if priority meets dynamic threshold
                if priority >= yesno_threshold:
                    return {"type": "yes"}
            return {"type": "no"}

    return None


def _handle_prompts(moves: list[dict]) -> dict | None:
    """Handle non-idlecmd/battlecmd prompts (select_card, tribute, etc.).

    Does NOT handle chain/yesno — those go through _decide_chain().
    Returns a move dict if a prompt is found, None otherwise.
    """
    for m in moves:
        t = m.get("type")
        if t == "select_chain" or t in ("effectyn", "yesno"):
            continue  # Handled by _decide_chain()
        if t == "select_card":
            min_count = m.get("min", 1)
            cards = m.get("cards", [])
            if cards:
                indices = list(range(min(min_count, len(cards))))
                return {"type": "select", "indices": indices}
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
    """Pick the best card to set based on effect value."""
    cards = idlecmd.get("sset_cards", [])
    if not cards:
        return 0

    # Score each card by effect value
    best_idx = 0
    best_value = -1

    for i, c in enumerate(cards):
        code = c.get("code", 0)
        # Traps are generally better to set than spells
        if _is_trap(code):
            value = _card_effect_value(code) + 2.0  # Bonus for traps
        elif _is_spell(code):
            value = _card_effect_value(code) + 1.0  # Bonus for spells
        else:
            value = _card_effect_value(code)

        if value > best_value:
            best_value = value
            best_idx = i

    # If no effect text found, fall back to trap > spell preference
    if best_value <= 0:
        for i, c in enumerate(cards):
            if _is_trap(c.get("code", 0)):
                return i
        for i, c in enumerate(cards):
            if _is_spell(c.get("code", 0)):
                return i

    return best_idx


def _pick_best_activate_index(idlecmd: dict) -> int:
    """Pick the best effect to activate based on effect text value."""
    cards = idlecmd.get("activate_cards", [])
    if not cards:
        return 0

    # Score each card by effect priority
    best_idx = 0
    best_priority = -1

    for i, c in enumerate(cards):
        code = c.get("code", 0)
        priority = _card_effect_priority(code)
        if priority > best_priority:
            best_priority = priority
            best_idx = i

    # If no effect text found, fall back to hand > field preference
    if best_priority <= 0:
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

    return best_idx


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

    # Handle chain responses first (smart priority-based decisions)
    chain = _decide_chain(moves, state, player)
    if chain:
        return chain

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
            return {"type": "spsummon", "index": _pick_best_spsummon_index(idlecmd)}
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

    # Handle chain responses first (smart priority-based decisions)
    chain = _decide_chain(moves, state, player)
    if chain:
        return chain

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
            return {"type": "spsummon", "index": _pick_best_spsummon_index(idlecmd)}
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

    # Handle chain responses first (smart priority-based decisions)
    chain = _decide_chain(moves, state, player)
    if chain:
        return chain

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
            return {"type": "spsummon", "index": _pick_best_spsummon_index(idlecmd)}
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

            # Check opening book first for early turns
            chosen = None
            if is_opening_turn(turn_count):
                strategy = strategy_p1 if player == 1 else strategy_p2
                try:
                    # Extract hand card codes for opening book
                    hand_key = "hand"
                    my_key = "player" if player == 1 else "opponent"
                    hand_data = game_state.get(my_key, {}).get(hand_key, [])
                    hand_codes = [c.get("code", 0) for c in hand_data if isinstance(c, dict)]

                    # Try to get opening sequence
                    opening_seq = get_opening_sequence(strategy, hand_codes, turn_count)
                    if opening_seq:
                        # Find matching move from opening sequence in legal moves
                        for open_move in opening_seq:
                            for legal_move in moves:
                                if legal_move.get("type") == open_move.get("type"):
                                    # Check if the move type is available
                                    if legal_move.get("type") == "idlecmd":
                                        # For idlecmd, check if the action is available
                                        if open_move.get("type") == "summon" and legal_move.get("summon_count", 0) > 0:
                                            chosen = open_move
                                            break
                                        elif open_move.get("type") == "spsummon" and legal_move.get("spsummon_count", 0) > 0:
                                            chosen = open_move
                                            break
                                        elif open_move.get("type") == "sset" and legal_move.get("sset_count", 0) > 0:
                                            chosen = open_move
                                            break
                                        elif open_move.get("type") == "to_bp" and legal_move.get("to_bp", 0):
                                            chosen = open_move
                                            break
                                        elif open_move.get("type") == "to_ep" and legal_move.get("to_ep", 0):
                                            chosen = open_move
                                            break
                                    elif legal_move.get("type") == "battlecmd":
                                        if open_move.get("type") == "attack" and legal_move.get("attack_count", 0) > 0:
                                            chosen = open_move
                                            break
                                        elif open_move.get("type") == "to_ep" and legal_move.get("to_ep", 0):
                                            chosen = open_move
                                            break
                            if chosen:
                                break
                except Exception:
                    pass  # Fall back to general strategy

            # Fall back to general strategy if opening book didn't provide a move
            if chosen is None:
                chosen = pick_fn(moves, player, game_state)

            if chosen is None:
                break

            # Track turn changes
            if move_type == "idlecmd" and chosen.get("type") == "to_ep":
                turn_count += 1

            # Execute move — chain responses use respond_chain(), others use do_move_raw()
            try:
                if chosen.get("type") == "chain":
                    idx = chosen.get("index", -1)
                    if idx >= 0:
                        result = instance.respond_chain("activate", card_idx=idx)
                    else:
                        result = instance.respond_chain("pass")
                    response = {"ok": result.success}
                    if not result.success:
                        response["reason"] = result.error
                elif chosen.get("type") == "yes":
                    result = instance.respond_chain("activate")
                    response = {"ok": result.success}
                    if not result.success:
                        response["reason"] = result.error
                elif chosen.get("type") == "no":
                    result = instance.respond_chain("no")
                    response = {"ok": result.success}
                    if not result.success:
                        response["reason"] = result.error
                else:
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
                if chosen.get("type") not in ("to_ep", "to_ep_battle", "chain", "yes", "no"):
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
