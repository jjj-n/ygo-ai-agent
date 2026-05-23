"""Predefined deck archetypes for testing and multi-agent battles."""

from __future__ import annotations
import sqlite3
from pathlib import Path
from ygo_engine_bridge.process import _DEFAULT_CARD_DB


def _query_cards(sql: str, params: tuple = ()) -> list[int]:
    """Query card IDs from the database."""
    db_path = str(_DEFAULT_CARD_DB)
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(sql, params).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def _find_monsters(min_atk: int = 0, max_level: int = 4, count: int = 10) -> list[int]:
    """Find monster cards matching criteria."""
    return _query_cards(
        """SELECT id FROM datas
           WHERE type & 1
             AND NOT (type & 0x40)    -- not Fusion
             AND NOT (type & 0x2000)  -- not Synchro
             AND NOT (type & 0x800000) -- not XYZ
             AND NOT (type & 0x4000000) -- not Link
             AND (level & 0xFF) >= 1
             AND (level & 0xFF) <= ?
             AND atk >= ?
           ORDER BY atk DESC
           LIMIT ?""",
        (max_level, min_atk, count),
    )


def _find_spells(count: int = 6) -> list[int]:
    """Find spell cards for deck."""
    return _query_cards(
        """SELECT id FROM datas
           WHERE type & 2            -- TYPE_SPELL
             AND NOT (type & 4)      -- not TYPE_TRAP
             AND NOT (type & 0x20000) -- not Continuous
             AND NOT (type & 0x10000) -- not Quickplay
             AND NOT (type & 0x40000) -- not Equip
             AND NOT (type & 0x80000) -- not Field
             AND NOT (type & 0x80)    -- not Ritual
           LIMIT ?""",
        (count,),
    )


def _find_traps(count: int = 4) -> list[int]:
    """Find trap cards for deck."""
    return _query_cards(
        """SELECT id FROM datas
           WHERE type & 4            -- TYPE_TRAP
             AND NOT (type & 0x20000) -- not Continuous
             AND NOT (type & 0x100000) -- not Counter
           LIMIT ?""",
        (count,),
    )


# Deck archetypes
DECK_ARCHETYPES = {
    "aggro": {
        "description": "Aggressive deck with high-ATK monsters and burn spells",
        "strategy": "aggressive",
        "build": lambda: _find_monsters(min_atk=1800, max_level=4, count=14) + _find_spells(count=6),
    },
    "control": {
        "description": "Control deck with traps and medium-ATK monsters",
        "strategy": "control",
        "build": lambda: _find_monsters(min_atk=1400, max_level=4, count=10) + _find_traps(count=6) + _find_spells(count=4),
    },
    "combo": {
        "description": "Combo deck with special summons and effect monsters",
        "strategy": "combo",
        "build": lambda: _find_monsters(min_atk=1000, max_level=4, count=14) + _find_spells(count=6),
    },
    "balanced": {
        "description": "Balanced deck with mix of monsters, spells, and traps",
        "strategy": "aggressive",
        "build": lambda: _find_monsters(min_atk=1500, max_level=4, count=12) + _find_spells(count=4) + _find_traps(count=4),
    },
}


def get_deck(archetype: str) -> list[int]:
    """Get a deck by archetype name."""
    if archetype not in DECK_ARCHETYPES:
        raise ValueError(f"Unknown archetype: {archetype}. Available: {list(DECK_ARCHETYPES.keys())}")
    return DECK_ARCHETYPES[archetype]["build"]()


def get_strategy(archetype: str) -> str:
    """Get the recommended strategy for an archetype."""
    if archetype not in DECK_ARCHETYPES:
        return "aggressive"
    return DECK_ARCHETYPES[archetype]["strategy"]


def list_archetypes() -> dict:
    """List all available archetypes with descriptions."""
    return {
        name: {"description": info["description"], "strategy": info["strategy"]}
        for name, info in DECK_ARCHETYPES.items()
    }
