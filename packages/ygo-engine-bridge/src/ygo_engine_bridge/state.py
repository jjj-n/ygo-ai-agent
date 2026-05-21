"""Game state data structures for YGO Engine Bridge."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .types import Phase, CardType, CardPosition, MoveType, Zone, Attribute, Race


@dataclass
class Card:
    """Represents a card in the game."""
    card_id: int
    name: str = ""
    name_en: str = ""
    card_type: CardType = CardType.MONSTER
    position: CardPosition = CardPosition.FACEUP_ATTACK
    is_faceup: bool = True
    counters: dict[str, int] = field(default_factory=dict)

    # Monster-specific
    atk: Optional[int] = None
    def_: Optional[int] = None
    level: Optional[int] = None
    attribute: Optional[Attribute] = None
    race: Optional[Race] = None
    effect_text: str = ""

    def to_llm_dict(self) -> dict:
        """Convert to LLM-friendly dictionary."""
        result = {
            "card_id": self.card_id,
            "name": self.name,
            "name_en": self.name_en,
            "position": self.position.value,
            "is_faceup": self.is_faceup,
        }

        if self.atk is not None:
            result["atk"] = self.atk
        if self.def_ is not None:
            result["def"] = self.def_
        if self.level is not None:
            result["level"] = self.level
        if self.attribute is not None:
            result["attribute"] = self.attribute.name
        if self.race is not None:
            result["race"] = self.race.name
        if self.effect_text:
            result["effect_text"] = self.effect_text
        if self.counters:
            result["counters"] = self.counters

        return result


@dataclass
class FieldZone:
    """A zone on the field (monster zone, spell/trap zone, etc.)."""
    card: Optional[Card] = None
    is_empty: bool = True

    def to_llm_dict(self) -> Optional[dict]:
        if self.is_empty or self.card is None:
            return None
        return self.card.to_llm_dict()


@dataclass
class PlayerState:
    """State for one player."""
    lp: int = 8000
    monster_zones: list[FieldZone] = field(default_factory=lambda: [FieldZone() for _ in range(6)])
    spell_trap_zones: list[FieldZone] = field(default_factory=lambda: [FieldZone() for _ in range(6)])
    field_spell: Optional[Card] = None
    hand: list[Card] = field(default_factory=list)
    graveyard: list[Card] = field(default_factory=list)
    banished: list[Card] = field(default_factory=list)
    deck_count: int = 0
    extra_deck: list[Card] = field(default_factory=list)

    def to_llm_dict(self, hide_hand: bool = False) -> dict:
        """Convert to LLM-friendly dictionary."""
        result = {
            "lp": self.lp,
            "monster_zones": [z.to_llm_dict() for z in self.monster_zones],
            "spell_trap_zones": [z.to_llm_dict() for z in self.spell_trap_zones],
            "field_spell": self.field_spell.to_llm_dict() if self.field_spell else None,
            "graveyard": [c.to_llm_dict() for c in self.graveyard],
            "banished": [c.to_llm_dict() for c in self.banished],
            "deck_count": self.deck_count,
            "extra_deck_count": len(self.extra_deck),
        }

        if hide_hand:
            result["hand"] = {"count": len(self.hand), "cards": "hidden"}
        else:
            result["hand"] = [c.to_llm_dict() for c in self.hand]

        return result


@dataclass
class ChainEntry:
    """An entry in the chain."""
    card: Card
    player: int
    effect_description: str = ""
    is_negated: bool = False


@dataclass
class ChainState:
    """Current chain state."""
    entries: list[ChainEntry] = field(default_factory=list)
    is_active: bool = False

    def to_llm_dict(self) -> dict:
        if not self.is_active:
            return {"active": False}
        return {
            "active": True,
            "entries": [
                {
                    "card": e.card.to_llm_dict(),
                    "player": e.player,
                    "effect": e.effect_description,
                    "negated": e.is_negated,
                }
                for e in self.entries
            ],
        }


@dataclass
class GameState:
    """Complete game state snapshot."""
    turn: int = 0
    phase: Phase = Phase.MAIN1
    current_player: int = 1

    player1: PlayerState = field(default_factory=PlayerState)
    player2: PlayerState = field(default_factory=PlayerState)

    chain: ChainState = field(default_factory=ChainState)
    last_actions: list[dict] = field(default_factory=list)

    is_game_over: bool = False
    winner: int = -1

    def to_llm_dict(self, player_pov: int = 1, include_hidden: bool = False) -> dict:
        """Convert to LLM-friendly dictionary.

        Args:
            player_pov: Which player's perspective (1 or 2)
            include_hidden: Whether to include opponent's hidden info
        """
        my_state = self.player1 if player_pov == 1 else self.player2
        opp_state = self.player2 if player_pov == 1 else self.player1

        return {
            "turn": self.turn,
            "phase": self.phase.value,
            "current_player": self.current_player,
            "is_game_over": self.is_game_over,
            "winner": self.winner if self.is_game_over else None,
            "player": my_state.to_llm_dict(hide_hand=False),
            "opponent": opp_state.to_llm_dict(hide_hand=not include_hidden),
            "chain": self.chain.to_llm_dict(),
            "last_actions": self.last_actions[-5:],  # Last 5 actions
        }


@dataclass
class Move:
    """A game move."""
    move_type: MoveType
    player: int
    source_zone: Optional[Zone] = None
    source_idx: Optional[int] = None
    target_zone: Optional[Zone] = None
    target_idx: Optional[int] = None
    materials: Optional[list[int]] = None
    declare_info: Optional[dict] = None

    def to_engine_dict(self) -> dict:
        """Convert to engine command format."""
        result = {
            "type": self.move_type.value,
            "player": self.player,
        }
        if self.source_zone is not None:
            result["source"] = self.source_zone.value
        if self.source_idx is not None:
            result["source_idx"] = self.source_idx
        if self.target_zone is not None:
            result["target"] = self.target_zone.value
        if self.target_idx is not None:
            result["target_idx"] = self.target_idx
        if self.materials is not None:
            result["materials"] = self.materials
        if self.declare_info is not None:
            result["declare_info"] = self.declare_info
        return result


@dataclass
class GameEvent:
    """An event that occurred during the game."""
    event_type: str
    description: str
    player: int
    card: Optional[Card] = None
    details: dict = field(default_factory=dict)


@dataclass
class MoveResult:
    """Result of executing a move."""
    success: bool
    new_state: Optional[GameState] = None
    events: list[GameEvent] = field(default_factory=list)
    legal_next_moves: list[Move] = field(default_factory=list)
    error: Optional[str] = None
