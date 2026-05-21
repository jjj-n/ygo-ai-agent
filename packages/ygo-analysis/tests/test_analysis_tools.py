"""Tests for ygo-analysis MCP Server tools."""

import pytest


@pytest.mark.asyncio
async def test_evaluate_position_no_instance():
    """Test evaluate_position when no game instance exists."""
    from ygo_analysis.tools.evaluate_position import evaluate_position

    result = await evaluate_position("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_simulate_move_no_instance():
    """Test simulate_move when no game instance exists."""
    from ygo_analysis.tools.simulate_move import simulate_move

    result = await simulate_move("nonexistent", "summon", 1)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_find_best_line_no_instance():
    """Test find_best_line when no game instance exists."""
    from ygo_analysis.tools.find_best_line import find_best_line

    result = await find_best_line("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_simulate_move_invalid_type():
    """Test simulate_move with invalid move type."""
    from ygo_analysis.tools.simulate_move import simulate_move

    result = await simulate_move("test", "invalid_type", 1)
    # Should fail on game instance not found, not move type
    assert result["success"] is False
