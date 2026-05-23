"""Phase 7 Integration Tests: Teaching Agent + Replay System.

Tests the new features implemented in Phase 7:
- explain_line: move sequence explanation
- explain_card: card analysis
- explain_move: single move explanation
- quiz_position / check_answer: teaching quizzes
- save_replay / load_replay: replay persistence
- get_turn_state: state reconstruction
- analyze_mistakes: post-game analysis
- suggest_improvement: improvement suggestions

Run with: python -m pytest tests/test_phase7.py -v
"""

import pytest
import asyncio
import os


def _make_deck(base_cards: list[int], target_size: int = 45) -> list[int]:
    """Expand a deck to meet minimum size requirement."""
    if len(base_cards) >= target_size:
        return base_cards[:target_size]
    result = []
    while len(result) < target_size:
        result.extend(base_cards)
    return result[:target_size]


# ============================================================================
# Teaching Tools Tests
# ============================================================================

@pytest.mark.asyncio
async def test_explain_card_by_name():
    """Test explain_card with a card name."""
    from ygo_mcp.tools.teaching import explain_card

    result = await explain_card(card_name="Blue-Eyes White Dragon")
    if not result.get("success"):
        # Try Chinese name
        result = await explain_card(card_name="青眼白龙")

    # Should find some card even if name differs
    assert result["success"] is True, f"explain_card failed: {result}"
    assert "card" in result
    assert "analysis" in result
    assert result["card"]["name"] != ""


@pytest.mark.asyncio
async def test_explain_card_by_id():
    """Test explain_card with a card ID."""
    from ygo_mcp.tools.teaching import explain_card
    from ygo_battle.decks import get_deck

    # Get a card ID from a deck
    deck = get_deck("aggro")
    if deck:
        result = await explain_card(card_id=deck[0])
        assert result["success"] is True
        assert "card" in result
        assert "analysis" in result
        assert "keywords" in result["analysis"]


@pytest.mark.asyncio
async def test_explain_move():
    """Test explain_move in an active game."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_mcp.tools.teaching import explain_move
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=42)
    assert result["success"] is True

    game_id = result["game_id"]
    result = await explain_move(game_id)

    assert result["success"] is True
    # Should have move info (or "no moves" message)
    assert "move" in result or "message" in result


@pytest.mark.asyncio
async def test_explain_line():
    """Test explain_line with auto search."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_analysis.tools.explain_line import explain_line
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=55)
    assert result["success"] is True

    game_id = result["game_id"]

    # Run one turn to get to a state with moves
    await auto_play(game_id, max_turns=1)

    result = await explain_line(game_id, player=1, max_depth=1)
    assert result["success"] is True
    assert "line" in result


# ============================================================================
# Quiz Tests
# ============================================================================

@pytest.mark.asyncio
async def test_quiz_position():
    """Test quiz_position generates valid quiz."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_mcp.tools.teaching import quiz_position
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=33)
    assert result["success"] is True

    game_id = result["game_id"]
    result = await quiz_position(game_id, player=1)

    assert result["success"] is True
    assert "quiz_id" in result
    assert "quiz_type" in result
    assert "options" in result
    assert "correct_answer" in result


@pytest.mark.asyncio
async def test_check_answer():
    """Test check_answer with correct and incorrect answers."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_mcp.tools.teaching import quiz_position, check_answer
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=77)
    assert result["success"] is True

    game_id = result["game_id"]

    # Generate quiz
    quiz = await quiz_position(game_id, player=1)
    assert quiz["success"] is True

    quiz_id = quiz["quiz_id"]
    correct = quiz["correct_answer"]

    # Check correct answer
    result = await check_answer(game_id, quiz_id, correct)
    assert result["success"] is True
    assert result["correct"] is True

    # Check incorrect answer
    wrong = "Z" if correct != "Z" else "A"
    result = await check_answer(game_id, quiz_id, wrong)
    assert result["success"] is True
    if wrong != correct:
        assert result["correct"] is False


# ============================================================================
# Replay Tests
# ============================================================================

@pytest.mark.asyncio
async def test_save_and_load_replay():
    """Test save_replay and load_replay round-trip."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_mcp.tools.replay import save_replay, load_replay
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=42)
    assert result["success"] is True

    game_id = result["game_id"]

    # Play a few turns
    await auto_play(game_id, max_turns=3)

    # Save replay
    save_result = await save_replay(
        game_id,
        name="Test Replay",
        strategies={"player1": "aggressive", "player2": "control"},
    )
    assert save_result["success"] is True
    assert "replay_id" in save_result
    assert "path" in save_result
    assert save_result["move_count"] > 0

    replay_id = save_result["replay_id"]

    # Load replay
    load_result = await load_replay(replay_id=replay_id)
    assert load_result["success"] is True
    assert load_result["replay"]["replay_id"] == replay_id
    assert load_result["replay"]["name"] == "Test Replay"

    # Cleanup
    try:
        os.remove(save_result["path"])
    except OSError:
        pass


@pytest.mark.asyncio
async def test_get_turn_state():
    """Test get_turn_state reconstructs a state."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_mcp.tools.replay import save_replay, get_turn_state
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=99)
    assert result["success"] is True

    game_id = result["game_id"]
    await auto_play(game_id, max_turns=2)

    # Save replay
    save_result = await save_replay(game_id, name="Turn State Test")
    assert save_result["success"] is True
    replay_id = save_result["replay_id"]

    # Get turn 1 state
    turn_result = await get_turn_state(replay_id, turn=1, player_pov=1)
    assert turn_result["success"] is True
    assert "state" in turn_result
    assert "evaluation" in turn_result

    # Cleanup
    try:
        os.remove(save_result["path"])
    except OSError:
        pass


@pytest.mark.asyncio
async def test_analyze_mistakes():
    """Test analyze_mistakes on a completed game."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_mcp.tools.replay import save_replay, analyze_mistakes
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=42)
    assert result["success"] is True

    game_id = result["game_id"]
    await auto_play(game_id, max_turns=5)

    # Save replay
    save_result = await save_replay(game_id, name="Mistakes Test")
    assert save_result["success"] is True
    replay_id = save_result["replay_id"]

    # Analyze mistakes
    analysis = await analyze_mistakes(replay_id, threshold=5.0, player=1)
    assert analysis["success"] is True
    assert "mistakes" in analysis
    assert "total_mistakes" in analysis
    assert "total_moves_analyzed" in analysis

    # Cleanup
    try:
        os.remove(save_result["path"])
    except OSError:
        pass


@pytest.mark.asyncio
async def test_suggest_improvement():
    """Test suggest_improvement for a specific turn."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_mcp.tools.replay import save_replay, suggest_improvement
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=42)
    assert result["success"] is True

    game_id = result["game_id"]
    await auto_play(game_id, max_turns=3)

    # Save replay
    save_result = await save_replay(game_id, name="Suggest Test")
    assert save_result["success"] is True
    replay_id = save_result["replay_id"]

    # Get improvement suggestions
    suggestion = await suggest_improvement(replay_id, turn=1, player=1)
    assert suggestion["success"] is True
    assert "current_score" in suggestion

    # Cleanup
    try:
        os.remove(save_result["path"])
    except OSError:
        pass


# ============================================================================
# get_battle_log Test
# ============================================================================

@pytest.mark.asyncio
async def test_get_battle_log_improved():
    """Test improved get_battle_log returns actual move history."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.tools.get_battle_log import get_battle_log
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=42)
    assert result["success"] is True

    game_id = result["game_id"]
    await auto_play(game_id, max_turns=2)

    # Get battle log
    log_result = await get_battle_log(game_id)
    assert log_result["success"] is True
    assert "log" in log_result
    assert log_result["move_count"] > 0
    assert len(log_result["log"]) > 0

    # Check log entries have descriptions
    first_entry = log_result["log"][0]
    assert "index" in first_entry
    assert "command" in first_entry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
