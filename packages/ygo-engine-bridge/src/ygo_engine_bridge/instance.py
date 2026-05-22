"""Game instance management for YGO Engine Bridge."""

from __future__ import annotations
import uuid
from typing import Optional

from .process import EngineProcess, _DEFAULT_CARD_DB, _DEFAULT_SCRIPTS
from .cards import CardDatabase
from .state import GameState, Move, MoveResult, GameEvent, Card, PlayerState, FieldZone, ChainState
from .types import Phase, MoveType, DUEL_STATUS_AWAITING, DUEL_STATUS_END, DUEL_STATUS_CONTINUE

# Lazy-loaded card database singleton
_card_db: Optional[CardDatabase] = None


def _get_card_db() -> CardDatabase:
    """Get or initialize the card database singleton."""
    global _card_db
    if _card_db is None:
        _card_db = CardDatabase(str(_DEFAULT_CARD_DB))
        _card_db.connect()
    return _card_db

# --- LLM-friendly name mappings ---

_PHASE_NAMES = {
    0x1: "draw", 0x2: "standby", 0x4: "main_phase_1",
    0x8: "battle_start", 0x10: "battle_step", 0x20: "damage",
    0x40: "damage_cal", 0x80: "main_phase_2", 0x100: "end",
}

_ATTRIBUTE_NAMES = {
    0x1: "EARTH", 0x2: "WATER", 0x4: "FIRE", 0x8: "WIND",
    0x10: "LIGHT", 0x20: "DARK", 0x40: "DIVINE",
}

_RACE_NAMES = {
    0x1: "WARRIOR", 0x2: "SPELLCASTER", 0x4: "FAIRY", 0x8: "FIEND",
    0x10: "ZOMBIE", 0x20: "MACHINE", 0x40: "AQUA", 0x80: "PYRO",
    0x100: "ROCK", 0x200: "WINGEDBEAST", 0x400: "PLANT", 0x800: "INSECT",
    0x1000: "THUNDER", 0x2000: "DRAGON", 0x4000: "BEAST", 0x8000: "BEASTWARRIOR",
    0x10000: "DINOSAUR", 0x20000: "FISH", 0x40000: "SEASERPENT", 0x80000: "REPTILE",
    0x100000: "PSYCHIC", 0x200000: "DIVINEBEAST", 0x400000: "CREATORGOD",
    0x800000: "WYRM", 0x1000000: "CYBERSE", 0x2000000: "ILLUSION",
}

_POSITION_NAMES = {
    0x1: "faceup_attack", 0x2: "facedown_attack",
    0x4: "faceup_defense", 0x8: "facedown_defense",
    0xa: "in_hand",  # hand cards (ygopro uses 0xa)
}


def _format_card(card_data: dict, zone: str = "") -> dict:
    """Transform raw engine card data into LLM-friendly format.

    Args:
        card_data: Raw card data from engine query
        zone: Zone context ("monster", "spell_trap", "hand", "graveyard", etc.)
              Used to correctly interpret position values.
    """
    code = card_data.get("code", 0)
    pos = card_data.get("position", 0)
    card_type = card_data.get("type", 0)

    # Engine returns pos=0xa for set spell/trap cards (same as in_hand).
    # Use zone context to disambiguate.
    if zone == "spell_trap" and pos == 0xa:
        pos = 0x8  # Treat as facedown_defense (set)
    elif zone == "monster" and pos == 0xa:
        pos = 0x8  # Facedown defense position

    result = {
        "code": code,
        "position": _POSITION_NAMES.get(pos, f"unknown(0x{pos:x})"),
        "is_faceup": bool(pos & 0x15) or pos == 0xa,  # faceup positions + hand
    }

    # Resolve card name from database (faceup cards or hand)
    if pos & 0x15 or pos == 0xa:  # faceup or in hand
        try:
            db = _get_card_db()
            info = db.get_card(code)
            if info and info.get("name"):
                result["name"] = info["name"]
        except Exception:
            pass  # DB not available — skip name resolution

    # Monster card (type & 0x1)
    if card_type & 0x1:
        result["atk"] = card_data.get("atk", 0)
        result["def"] = card_data.get("def", 0)
        result["level"] = card_data.get("level", 0)
        attr = card_data.get("attribute", 0)
        race = card_data.get("race", 0)
        if attr:
            result["attribute"] = _ATTRIBUTE_NAMES.get(attr, f"0x{attr:x}")
        if race:
            result["race"] = _RACE_NAMES.get(race, f"0x{race:x}")

    # Spell/Trap
    if card_type & 0x2:
        result["card_type"] = "spell"
    elif card_type & 0x4:
        result["card_type"] = "trap"

    return result


def _format_zone(cards: list, hide: bool = False, zone: str = "") -> list | dict:
    """Format a list of cards for a zone."""
    if hide:
        return {"count": len(cards), "cards": "hidden"}
    return [_format_card(c, zone=zone) for c in cards]


class GameInstance:
    """A game instance wrapping a ygopro-engine subprocess.

    Each GameInstance manages one duel. Instances are registered globally
    and can be retrieved by game_id.
    """

    _registry: dict[str, "GameInstance"] = {}

    def __init__(self, game_id: str, engine: EngineProcess):
        self.game_id = game_id
        self._engine = engine
        self._state: Optional[GameState] = None
        self._initialized = False
        self._last_idlecmd_player: int = 0
        self._move_history: list[dict] = []
        self._deck_p1: list[int] = []
        self._deck_p2: list[int] = []
        self._seed: int = 0

    @classmethod
    def create(
        cls,
        deck_p1: list[int],
        deck_p2: list[int],
        engine_path: Optional[str] = None,
        card_db_path: Optional[str] = None,
        scripts_path: Optional[str] = None,
        seed: int = 0,
        flags: int = 0,
    ) -> "GameInstance":
        """Create a new game instance.

        Args:
            deck_p1: Card IDs for player 1's deck
            deck_p2: Card IDs for player 2's deck
            engine_path: Path to ygopro-engine binary (default: auto-detect)
            card_db_path: Path to cards.cdb (default: auto-detect)
            scripts_path: Path to Lua scripts (default: auto-detect)
            seed: Random seed (0 for random)
            flags: Duel mode flags

        Returns:
            New GameInstance
        """
        game_id = str(uuid.uuid4())[:8]
        engine = EngineProcess(engine_path)
        engine.start(
            card_db_path or str(_DEFAULT_CARD_DB),
            scripts_path or str(_DEFAULT_SCRIPTS),
        )

        instance = cls(game_id, engine)
        cls._registry[game_id] = instance

        # Store creation params for cloning
        instance._deck_p1 = list(deck_p1)
        instance._deck_p2 = list(deck_p2)
        instance._seed = seed

        # Initialize the duel
        response = engine.send_command({
            "cmd": "init",
            "deck_p1": deck_p1,
            "deck_p2": deck_p2,
            "seed": seed,
            "flags": flags,
        })

        if not response.get("ok"):
            raise RuntimeError(f"Failed to initialize duel: {response.get('reason')}")

        instance._initialized = True
        instance._state = GameState(turn=1, current_player=1)
        return instance

    @classmethod
    def get(cls, game_id: str) -> "GameInstance":
        """Get an existing game instance by ID.

        Args:
            game_id: The game instance ID

        Returns:
            The GameInstance

        Raises:
            KeyError: If game_id not found
        """
        if game_id not in cls._registry:
            raise KeyError(f"Game instance not found: {game_id}")
        return cls._registry[game_id]

    @classmethod
    def list_instances(cls) -> list[str]:
        """List all active game instance IDs."""
        return list(cls._registry.keys())

    def get_state(self, player_pov: int = 1, include_hidden: bool = False) -> dict:
        """Get current game state as LLM-friendly dictionary.

        Args:
            player_pov: Which player's perspective (1 or 2)
            include_hidden: Whether to include opponent's hidden info

        Returns:
            Game state dictionary with card names, attributes, positions, etc.
        """
        if not self._initialized:
            raise RuntimeError("Game not initialized")

        response = self._engine.send_command({
            "cmd": "get_state",
            "player_pov": player_pov,
        })

        if not response.get("ok"):
            raise RuntimeError(f"Failed to get state: {response.get('reason')}")

        data = response.get("data", {})

        # Update internal tracking state
        self._update_state(data)

        # Transform into LLM-friendly format
        my_key = f"player{player_pov}"
        opp_key = f"player{2 if player_pov == 1 else 1}"

        lp = data.get("lp", {})
        counts = data.get("counts", {})
        zones = data.get("zones", {})
        phase_raw = data.get("phase", 0) or 0x4  # default to main_phase_1 if 0
        current_player = data.get("current_player", 0)

        def build_player_state(pkey: str, hide_hand: bool) -> dict:
            pzones = zones.get(pkey, {})
            pcounts = counts.get(pkey, {})
            return {
                "lp": lp.get(pkey, 8000),
                "monster_zones": _format_zone(pzones.get("monster", []), zone="monster"),
                "spell_trap_zones": _format_zone(pzones.get("spell_trap", []), zone="spell_trap"),
                "field_spell": None,  # TODO: field spell zone
                "hand": _format_zone(pzones.get("hand", []), hide=hide_hand, zone="hand"),
                "graveyard": _format_zone(pzones.get("graveyard", []), zone="graveyard"),
                "banished": _format_zone(pzones.get("banished", []), zone="banished"),
                "deck_count": pcounts.get("deck", 0),
                "extra_deck_count": pcounts.get("extra", 0),
            }

        return {
            "turn": data.get("turn", 0),
            "phase": _PHASE_NAMES.get(phase_raw, f"unknown(0x{phase_raw:x})"),
            "current_player": current_player + 1,  # engine 0-based → 1-based
            "is_game_over": data.get("finished", False),
            "winner": data.get("winner", -1) if data.get("finished") else None,
            "player": build_player_state(my_key, hide_hand=False),
            "opponent": build_player_state(opp_key, hide_hand=not include_hidden),
            "chain": {"active": False},  # TODO: chain state from engine
        }

    def get_legal_moves(self) -> list[dict]:
        """Get all legal moves in the current position.

        Returns:
            List of legal move dictionaries
        """
        if not self._initialized:
            raise RuntimeError("Game not initialized")

        response = self._engine.send_command({"cmd": "get_legal_moves"})

        if not response.get("ok"):
            raise RuntimeError(f"Failed to get legal moves: {response.get('reason')}")

        moves = response.get("data", {}).get("moves", [])

        # Track state from moves (idlecmd tells us whose turn it is)
        if moves:
            move = moves[0]
            player = move.get("player")
            move_type = move.get("type")
            if player is not None:
                self._state.current_player = player + 1
                if move_type == "idlecmd" and player != self._last_idlecmd_player:
                    self._state.turn += 1
                    self._last_idlecmd_player = player

        return moves

    def do_move_raw(self, move: dict) -> dict:
        """Execute a move from a raw dict (pass-through to engine).

        Args:
            move: Move dict with 'type' and parameters, e.g.
                  {"type": "summon", "index": 0}
                  {"type": "sset", "index": 0}
                  {"type": "to_ep"}

        Returns:
            Engine response dict
        """
        if not self._initialized:
            raise RuntimeError("Game not initialized")

        response = self._engine.send_command({
            "cmd": "do_move",
            "move": move,
        })

        if response.get("ok"):
            self._move_history.append({"cmd": "do_move", "move": move})
            self._track_state(response.get("data", {}))
            self._auto_handle_prompts(response)

        return response

    def _auto_handle_prompts(self, response: dict):
        """Auto-handle prompts that don't need LLM decisions.

        Handles:
        - select_place: auto-select first available zone
        - select_chain with count=0: auto-pass empty chain windows
        - select_effectyn: auto-respond "no"
        - select_yesno: auto-respond "no"

        Updates response dict in-place so the caller sees the final state.
        """
        data = response.get("data", {})
        next_moves = data.get("next_moves", [])

        while next_moves:
            prompt = next_moves[0]
            prompt_type = prompt.get("type")

            if prompt_type == "select_chain":
                chain_count = prompt.get("count", 0)
                if chain_count > 0:
                    break  # Has real chains - let the caller decide
                cmd = {"cmd": "respond_chain", "action": "pass"}
                resp = self._engine.send_command(cmd)
                self._move_history.append(cmd)
            elif prompt_type == "select_place":
                # Auto-select first available zone from flag bitmask
                flag = prompt.get("flag", 0)
                player = prompt.get("player", 0)
                count = prompt.get("count", 1)
                loc, seq = self._pick_first_zone(flag)
                cmd = {"cmd": "do_move", "move": {
                    "type": "place",
                    "player": player,
                    "count": count,
                    "location": loc,
                    "sequence": seq,
                }}
                resp = self._engine.send_command(cmd)
                self._move_history.append(cmd)
            elif prompt_type in ("select_effectyn", "select_yesno"):
                # Auto-respond "no" - safe for vanilla cards, correct default for auto_play
                cmd = {"cmd": "respond_chain", "action": "no"}
                resp = self._engine.send_command(cmd)
                self._move_history.append(cmd)
            else:
                break  # Prompt needs LLM decision

            if not resp.get("ok"):
                break
            resp_data = resp.get("data", {})
            self._track_state(resp_data)
            next_moves = resp_data.get("next_moves", [])

        data["next_moves"] = next_moves

    @staticmethod
    def _pick_first_zone(flag: int) -> tuple[int, int]:
        """Pick the first available zone from a SELECT_PLACE flag bitmask.

        Flag layout (32-bit):
          bits 0-6:   player 0 MZONE (0-6)
          bits 8-15:  player 0 SZONE (0-7)
          bits 16-22: player 1 MZONE (0-6)
          bits 24-31: player 1 SZONE (0-7)

        Returns (location, sequence) where location is 4 (MZONE) or 8 (SZONE).
        """
        LOCATION_MZONE = 4
        LOCATION_SZONE = 8
        # Try player 0 MZONE first
        for seq in range(7):
            if not (flag & (1 << seq)):
                return (LOCATION_MZONE, seq)
        # Player 0 SZONE
        for seq in range(8):
            if not (flag & (1 << (seq + 8))):
                return (LOCATION_SZONE, seq)
        # Player 1 MZONE
        for seq in range(7):
            if not (flag & (1 << (seq + 16))):
                return (LOCATION_MZONE, seq)
        # Player 1 SZONE
        for seq in range(8):
            if not (flag & (1 << (seq + 24))):
                return (LOCATION_SZONE, seq)
        return (LOCATION_MZONE, 0)  # fallback

    def do_move(self, move: Move) -> MoveResult:
        """Execute a move.

        Args:
            move: The move to execute

        Returns:
            MoveResult with new state and events
        """
        if not self._initialized:
            raise RuntimeError("Game not initialized")

        response = self._engine.send_command({
            "cmd": "do_move",
            "move": move.to_engine_dict(),
        })

        if not response.get("ok"):
            return MoveResult(
                success=False,
                error=response.get("reason", "Unknown error"),
            )

        # Update state
        data = response.get("data", {})
        self._update_state(data.get("state", {}))

        # Parse events
        events = []
        for event_data in data.get("events", []):
            events.append(GameEvent(
                event_type=event_data.get("type", "unknown"),
                description=event_data.get("description", ""),
                player=event_data.get("player", 0),
            ))

        return MoveResult(
            success=True,
            new_state=self._state,
            events=events,
        )

    def respond_chain(self, action: str, card_idx: Optional[int] = None) -> MoveResult:
        """Respond to a chain prompt.

        Args:
            action: "activate", "negate", or "pass"
            card_idx: Card index (for activate/negate)

        Returns:
            MoveResult
        """
        cmd = {"cmd": "respond_chain", "action": action, "card_idx": card_idx}
        response = self._engine.send_command(cmd)

        if not response.get("ok"):
            return MoveResult(success=False, error=response.get("reason"))

        self._move_history.append(cmd)
        data = response.get("data", {})
        self._track_state(data)

        return MoveResult(success=True, new_state=self._state)

    def close(self):
        """Close the game instance and stop the engine."""
        self._engine.stop()
        if self.game_id in self._registry:
            del self._registry[self.game_id]

    def clone(self) -> "GameInstance":
        """Create a sandboxed clone of this game instance.

        Spawns a fresh engine with the same decks/seed and replays
        all moves to reproduce the current state. The clone is NOT
        registered in _registry — call .close() when done.

        Returns:
            A new GameInstance at the same game state.
        """
        clone_id = f"{self.game_id}_clone"
        engine = EngineProcess()
        engine.start(
            str(_DEFAULT_CARD_DB),
            str(_DEFAULT_SCRIPTS),
        )

        clone = GameInstance(clone_id, engine)
        clone._deck_p1 = list(self._deck_p1)
        clone._deck_p2 = list(self._deck_p2)
        clone._seed = self._seed

        # Initialize with same params
        response = engine.send_command({
            "cmd": "init",
            "deck_p1": self._deck_p1,
            "deck_p2": self._deck_p2,
            "seed": self._seed,
        })
        if not response.get("ok"):
            engine.stop()
            raise RuntimeError(f"Clone init failed: {response.get('reason')}")

        clone._initialized = True
        clone._state = GameState(turn=1, current_player=1)

        # Replay all moves (commands already include auto-handled prompts)
        for recorded in self._move_history:
            resp = engine.send_command(recorded)
            if not resp.get("ok"):
                break  # Stop replaying if a move fails (state diverged)
            clone._track_state(resp.get("data", {}))

        return clone

    def _update_state(self, data: dict):
        """Update internal state from engine response data."""
        if not self._state:
            self._state = GameState()

        # Update basic state
        if "turn" in data:
            self._state.turn = data["turn"]
        if "phase" in data:
            try:
                self._state.phase = Phase(data["phase"])
            except ValueError:
                pass
        if "current_player" in data:
            self._state.current_player = data["current_player"]
        if "is_game_over" in data:
            self._state.is_game_over = data["is_game_over"]
        if "winner" in data:
            self._state.winner = data.get("winner", -1)

    def _track_state(self, data: dict):
        """Track turn/phase/player from do_move/respond_chain response data.

        Detects turn transitions by watching for idlecmd prompts with
        a different player than the previous idlecmd.
        """
        if not self._state:
            self._state = GameState()

        # Track game over and winner
        if data.get("game_over"):
            self._state.is_game_over = True
        # Winner can be at top level (from cmd_do_move) or in events
        if "winner" in data and data["winner"] >= 0:
            self._state.winner = data["winner"]
        else:
            # Check events for MSG_WIN (type 5)
            for ev in data.get("events", []):
                if ev.get("type") == 5 and "winner" in ev:
                    self._state.winner = ev["winner"]
                    break

        # Track turn/phase from events (MSG_NEW_TURN=40, MSG_NEW_PHASE=41)
        for ev in data.get("events", []):
            ev_type = ev.get("type")
            if ev_type == 40:  # MSG_NEW_TURN
                self._state.turn += 1
                if "player" in ev:
                    self._state.current_player = ev["player"] + 1
            elif ev_type == 41:  # MSG_NEW_PHASE
                pass  # Phase tracking from events is informational

        # Also track current player from next_moves
        next_moves = data.get("next_moves", [])
        if next_moves:
            move = next_moves[0]
            player = move.get("player")
            if player is not None:
                self._state.current_player = player + 1  # engine uses 0-based

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
