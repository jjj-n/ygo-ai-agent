"""Opening book: predefined opening sequences for common deck strategies.

The opening book provides optimal first-turn sequences for different deck
archetypes. When the game is in early turns (turn 1-2), the opening book
is consulted before falling back to the general strategy.

Sequences are stored as lists of move dicts that can be executed directly.
The book matches based on available cards in hand/field.
"""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge.effects import get_effect_priority, classify_effect


# Card type constants
TYPE_MONSTER = 0x1
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_NORMAL = 0x10
TYPE_EFFECT = 0x20
TYPE_FUSION = 0x40
TYPE_RITUAL = 0x80
TYPE_CONTINUOUS = 0x20000
TYPE_QUICKPLAY = 0x10000
TYPE_EQUIP = 0x40000
TYPE_FIELD = 0x80000
TYPE_COUNTER = 0x100000
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_PENDULUM = 0x1000000
TYPE_LINK = 0x4000000

EXTRA_DECK_TYPES = TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK


def _get_card_db():
    """Lazy-load card database."""
    from ygo_battle.tools.auto_play import _get_card_db
    return _get_card_db()


def _card_type(code: int) -> int:
    """Get card type flags."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("type", 0)
    except Exception:
        pass
    return 0


def _card_atk(code: int) -> int:
    """Get card ATK value."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("atk", 0) or 0
    except Exception:
        pass
    return 0


def _card_def(code: int) -> int:
    """Get card DEF value."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("def", 0) or 0
    except Exception:
        pass
    return 0


def _card_level(code: int) -> int:
    """Get card level/rank."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("level", 0) or 0
    except Exception:
        pass
    return 0


def _card_effect_text(code: int) -> str:
    """Get card effect text."""
    try:
        db = _get_card_db()
        info = db.get_card(code)
        if info:
            return info.get("desc", "")
    except Exception:
        pass
    return ""


def _is_monster(code: int) -> bool:
    """Check if card is a monster."""
    return bool(_card_type(code) & TYPE_MONSTER)


def _is_spell(code: int) -> bool:
    """Check if card is a spell."""
    return bool(_card_type(code) & TYPE_SPELL)


def _is_trap(code: int) -> bool:
    """Check if card is a trap."""
    return bool(_card_type(code) & TYPE_TRAP)


def _is_extra_deck(code: int) -> bool:
    """Check if card is an extra deck monster."""
    return bool(_card_type(code) & EXTRA_DECK_TYPES)


def _has_card_type(hand_codes: list[int], card_type: int) -> bool:
    """Check if hand contains a card of given type."""
    for code in hand_codes:
        if _card_type(code) & card_type:
            return True
    return False


def _count_card_type(hand_codes: list[int], card_type: int) -> int:
    """Count cards of given type in hand."""
    return sum(1 for code in hand_codes if _card_type(code) & card_type)


def _has_high_atk_monster(hand_codes: list[int], min_atk: int = 1800) -> bool:
    """Check if hand contains a monster with ATK >= min_atk."""
    for code in hand_codes:
        if _is_monster(code) and _card_atk(code) >= min_atk:
            return True
    return False


def _get_highest_atk_monster(hand_codes: list[int]) -> int | None:
    """Get the index of the highest ATK normal-summonable monster."""
    best_idx = None
    best_atk = -1
    for i, code in enumerate(hand_codes):
        if _is_monster(code) and _card_level(code) <= 4:
            atk = _card_atk(code)
            if atk > best_atk:
                best_atk = atk
                best_idx = i
    return best_idx


def _has_search_spell(hand_codes: list[int]) -> bool:
    """Check if hand contains a search/recovery spell."""
    for code in hand_codes:
        if _is_spell(code):
            effect_text = _card_effect_text(code)
            classification = classify_effect(effect_text)
            keywords = classification.get("keywords", [])
            if "search" in keywords or "draw" in keywords:
                return True
    return False


def _has_trap_card(hand_codes: list[int]) -> bool:
    """Check if hand contains a trap card."""
    for code in hand_codes:
        if _is_trap(code):
            return True
    return False


def _has_counter_trap(hand_codes: list[int]) -> bool:
    """Check if hand contains a counter trap."""
    for code in hand_codes:
        if _card_type(code) & TYPE_COUNTER:
            return True
    return False


def _has_destruction_trap(hand_codes: list[int]) -> bool:
    """Check if hand contains a destruction-type trap."""
    for code in hand_codes:
        if _is_trap(code):
            effect_text = _card_effect_text(code)
            classification = classify_effect(effect_text)
            keywords = classification.get("keywords", [])
            if "destroy" in keywords or "negate" in keywords:
                return True
    return False


def _has_ritual_spell(hand_codes: list[int]) -> bool:
    """Check if hand contains a ritual spell."""
    for code in hand_codes:
        if _card_type(code) & TYPE_RITUAL:
            return True
    return False


def _has_fusion_spell(hand_codes: list[int]) -> bool:
    """Check if hand contains a fusion spell."""
    for code in hand_codes:
        if _is_spell(code):
            effect_text = _card_effect_text(code)
            if "融合" in effect_text or "Fusion" in effect_text:
                return True
    return False


def _has_pendulum_monster(hand_codes: list[int]) -> bool:
    """Check if hand contains pendulum monsters."""
    for code in hand_codes:
        if _card_type(code) & TYPE_PENDULUM:
            return True
    return False


def _has_special_summon_effect(hand_codes: list[int]) -> bool:
    """Check if hand has a monster that can special summon itself."""
    for code in hand_codes:
        if _is_monster(code):
            effect_text = _card_effect_text(code)
            classification = classify_effect(effect_text)
            keywords = classification.get("keywords", [])
            if "special_summon" in keywords:
                return True
    return False


def _has_burn_effect(hand_codes: list[int]) -> bool:
    """Check if hand has burn (LP damage) effects."""
    for code in hand_codes:
        effect_text = _card_effect_text(code)
        classification = classify_effect(effect_text)
        keywords = classification.get("keywords", [])
        if "burn" in keywords:
            return True
    return False


def _has_protection_spell(hand_codes: list[int]) -> bool:
    """Check if hand has protection spells (equip, field)."""
    for code in hand_codes:
        ctype = _card_type(code)
        if ctype & (TYPE_EQUIP | TYPE_FIELD):
            return True
        if _is_spell(code):
            effect_text = _card_effect_text(code)
            classification = classify_effect(effect_text)
            keywords = classification.get("keywords", [])
            if "protection" in keywords:
                return True
    return False


# ============================================================================
# Opening sequences
# ============================================================================

def _aggro_opening_high_atk(hand_codes: list[int]) -> list[dict] | None:
    """Aggressive: summon highest ATK level<=4, attack, set traps."""
    if not _has_high_atk_monster(hand_codes, 1600):
        return None
    seq = [{"type": "summon", "index": 0}]
    if _has_trap_card(hand_codes):
        seq.append({"type": "sset", "index": 0})
    seq.extend([
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "to_ep"},
    ])
    return seq


def _aggro_opening_special_summon(hand_codes: list[int]) -> list[dict] | None:
    """Aggressive: special summon first, then normal summon, attack."""
    if not _has_special_summon_effect(hand_codes):
        return None
    if not _has_high_atk_monster(hand_codes, 1400):
        return None
    return [
        {"type": "spsummon", "index": 0},
        {"type": "summon", "index": 0},
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "attack", "index": 1},
        {"type": "to_ep"},
    ]


def _control_opening_traps(hand_codes: list[int]) -> list[dict] | None:
    """Control: set multiple traps, end turn."""
    trap_count = _count_card_type(hand_codes, TYPE_TRAP)
    if trap_count < 1:
        return None
    seq = []
    # Set up to 2 traps
    for i in range(min(trap_count, 2)):
        seq.append({"type": "sset", "index": 0})
    # If we have a monster, summon it for defense
    if _has_high_atk_monster(hand_codes, 1400):
        seq.append({"type": "mset", "index": 0})
    seq.append({"type": "to_ep"})
    return seq


def _control_opening_counter(hand_codes: list[int]) -> list[dict] | None:
    """Control: set counter traps, summon defensively."""
    if not _has_counter_trap(hand_codes):
        return None
    seq = [{"type": "sset", "index": 0}]
    if _has_high_atk_monster(hand_codes, 1500):
        seq.append({"type": "mset", "index": 0})
    seq.append({"type": "to_ep"})
    return seq


def _combo_opening_search(hand_codes: list[int]) -> list[dict] | None:
    """Combo: use search spell first, then summon."""
    if not _has_search_spell(hand_codes):
        return None
    return [
        {"type": "activate", "index": 0},  # Search spell
        {"type": "summon", "index": 0},
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "to_ep"},
    ]


def _combo_opening_double_summon(hand_codes: list[int]) -> list[dict] | None:
    """Combo: special summon + normal summon for board presence."""
    if not _has_special_summon_effect(hand_codes):
        return None
    monster_count = _count_card_type(hand_codes, TYPE_MONSTER)
    if monster_count < 2:
        return None
    return [
        {"type": "spsummon", "index": 0},
        {"type": "summon", "index": 0},
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "attack", "index": 1},
        {"type": "to_ep"},
    ]


def _ritual_opening(hand_codes: list[int]) -> list[dict] | None:
    """Ritual: use ritual spell to summon ritual monster."""
    if not _has_ritual_spell(hand_codes):
        return None
    if not _has_card_type(hand_codes, TYPE_RITUAL):
        return None
    return [
        {"type": "activate", "index": 0},  # Ritual spell
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "to_ep"},
    ]


def _pendulum_opening(hand_codes: list[int]) -> list[dict] | None:
    """Pendulum: set pendulum scales, then pendulum summon."""
    if not _has_pendulum_monster(hand_codes):
        return None
    pend_count = _count_card_type(hand_codes, TYPE_PENDULUM)
    if pend_count < 2:
        return None
    return [
        {"type": "activate", "index": 0},  # Set scale 1
        {"type": "activate", "index": 0},  # Set scale 2
        {"type": "spsummon", "index": 0},  # Pendulum summon
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "to_ep"},
    ]


def _burn_opening(hand_codes: list[int]) -> list[dict] | None:
    """Burn: use burn effects to deal LP damage."""
    if not _has_burn_effect(hand_codes):
        return None
    return [
        {"type": "activate", "index": 0},  # Burn effect
        {"type": "summon", "index": 0},
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "to_ep"},
    ]


def _stall_opening(hand_codes: list[int]) -> list[dict] | None:
    """Stall: set defensive cards, protect LP."""
    if not _has_protection_spell(hand_codes) and not _has_trap_card(hand_codes):
        return None
    seq = []
    if _has_trap_card(hand_codes):
        seq.append({"type": "sset", "index": 0})
    if _has_protection_spell(hand_codes):
        seq.append({"type": "activate", "index": 0})
    if _has_high_atk_monster(hand_codes, 1000):
        seq.append({"type": "mset", "index": 0})
    seq.append({"type": "to_ep"})
    return seq


def _otk_opening(hand_codes: list[int]) -> list[dict] | None:
    """OTK: maximize damage output for potential one-turn kill."""
    monster_count = _count_card_type(hand_codes, TYPE_MONSTER)
    if monster_count < 2:
        return None
    total_atk = sum(_card_atk(c) for c in hand_codes if _is_monster(c))
    if total_atk < 4000:  # Not enough for OTK
        return None
    seq = []
    if _has_special_summon_effect(hand_codes):
        seq.append({"type": "spsummon", "index": 0})
    seq.extend([
        {"type": "summon", "index": 0},
        {"type": "to_bp"},
        {"type": "attack", "index": 0},
        {"type": "attack", "index": 1},
        {"type": "to_ep"},
    ])
    return seq


# ============================================================================
# Opening book registry
# ============================================================================

# Each entry: (priority, condition_fn, sequence_generator)
# Higher priority = checked first
_OPENING_BOOK: list[tuple[int, str, str, callable]] = [
    # (priority, strategy, name, generator_fn)
    (100, "aggressive", "otk_setup", _otk_opening),
    (90, "aggressive", "special_summon_aggro", _aggro_opening_special_summon),
    (80, "aggressive", "high_atk_aggro", _aggro_opening_high_atk),
    (70, "combo", "double_summon", _combo_opening_double_summon),
    (60, "combo", "search_combo", _combo_opening_search),
    (50, "combo", "pendulum", _pendulum_opening),
    (40, "combo", "ritual", _ritual_opening),
    (30, "control", "counter_traps", _control_opening_counter),
    (20, "control", "trap_heavy", _control_opening_traps),
    (10, "control", "stall", _stall_opening),
    (5, "aggressive", "burn", _burn_opening),
]


def get_opening_sequence(
    strategy: str,
    hand_codes: list[int],
    turn: int,
) -> list[dict] | None:
    """Get a complete opening sequence from the book.

    Args:
        strategy: Strategy name (aggressive/control/combo)
        hand_codes: Card codes in hand
        turn: Current turn number

    Returns:
        A list of moves to execute, or None if no matching sequence.
    """
    if turn > 2:
        return None

    if not hand_codes:
        return None

    # Filter by strategy and sort by priority
    candidates = [
        (prio, name, gen_fn)
        for prio, strat, name, gen_fn in _OPENING_BOOK
        if strat == strategy
    ]
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Try each opening in priority order
    for prio, name, gen_fn in candidates:
        try:
            seq = gen_fn(hand_codes)
            if seq:
                return seq
        except Exception:
            continue

    # Fallback: try any strategy's opening
    all_candidates = sorted(_OPENING_BOOK, key=lambda x: x[0], reverse=True)
    for prio, strat, name, gen_fn in all_candidates:
        try:
            seq = gen_fn(hand_codes)
            if seq:
                return seq
        except Exception:
            continue

    return None


def get_opening_move(
    strategy: str,
    hand_codes: list[int],
    field_state: dict,
    turn: int,
    player: int,
) -> dict | None:
    """Get the next move from the opening book if applicable.

    Args:
        strategy: Strategy name (aggressive/control/combo)
        hand_codes: List of card codes in hand
        field_state: Current field state
        turn: Current turn number
        player: Current player (1 or 2)

    Returns:
        A move dict if the opening book has a suggestion, None otherwise.
    """
    if turn > 2:
        return None

    # Get opening sequence
    seq = get_opening_sequence(strategy, hand_codes, turn)
    if not seq:
        return None

    # Return the first move that could be valid
    # The caller will check against legal moves
    return seq[0] if seq else None


def is_opening_turn(turn: int) -> bool:
    """Check if we're still in the opening phase."""
    return turn <= 2


def get_opening_stats() -> dict:
    """Get statistics about the opening book.

    Returns:
        Dict with counts per strategy and total.
    """
    stats = {"aggressive": 0, "control": 0, "combo": 0, "total": 0}
    for _, strat, _, _ in _OPENING_BOOK:
        stats[strat] = stats.get(strat, 0) + 1
        stats["total"] += 1
    return stats
