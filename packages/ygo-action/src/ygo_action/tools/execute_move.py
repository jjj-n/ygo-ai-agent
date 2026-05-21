"""Tool: execute_move - Execute a game move."""

from __future__ import annotations
from typing import Optional
from ygo_engine_bridge import GameInstance, Move, MoveType, Zone


async def execute_move(
    game_id: str,
    move_type: str,
    player: int,
    source_zone: Optional[str] = None,
    source_idx: Optional[int] = None,
    target_zone: Optional[str] = None,
    target_idx: Optional[int] = None,
    materials: Optional[list[int]] = None,
    declare_info: Optional[dict] = None,
) -> dict:
    """执行一个游戏操作。

    支持的操作类型：
    - summon: 通常召唤 (hand → monster_zone)
    - special_summon: 特殊召唤
    - activate_effect: 发动效果
    - set_spell: 覆盖魔法卡
    - set_trap: 覆盖陷阱卡
    - change_position: 改变表示形式
    - tribute: 解放
    - fusion: 融合召唤
    - synchro: 同调召唤
    - xyz: 超量召唤
    - link: 连接召唤
    - pendulum: 灵摆召唤
    - draw: 抽卡
    - phase_end: 结束阶段

    Args:
        game_id: 游戏实例 ID
        move_type: 操作类型
        player: 执行操作的玩家 (1 或 2)
        source_zone: 来源区域 (hand/graveyard/field/banished/extra)
        source_idx: 来源位置索引
        target_zone: 目标区域 (monster/spell_trap)
        target_idx: 目标位置索引
        materials: 素材列表 (融合/同调/超量/连接用)
        declare_info: 宣言信息 (效果发动时的选择)

    Returns:
        操作执行结果
    """
    try:
        instance = GameInstance.get(game_id)

        # Parse move type
        try:
            mt = MoveType(move_type)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid move type: {move_type}. "
                         f"Valid types: {', '.join([t.value for t in MoveType])}",
            }

        # Parse zones
        sz = Zone(source_zone) if source_zone else None
        tz = Zone(target_zone) if target_zone else None

        # Create move
        move = Move(
            move_type=mt,
            player=player,
            source_zone=sz,
            source_idx=source_idx,
            target_zone=tz,
            target_idx=target_idx,
            materials=materials,
            declare_info=declare_info,
        )

        # Execute
        result = instance.do_move(move)

        return {
            "success": result.success,
            "events": [
                {
                    "type": e.event_type,
                    "description": e.description,
                    "player": e.player,
                }
                for e in result.events
            ],
            "state": result.new_state.to_llm_dict(player) if result.new_state else None,
            "error": result.error,
        }

    except KeyError:
        return {
            "success": False,
            "error": f"Game instance not found: {game_id}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
