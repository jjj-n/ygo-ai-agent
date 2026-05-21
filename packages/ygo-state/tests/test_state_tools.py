"""Tests for ygo-state MCP Server tools."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_get_game_state_no_instance():
    """Test get_game_state when no game instance exists."""
    from ygo_state.tools.get_game_state import get_game_state

    result = await get_game_state("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_legal_moves_no_instance():
    """Test get_legal_moves when no game instance exists."""
    from ygo_state.tools.get_legal_moves import get_legal_moves

    result = await get_legal_moves("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_zone_detail_invalid_zone():
    """Test get_zone_detail with invalid zone."""
    from ygo_state.tools.get_zone_detail import get_zone_detail

    result = await get_zone_detail("test", "invalid_zone", 1)
    assert result["success"] is False
    assert "invalid zone" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_card_info_no_params():
    """Test get_card_info with no parameters."""
    from ygo_state.tools.get_card_info import get_card_info

    result = await get_card_info()
    assert result["success"] is False
    assert "must provide" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_zone_detail_valid_zones():
    """Test that all valid zones are accepted."""
    from ygo_state.tools.get_zone_detail import get_zone_detail

    valid_zones = ["monster", "spell_trap", "graveyard", "banished", "extra", "hand", "field_spell"]

    for zone in valid_zones:
        # Should not return "invalid zone" error (will return "not found" since no game exists)
        result = await get_zone_detail("nonexistent", zone, 1)
        # The error should be about the game not existing, not about invalid zone
        if not result["success"]:
            assert "invalid zone" not in result["error"].lower()
