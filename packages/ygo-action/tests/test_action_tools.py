"""Tests for ygo-action MCP Server tools."""

import pytest


@pytest.mark.asyncio
async def test_respond_chain_invalid_action():
    """Test respond_chain with invalid action."""
    from ygo_action.tools.respond_chain import respond_chain

    result = await respond_chain("test", "invalid_action")
    assert result["success"] is False
    assert "invalid action" in result["error"].lower()


@pytest.mark.asyncio
async def test_execute_move_no_instance():
    """Test execute_move when no game instance exists."""
    from ygo_action.tools.execute_move import execute_move

    result = await execute_move("nonexistent", "summon", 1)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_respond_chain_no_instance():
    """Test respond_chain when no game instance exists."""
    from ygo_action.tools.respond_chain import respond_chain

    result = await respond_chain("nonexistent", "pass")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_declare_attack_no_instance():
    """Test declare_attack when no game instance exists."""
    from ygo_action.tools.declare_attack import declare_attack

    result = await declare_attack("nonexistent", 0)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_execute_move_valid_types():
    """Test that all valid move types are recognized."""
    from ygo_action.tools.execute_move import execute_move
    from ygo_engine_bridge import MoveType

    # All move types should be recognized (will fail on game instance, not move type)
    for move_type in MoveType:
        result = await execute_move("nonexistent", move_type.value, 1)
        # Should fail on "not found", not on "invalid move type"
        if not result["success"]:
            assert "invalid move type" not in result["error"].lower()
