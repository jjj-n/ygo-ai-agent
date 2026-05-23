"""Opening book: predefined opening sequences for common deck strategies.

The opening book provides optimal first-turn sequences for different deck
archetypes. When the game is in early turns (turn 1-2), the opening book
is consulted before falling back to the general strategy.

Sequences are stored as lists of move dicts that can be executed directly.
The book matches based on available cards in hand/field.
"""

from __future__ import annotations
from typing import Optional


# Opening sequences keyed by strategy type
# Each entry: (condition_fn, sequence)
# condition_fn(hand_codes, field_state) -> bool
# sequence: list of move dicts to execute in order

_OPENING_BOOK: dict[str, list[tuple[callable, list[dict]]]] = {
    "aggressive": [],
    "control": [],
    "combo": [],
}


def _has_card_type(hand_codes: list[int], card_type: int) -> bool:
    """Check if hand contains a card of given type."""
    from ygo_battle.tools.auto_play import _card_type
    for code in hand_codes:
        if _card_type(code) & card_type:
            return True
    return False


def _has_high_atk_monster(hand_codes: list[int], min_atk: int = 1800) -> bool:
    """Check if hand contains a monster with ATK >= min_atk."""
    from ygo_battle.tools.auto_play import _card_atk, _is_monster
    for code in hand_codes:
        if _is_monster(code) and _card_atk(code) >= min_atk:
            return True
    return False


def _has_search_spell(hand_codes: list[int]) -> bool:
    """Check if hand contains a search/recovery spell."""
    from ygo_engine_bridge.effects import get_effect_priority
    from ygo_battle.tools.auto_play import _is_spell
    for code in hand_codes:
        if _is_spell(code):
            try:
                from ygo_battle.tools.auto_play import _get_card_db
                db = _get_card_db()
                info = db.get_card(code)
                if info:
                    effect_text = info.get("desc", "")
                    priority = get_effect_priority(effect_text)
                    if priority >= 70:  # search/recovery level
                        return True
            except Exception:
                pass
    return False


def _has_trap_card(hand_codes: list[int]) -> bool:
    """Check if hand contains a trap card."""
    from ygo_battle.tools.auto_play import _is_trap
    for code in hand_codes:
        if _is_trap(code):
            return True
    return False


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
    # Only use opening book in turns 1-2
    if turn > 2:
        return None

    # Get available moves from field_state
    # This is a simplified version — the actual implementation would
    # need to check idlecmd/battlecmd to know what's available

    return None  # Fall back to general strategy


def get_opening_sequence(
    strategy: str,
    hand_codes: list[int],
    turn: int,
) -> list[dict] | None:
    """Get a complete opening sequence from the book.

    Args:
        strategy: Strategy name
        hand_codes: Card codes in hand
        turn: Current turn number

    Returns:
        A list of moves to execute, or None if no matching sequence.
    """
    if turn > 2:
        return None

    # Aggressive opening: summon highest ATK level<=4, then set traps
    if strategy == "aggressive":
        if _has_high_atk_monster(hand_codes):
            return [
                {"type": "summon", "index": 0},  # Will be resolved by strategy
                {"type": "to_bp"},
                {"type": "attack", "index": 0},
                {"type": "to_ep"},
            ]

    # Control opening: set traps first, then summon if safe
    elif strategy == "control":
        if _has_trap_card(hand_codes):
            return [
                {"type": "sset", "index": 0},
                {"type": "to_ep"},
            ]

    # Combo opening: look for special summon opportunities
    elif strategy == "combo":
        if _has_card_type(hand_codes, 0x20):  # Effect monsters
            return [
                {"type": "spsummon", "index": 0},
                {"type": "summon", "index": 0},
                {"type": "to_bp"},
                {"type": "attack", "index": 0},
                {"type": "to_ep"},
            ]

    return None


def is_opening_turn(turn: int) -> bool:
    """Check if we're still in the opening phase."""
    return turn <= 2
