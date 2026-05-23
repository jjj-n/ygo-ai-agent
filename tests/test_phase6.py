"""Phase 6 Integration Tests: Effect Text, Beam Search, Extra Deck.

Tests the new features implemented in Phase 6:
- Effect text classification and value estimation
- Extra deck card exposure in game state
- Beam search in find_best_line
- Multi-strategy auto_play

Run with: python -m pytest tests/test_phase6.py -v
"""

import pytest
import asyncio


# ============================================================================
# Effect Classification Tests
# ============================================================================

class TestEffectClassification:
    """Test effects.py keyword detection."""

    def test_board_wipe_english(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("Destroy all monsters your opponent controls.")
        assert "board_wipe" in result["keywords"]
        assert result["value_score"] >= 9.0

    def test_board_wipe_chinese(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("破坏对方场上所有怪兽。")
        assert "board_wipe" in result["keywords"]

    def test_draw_effect(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("Draw 2 cards.")
        assert "draw" in result["keywords"]
        assert result["value_score"] >= 7.0

    def test_search_effect(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("Add 1 monster from your Deck to your hand.")
        assert "search" in result["keywords"]
        assert result["value_score"] >= 8.0

    def test_negate_effect(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("Negate the activation of a card, and if you do, destroy it.")
        assert "negate" in result["keywords"]
        assert result["value_score"] >= 8.5

    def test_special_summon(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("Special Summon this card from your hand.")
        assert "special_summon" in result["keywords"]

    def test_banish_effect(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("Banish 1 card your opponent controls.")
        assert "banish" in result["keywords"]

    def test_burn_effect(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("Inflict 500 damage to your opponent.")
        assert "burn" in result["keywords"]

    def test_protection_effect(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("This card cannot be destroyed by battle.")
        assert "protection" in result["keywords"]

    def test_empty_text(self):
        from ygo_engine_bridge.effects import classify_effect
        result = classify_effect("")
        assert result["keywords"] == []
        assert result["value_score"] == 0.0

    def test_estimate_card_value(self):
        from ygo_engine_bridge.effects import estimate_card_value
        value = estimate_card_value("Destroy all monsters your opponent controls.", 0x2)
        assert value >= 9.0

    def test_get_effect_priority(self):
        from ygo_engine_bridge.effects import get_effect_priority
        priority = get_effect_priority("Negate the activation of a card.")
        assert priority >= 85  # negate has high priority


# ============================================================================
# Integration Tests (require engine)
# ============================================================================

def _make_deck(base_cards: list[int], target_size: int = 45) -> list[int]:
    """Expand a deck to meet minimum size requirement."""
    if len(base_cards) >= target_size:
        return base_cards[:target_size]
    # Repeat cards to reach target size
    result = []
    while len(result) < target_size:
        result.extend(base_cards)
    return result[:target_size]


@pytest.mark.asyncio
async def test_auto_play_aggro_vs_control():
    """Test auto_play with aggressive vs control strategies."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=42)
    assert result["success"] is True, f"start_battle failed: {result}"

    game_id = result["game_id"]
    result = await auto_play(game_id, max_turns=30, strategy_p1="aggressive", strategy_p2="control")

    assert result["success"] is True, f"auto_play failed: {result}"
    assert result["winner"] in [1, 2, 0, -1], f"Invalid winner: {result['winner']}"
    assert result["turns"] > 0, "Game should have at least 1 turn"


@pytest.mark.asyncio
async def test_auto_play_combo_vs_aggro():
    """Test auto_play with combo vs aggressive strategies."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.decks import get_deck

    deck1 = _make_deck(get_deck("combo"))
    deck2 = _make_deck(get_deck("aggro"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=123)
    assert result["success"] is True

    game_id = result["game_id"]
    result = await auto_play(game_id, max_turns=30, strategy_p1="combo", strategy_p2="aggressive")

    assert result["success"] is True
    assert result["winner"] in [1, 2, 0, -1]


@pytest.mark.asyncio
async def test_game_state_has_extra_deck():
    """Test that get_state returns extra_deck field."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.decks import get_deck
    from ygo_engine_bridge import GameInstance

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=99)
    assert result["success"] is True

    game_id = result["game_id"]
    instance = GameInstance.get(game_id)
    state = instance.get_state(player_pov=1)

    # Check extra_deck field exists
    assert "extra_deck" in state.get("player", {}), "extra_deck field missing from player state"
    assert "extra_deck" in state.get("opponent", {}), "extra_deck field missing from opponent state"
    assert "extra_deck_count" in state.get("player", {}), "extra_deck_count field missing"


@pytest.mark.asyncio
async def test_game_state_has_effect_text():
    """Test that get_state returns effect_text for hand cards."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.decks import get_deck
    from ygo_engine_bridge import GameInstance

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=77)
    assert result["success"] is True

    game_id = result["game_id"]
    instance = GameInstance.get(game_id)
    state = instance.get_state(player_pov=1)

    # Check hand cards have effect_text
    hand = state.get("player", {}).get("hand", [])
    if hand:  # If there are cards in hand
        first_card = hand[0]
        assert "effect_text" in first_card, "effect_text field missing from hand card"


@pytest.mark.asyncio
async def test_find_best_line():
    """Test find_best_line returns valid results."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.decks import get_deck
    from ygo_analysis.tools.find_best_line import find_best_line

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=55)
    assert result["success"] is True

    game_id = result["game_id"]

    # Run one turn of auto_play to get to a state with moves
    await auto_play(game_id, max_turns=1, strategy_p1="aggressive", strategy_p2="control")

    # Try find_best_line
    lines = await find_best_line(game_id, player=1, max_depth=2, top_k=3)
    assert lines["success"] is True, f"find_best_line failed: {lines}"


@pytest.mark.asyncio
async def test_evaluate_position():
    """Test evaluate_position returns valid score."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.decks import get_deck
    from ygo_analysis.tools.evaluate_position import evaluate_position

    deck1 = _make_deck(get_deck("aggro"))
    deck2 = _make_deck(get_deck("control"))

    result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=33)
    assert result["success"] is True

    game_id = result["game_id"]

    # Run one turn
    await auto_play(game_id, max_turns=1, strategy_p1="aggressive", strategy_p2="control")

    # Evaluate position
    eval_result = await evaluate_position(game_id, player=1)
    assert eval_result["success"] is True
    assert 0 <= eval_result["score"] <= 100


# ============================================================================
# Multi-game Statistics Test
# ============================================================================

@pytest.mark.asyncio
async def test_multi_game_statistics():
    """Run multiple games and collect statistics."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play
    from ygo_battle.decks import get_deck

    strategies = ["aggressive", "control", "combo"]
    wins = {1: 0, 2: 0, 0: 0}
    total_games = 0

    for s1 in strategies:
        for s2 in strategies:
            for seed in [10, 20, 30]:
                deck1 = _make_deck(get_deck("aggro" if s1 == "aggressive" else s1))
                deck2 = _make_deck(get_deck("aggro" if s2 == "aggressive" else s2))

                result = await start_battle(deck_p1=deck1, deck_p2=deck2, seed=seed)
                if not result["success"]:
                    continue

                game_id = result["game_id"]
                result = await auto_play(game_id, max_turns=20, strategy_p1=s1, strategy_p2=s2)

                if result["success"]:
                    winner = result.get("winner", -1)
                    if winner in wins:
                        wins[winner] += 1
                    total_games += 1

    print(f"\nMulti-game statistics ({total_games} games):")
    print(f"  P1 wins: {wins[1]}")
    print(f"  P2 wins: {wins[2]}")
    print(f"  Draws: {wins[0]}")

    # At least some games should complete successfully
    assert total_games > 0, "No games completed successfully"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
