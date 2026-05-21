"""Tests for ygo-battle MCP Server tools."""

import pytest


@pytest.mark.asyncio
async def test_start_battle_invalid_mode():
    """Test start_battle with invalid AI mode."""
    from ygo_battle.tools.start_battle import start_battle

    result = await start_battle([1]*50, [1]*50, ai_mode="invalid")
    assert result["success"] is False
    assert "invalid ai mode" in result["error"].lower()


@pytest.mark.asyncio
async def test_start_battle_small_deck():
    """Test start_battle with deck too small."""
    from ygo_battle.tools.start_battle import start_battle

    result = await start_battle([1]*10, [1]*10)
    assert result["success"] is False
    assert "40" in result["error"]


@pytest.mark.asyncio
async def test_ai_decide_invalid_strategy():
    """Test ai_decide with invalid strategy."""
    from ygo_battle.tools.ai_decide import ai_decide

    result = await ai_decide("test", strategy="invalid")
    assert result["success"] is False
    assert "invalid strategy" in result["error"].lower()


@pytest.mark.asyncio
async def test_ai_decide_no_instance():
    """Test ai_decide when no game instance exists."""
    from ygo_battle.tools.ai_decide import ai_decide

    result = await ai_decide("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_auto_play_no_instance():
    """Test auto_play when no game instance exists."""
    from ygo_battle.tools.auto_play import auto_play

    result = await auto_play("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_battle_log_no_instance():
    """Test get_battle_log when no game instance exists."""
    from ygo_battle.tools.get_battle_log import get_battle_log

    result = await get_battle_log("nonexistent")
    assert result["success"] is False
    assert "not found" in result["error"].lower()
