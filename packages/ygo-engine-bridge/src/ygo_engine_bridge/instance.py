"""Game instance management for YGO Engine Bridge."""

from __future__ import annotations
import uuid
from typing import Optional

from .process import EngineProcess, _DEFAULT_CARD_DB, _DEFAULT_SCRIPTS
from .state import GameState, Move, MoveResult, GameEvent, Card, PlayerState, FieldZone, ChainState
from .types import Phase, MoveType, DUEL_STATUS_AWAITING, DUEL_STATUS_END, DUEL_STATUS_CONTINUE


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
            Game state dictionary
        """
        if not self._initialized:
            raise RuntimeError("Game not initialized")

        response = self._engine.send_command({
            "cmd": "get_state",
            "player_pov": player_pov,
        })

        if not response.get("ok"):
            raise RuntimeError(f"Failed to get state: {response.get('reason')}")

        # Update internal state from response
        self._update_state(response.get("data", {}))

        # Return LLM-friendly format
        return self._state.to_llm_dict(player_pov, include_hidden)

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
                resp = self._engine.send_command({
                    "cmd": "respond_chain",
                    "action": "pass",
                })
            elif prompt_type == "select_place":
                # Auto-select first available zone from flag bitmask
                flag = prompt.get("flag", 0)
                player = prompt.get("player", 0)
                count = prompt.get("count", 1)
                loc, seq = self._pick_first_zone(flag)
                resp = self._engine.send_command({
                    "cmd": "do_move",
                    "move": {
                        "type": "place",
                        "player": player,
                        "count": count,
                        "location": loc,
                        "sequence": seq,
                    },
                })
            elif prompt_type in ("select_effectyn", "select_yesno"):
                # Auto-respond "no" - safe for vanilla cards, correct default for auto_play
                resp = self._engine.send_command({
                    "cmd": "respond_chain",
                    "action": "no",
                })
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
        response = self._engine.send_command({
            "cmd": "respond_chain",
            "action": action,
            "card_idx": card_idx,
        })

        if not response.get("ok"):
            return MoveResult(success=False, error=response.get("reason"))

        data = response.get("data", {})
        self._track_state(data)

        return MoveResult(success=True, new_state=self._state)

    def close(self):
        """Close the game instance and stop the engine."""
        self._engine.stop()
        if self.game_id in self._registry:
            del self._registry[self.game_id]

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
