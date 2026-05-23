"""Phase 8 Integration Tests: Chain Response Strategy + MCP Prompts.

Tests the new features implemented in Phase 8:
- Smart chain decisions based on effect priority
- Chain response format fix (respond_chain vs do_move_raw)
- MCP prompts registration

Run with: python -m pytest tests/test_phase8.py -v
"""

import pytest
import asyncio


def _make_deck(base_cards: list[int], target_size: int = 45) -> list[int]:
    """Expand a deck to meet minimum size requirement."""
    if len(base_cards) >= target_size:
        return base_cards[:target_size]
    result = []
    while len(result) < target_size:
        result.extend(base_cards)
    return result[:target_size]


# ============================================================================
# Chain Decision Tests
# ============================================================================

@pytest.mark.asyncio
async def test_decide_chain_with_high_priority():
    """Test that _decide_chain activates high-priority chainable cards."""
    from ygo_battle.tools.auto_play import _decide_chain

    # Simulate a select_chain prompt with a high-priority card (negate effect)
    # Card code 41420027 is Solemn Judgment (counter trap, priority ~100)
    moves = [
        {
            "type": "select_chain",
            "count": 1,
            "chains": [
                {"code": 41420027, "desc": "Solemn Judgment"},
            ],
        }
    ]

    result = _decide_chain(moves)
    assert result is not None
    assert result["type"] == "chain"
    assert result["index"] >= 0  # Should activate, not pass


@pytest.mark.asyncio
async def test_decide_chain_with_low_priority():
    """Test that _decide_chain passes on low-priority chainable cards."""
    from ygo_battle.tools.auto_play import _decide_chain

    # Simulate a select_chain with a low-priority card
    # Use a generic card code that likely has low priority
    moves = [
        {
            "type": "select_chain",
            "count": 1,
            "chains": [
                {"code": 0, "desc": "Unknown card"},  # Unknown = priority 0
            ],
        }
    ]

    result = _decide_chain(moves)
    assert result is not None
    assert result["type"] == "chain"
    assert result["index"] == -1  # Should pass


@pytest.mark.asyncio
async def test_decide_chain_with_no_chains():
    """Test that _decide_chain passes when count is 0."""
    from ygo_battle.tools.auto_play import _decide_chain

    moves = [
        {
            "type": "select_chain",
            "count": 0,
            "chains": [],
        }
    ]

    result = _decide_chain(moves)
    assert result is not None
    assert result["type"] == "chain"
    assert result["index"] == -1  # Should pass


@pytest.mark.asyncio
async def test_decide_chain_with_yesno():
    """Test that _decide_chain handles yesno prompts."""
    from ygo_battle.tools.auto_play import _decide_chain

    # yesno with unknown card should say no
    moves = [
        {
            "type": "yesno",
            "code": 0,
        }
    ]

    result = _decide_chain(moves)
    assert result is not None
    assert result["type"] == "no"


@pytest.mark.asyncio
async def test_decide_chain_with_no_chain_prompts():
    """Test that _decide_chain returns None when no chain prompts present."""
    from ygo_battle.tools.auto_play import _decide_chain

    moves = [
        {"type": "idlecmd", "summon_count": 1},
        {"type": "to_bp"},
    ]

    result = _decide_chain(moves)
    assert result is None


# ============================================================================
# Strategy Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_strategy_calls_decide_chain():
    """Test that strategy functions call _decide_chain before _handle_prompts."""
    from ygo_battle.tools.auto_play import _pick_move_aggressive

    # Create moves with a chain prompt
    moves = [
        {
            "type": "select_chain",
            "count": 0,
            "chains": [],
        },
        {
            "type": "idlecmd",
            "summon_count": 1,
            "summon_cards": [{"code": 0}],
        },
    ]

    # Should return chain pass response, not idlecmd
    result = _pick_move_aggressive(moves, 1)
    assert result is not None
    assert result["type"] == "chain"
    assert result["index"] == -1


# ============================================================================
# MCP Prompts Tests
# ============================================================================

def test_mcp_prompts_import():
    """Test that MCP prompts can be imported."""
    from ygo_mcp.prompts import ANALYSIS_PROMPT, BATTLE_PROMPT, TEACHING_PROMPT, AGENT_PROFILES

    assert len(ANALYSIS_PROMPT) > 0
    assert len(BATTLE_PROMPT) > 0
    assert len(TEACHING_PROMPT) > 0
    assert "aggressive" in AGENT_PROFILES
    assert "control" in AGENT_PROFILES
    assert "combo" in AGENT_PROFILES


def test_battle_prompt_formatting():
    """Test that BATTLE_PROMPT can be formatted with strategy profiles."""
    from ygo_mcp.prompts import BATTLE_PROMPT, AGENT_PROFILES

    for strategy, profile in AGENT_PROFILES.items():
        formatted = BATTLE_PROMPT.format(
            strategy=profile["strategy"],
            prompt=profile["prompt"],
        )
        assert len(formatted) > 0
        assert profile["strategy"] in formatted


@pytest.mark.asyncio
async def test_mcp_server_has_prompts():
    """Test that MCP server has prompt registrations."""
    from ygo_mcp.server import mcp

    # Check that prompts are registered
    prompts = await mcp.list_prompts()
    prompt_names = [p.name for p in prompts]

    assert "ygo_analysis_prompt" in prompt_names
    assert "ygo_battle_prompt" in prompt_names
    assert "ygo_teaching_prompt" in prompt_names


# ============================================================================
# Auto Play Integration Test
# ============================================================================

@pytest.mark.asyncio
async def test_auto_play_with_chain_strategy():
    """Test that auto_play runs successfully with chain strategy enabled."""
    from ygo_battle.tools.start_battle import start_battle
    from ygo_battle.tools.auto_play import auto_play

    # Create a deck with some chain-able cards
    base_deck = [
        41420027,  # Solemn Judgment
        41420027,
        84749824,  # Warning
        84749824,
        73628505,  # Terraforming
        73628505,
        10045474,  # Swords of Revealing Light
        10045474,
        53129443,  # Dark Hole
        53129443,
        24094653,  # Polymerization
        24094653,
        4031928,   # Change of Heart
        4031928,
        83764718,  # Reinforcement of the Army
        83764718,
        15025844,  # Upstart Goblin
        15025844,
        57953380,  # Card Destruction
        57953380,
        70231910,  # Giant Trunade
        70231910,
        29401950,  # Bottomless Trap Hole
        29401950,
        63102017,  # Compulsory Evacuation Device
        63102017,
        44095762,  # Mirror Force
        44095762,
        4206964,   # Trap Hole
        4206964,
        53582587,  # Torrential Tribute
        53582587,
        53046406,  # Heavy Storm
        53046406,
        5318639,   # Mystical Space Typhoon
        5318639,
        5318639,
        12580477,  # Raigeki
        12580477,
        97169186,  # Pot of Greed
        97169186,
        85991529,  # Graceful Charity
        85991529,
        37520316,  # Soul Exchange
        37520316,
    ]
    deck = _make_deck(base_deck, 45)

    result = await start_battle(deck, deck, seed=42)
    assert result["success"], f"start_battle failed: {result}"

    game_id = result["game_id"]

    # Run auto_play with aggressive vs control
    battle_result = await auto_play(
        game_id,
        max_turns=10,
        strategy_p1="aggressive",
        strategy_p2="control",
    )

    assert battle_result["success"], f"auto_play failed: {battle_result}"
    assert battle_result["game_over"] is True
    assert "log" in battle_result
    assert len(battle_result["log"]) > 0

    # Check that battle log contains some entries
    log = battle_result["log"]
    assert any(entry.get("event") == "battle_started" for entry in log)
    assert any(entry.get("event") == "game_over" for entry in log)
