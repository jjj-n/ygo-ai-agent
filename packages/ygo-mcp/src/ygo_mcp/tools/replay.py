"""Replay tools: save_replay, load_replay, get_turn_state, analyze_mistakes, suggest_improvement.

Provides persistent game recording and post-game analysis capabilities.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from datetime import datetime

from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.cards import CardDatabase
from ygo_engine_bridge.process import EngineProcess, _DEFAULT_CARD_DB, _DEFAULT_SCRIPTS
from ygo_engine_bridge.card_names_zh import get_card_id_by_chinese_name, search_chinese_names
from ygo_analysis.tools.find_best_line import evaluate_position_sync

# Chinese card database path
_DEFAULT_ZH_CARD_DB = Path(_DEFAULT_CARD_DB).parent / "cards_zh.cdb"


# Default replay directory
_DEFAULT_REPLAY_DIR = Path(__file__).resolve().parents[4] / "data" / "replays"

# Cached replay instances for get_turn_state (replay_id -> GameInstance)
_replay_cache: dict[str, GameInstance] = {}


def _ensure_replay_dir(path: Path) -> Path:
    """Create replay directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generate_replay_id() -> str:
    """Generate a unique replay ID."""
    return f"replay_{int(time.time())}_{id(object()) % 10000:04d}"


async def save_replay(
    game_id: str,
    name: str | None = None,
    strategies: dict | None = None,
) -> dict:
    """保存对局录像。

    将当前游戏的完整操作记录保存到文件，用于后续复盘分析。

    Args:
        game_id: 游戏实例 ID
        name: 录像名称（可选）
        strategies: 双方策略 {"player1": "aggressive", "player2": "control"}（可选）

    Returns:
        保存结果，包含 replay_id 和文件路径
    """
    try:
        instance = GameInstance.get(game_id)

        # Get current state for result info
        state = instance.get_state()
        winner = state.get("winner", -1)
        turn = state.get("turn", 0)
        is_game_over = state.get("is_game_over", False)

        replay_id = _generate_replay_id()

        replay_data = {
            "replay_id": replay_id,
            "timestamp": datetime.now().isoformat(),
            "name": name or f"Game {game_id}",
            "game_id": game_id,
            "decks": {
                "player1": list(instance._deck_p1),
                "player2": list(instance._deck_p2),
            },
            "seed": instance._seed,
            "strategies": strategies or {},
            "moves": list(instance._move_history),
            "result": {
                "winner": winner,
                "turns": turn,
                "is_game_over": is_game_over,
            },
            "move_count": len(instance._move_history),
        }

        # Save to file
        replay_dir = _ensure_replay_dir(_DEFAULT_REPLAY_DIR)
        filepath = replay_dir / f"{replay_id}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(replay_data, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "replay_id": replay_id,
            "path": str(filepath),
            "move_count": len(instance._move_history),
            "result": replay_data["result"],
        }

    except KeyError:
        return {"success": False, "error": f"Game instance not found: {game_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def load_replay(
    replay_id: str | None = None,
    path: str | None = None,
) -> dict:
    """加载对局录像。

    Args:
        replay_id: 录像 ID（从 data/replays/ 目录加载）
        path: 录像文件的完整路径（与 replay_id 二选一）

    Returns:
        录像元数据
    """
    try:
        if path:
            filepath = Path(path)
        elif replay_id:
            filepath = _DEFAULT_REPLAY_DIR / f"{replay_id}.json"
        else:
            return {"success": False, "error": "需要提供 replay_id 或 path"}

        if not filepath.exists():
            return {"success": False, "error": f"录像文件不存在: {filepath}"}

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "success": True,
            "replay": {
                "replay_id": data.get("replay_id"),
                "timestamp": data.get("timestamp"),
                "name": data.get("name"),
                "decks": data.get("decks"),
                "seed": data.get("seed"),
                "strategies": data.get("strategies"),
                "result": data.get("result"),
                "move_count": data.get("move_count", len(data.get("moves", []))),
            },
        }

    except json.JSONDecodeError:
        return {"success": False, "error": "录像文件格式错误"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _load_replay_data(replay_id: str) -> dict | None:
    """Load replay data from file. Returns None if not found."""
    filepath = _DEFAULT_REPLAY_DIR / f"{replay_id}.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_or_create_replay_instance(replay_data: dict) -> GameInstance:
    """Get cached replay instance or create a new one."""
    replay_id = replay_data["replay_id"]

    if replay_id in _replay_cache:
        return _replay_cache[replay_id]

    # Create new instance from replay data
    decks = replay_data.get("decks", {})
    deck_p1 = decks.get("player1", [])
    deck_p2 = decks.get("player2", [])
    seed = replay_data.get("seed")

    engine = EngineProcess()
    engine.start(str(_DEFAULT_CARD_DB), str(_DEFAULT_SCRIPTS))

    instance = GameInstance(f"replay_{replay_id}", engine)
    instance._deck_p1 = deck_p1
    instance._deck_p2 = deck_p2
    instance._seed = seed

    response = engine.send_command({
        "cmd": "init",
        "deck_p1": deck_p1,
        "deck_p2": deck_p2,
        "seed": seed,
    })

    if not response.get("ok"):
        engine.stop()
        raise RuntimeError(f"Replay init failed: {response.get('reason')}")

    instance._initialized = True
    from ygo_engine_bridge.instance import GameState
    instance._state = GameState(turn=1, current_player=1)

    _replay_cache[replay_id] = instance
    return instance


async def get_turn_state(
    replay_id: str,
    turn: int,
    player_pov: int = 1,
) -> dict:
    """获取指定回合的游戏状态。

    通过重放录像中的操作序列，重建指定回合的场面。

    Args:
        replay_id: 录像 ID
        turn: 目标回合数
        player_pov: 视角玩家 (1 或 2)

    Returns:
        指定回合的状态和评估分数
    """
    try:
        replay_data = _load_replay_data(replay_id)
        if not replay_data:
            return {"success": False, "error": f"录像不存在: {replay_id}"}

        instance = _get_or_create_replay_instance(replay_data)
        moves = replay_data.get("moves", [])

        # Replay moves, tracking turn changes
        current_turn = 1
        move_idx = 0

        for i, cmd in enumerate(moves):
            # Send command to replay instance
            try:
                resp = instance._engine.send_command(cmd)
                if resp.get("ok"):
                    instance._track_state(resp.get("data", {}))
                    current_turn = instance._state.turn if instance._state else current_turn
                    move_idx = i + 1
                else:
                    break
            except Exception:
                break

            # Check if we've reached the target turn
            if current_turn >= turn:
                # We're at or past the target turn
                break

        # If we need to go to an exact turn, replay from start up to that turn
        if current_turn != turn:
            # Re-create instance and replay more carefully
            if replay_id in _replay_cache:
                _replay_cache[replay_id].close()
                del _replay_cache[replay_id]

            instance = _get_or_create_replay_instance(replay_data)
            current_turn = 1

            for i, cmd in enumerate(moves):
                try:
                    resp = instance._engine.send_command(cmd)
                    if resp.get("ok"):
                        instance._track_state(resp.get("data", {}))
                        new_turn = instance._state.turn if instance._state else current_turn
                        if new_turn > turn:
                            break
                        current_turn = new_turn
                    else:
                        break
                except Exception:
                    break

        # Get the state
        state = instance.get_state(player_pov=player_pov)
        score = evaluate_position_sync(state, player_pov)

        return {
            "success": True,
            "replay_id": replay_id,
            "requested_turn": turn,
            "actual_turn": current_turn,
            "state": state,
            "evaluation": round(score, 2),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def analyze_mistakes(
    replay_id: str,
    threshold: float = 10.0,
    player: int = 1,
) -> dict:
    """分析对局中的关键失误。

    重放录像，在每一步评估局面分数，找出分数大幅下降的操作。

    Args:
        replay_id: 录像 ID
        threshold: 判定为失误的分数下降阈值 (默认 10.0)
        player: 分析哪个玩家的失误 (1 或 2)

    Returns:
        失误列表和分析
    """
    try:
        replay_data = _load_replay_data(replay_id)
        if not replay_data:
            return {"success": False, "error": f"录像不存在: {replay_id}"}

        decks = replay_data.get("decks", {})
        deck_p1 = decks.get("player1", [])
        deck_p2 = decks.get("player2", [])
        seed = replay_data.get("seed")
        moves = replay_data.get("moves", [])

        # Create fresh instance
        engine = EngineProcess()
        engine.start(str(_DEFAULT_CARD_DB), str(_DEFAULT_SCRIPTS))

        instance = GameInstance(f"analyze_{replay_id}", engine)
        instance._deck_p1 = deck_p1
        instance._deck_p2 = deck_p2
        instance._seed = seed

        response = engine.send_command({
            "cmd": "init",
            "deck_p1": deck_p1,
            "deck_p2": deck_p2,
            "seed": seed,
        })

        if not response.get("ok"):
            engine.stop()
            return {"success": False, "error": f"Replay init failed: {response.get('reason')}"}

        instance._initialized = True
        from ygo_engine_bridge.instance import GameState
        instance._state = GameState(turn=1, current_player=1)

        # Walk through moves, tracking scores
        mistakes = []
        prev_score = 50.0
        current_turn = 1

        for i, cmd in enumerate(moves):
            # Get state before move
            try:
                state_before = instance.get_state(player_pov=player)
                score_before = evaluate_position_sync(state_before, player)
            except Exception:
                score_before = prev_score

            # Execute move
            try:
                resp = instance._engine.send_command(cmd)
                if resp.get("ok"):
                    instance._track_state(resp.get("data", {}))
                    current_turn = instance._state.turn if instance._state else current_turn
                else:
                    continue
            except Exception:
                continue

            # Get state after move
            try:
                state_after = instance.get_state(player_pov=player)
                score_after = evaluate_position_sync(state_after, player)
            except Exception:
                score_after = score_before

            # Check for significant score drop
            score_drop = score_before - score_after
            if score_drop >= threshold:
                # Get alternatives at this point
                alternatives = []
                try:
                    clone = instance.clone()
                    legal = clone.get_legal_moves()
                    if legal:
                        from ygo_analysis.tools.find_best_line import _extract_all_moves
                        alt_moves = _extract_all_moves(legal)
                        for alt in alt_moves[:3]:
                            try:
                                alt_clone = clone.clone()
                                alt_result = alt_clone.do_move_raw(alt)
                                if alt_result.get("success", False) or alt_result.get("ok", False):
                                    alt_state = alt_clone.get_state(player_pov=player)
                                    alt_score = evaluate_position_sync(alt_state, player)
                                    alternatives.append({
                                        "move": alt,
                                        "score": round(alt_score, 2),
                                    })
                                alt_clone.close()
                            except Exception:
                                continue
                    clone.close()
                except Exception:
                    pass

                mistakes.append({
                    "move_index": i,
                    "turn": current_turn,
                    "move": cmd.get("move", cmd),
                    "score_before": round(score_before, 2),
                    "score_after": round(score_after, 2),
                    "score_drop": round(score_drop, 2),
                    "alternatives": alternatives,
                })

            prev_score = score_after

        instance.close()

        return {
            "success": True,
            "replay_id": replay_id,
            "player": player,
            "threshold": threshold,
            "mistakes": mistakes,
            "total_mistakes": len(mistakes),
            "total_moves_analyzed": len(moves),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def suggest_improvement(
    replay_id: str,
    turn: int,
    player: int = 1,
) -> dict:
    """为指定回合提供改进建议。

    重建指定回合的状态，模拟所有可用操作，找出最优选择。

    Args:
        replay_id: 录像 ID
        turn: 目标回合
        player: 分析哪个玩家 (1 或 2)

    Returns:
        改进建议和替代操作排名
    """
    try:
        replay_data = _load_replay_data(replay_id)
        if not replay_data:
            return {"success": False, "error": f"录像不存在: {replay_id}"}

        decks = replay_data.get("decks", {})
        deck_p1 = decks.get("player1", [])
        deck_p2 = decks.get("player2", [])
        seed = replay_data.get("seed")
        moves = replay_data.get("moves", [])

        # Create fresh instance and replay to target turn
        engine = EngineProcess()
        engine.start(str(_DEFAULT_CARD_DB), str(_DEFAULT_SCRIPTS))

        instance = GameInstance(f"suggest_{replay_id}", engine)
        instance._deck_p1 = deck_p1
        instance._deck_p2 = deck_p2
        instance._seed = seed

        response = engine.send_command({
            "cmd": "init",
            "deck_p1": deck_p1,
            "deck_p2": deck_p2,
            "seed": seed,
        })

        if not response.get("ok"):
            engine.stop()
            return {"success": False, "error": f"Replay init failed: {response.get('reason')}"}

        instance._initialized = True
        from ygo_engine_bridge.instance import GameState
        instance._state = GameState(turn=1, current_player=1)

        # Replay to target turn
        current_turn = 1
        last_move_idx = 0

        for i, cmd in enumerate(moves):
            try:
                resp = instance._engine.send_command(cmd)
                if resp.get("ok"):
                    instance._track_state(resp.get("data", {}))
                    new_turn = instance._state.turn if instance._state else current_turn
                    if new_turn > turn:
                        break
                    current_turn = new_turn
                    last_move_idx = i
                else:
                    break
            except Exception:
                break

        # Get current state and legal moves
        state = instance.get_state(player_pov=player)
        current_score = evaluate_position_sync(state, player)

        try:
            legal = instance.get_legal_moves()
        except Exception:
            legal = []

        if not legal:
            instance.close()
            return {
                "success": True,
                "turn": current_turn,
                "message": "该回合没有可用操作",
                "current_score": round(current_score, 2),
            }

        # Simulate all alternatives
        from ygo_analysis.tools.find_best_line import _extract_all_moves
        all_moves = _extract_all_moves(legal)

        alternatives = []
        for move in all_moves:
            try:
                clone = instance.clone()
                result = clone.do_move_raw(move)
                if result.get("success", False) or result.get("ok", False):
                    alt_state = clone.get_state(player_pov=player)
                    alt_score = evaluate_position_sync(alt_state, player)
                    alternatives.append({
                        "move": move,
                        "score": round(alt_score, 2),
                        "improvement": round(alt_score - current_score, 2),
                    })
                clone.close()
            except Exception:
                continue

        # Sort by score
        alternatives.sort(key=lambda x: x["score"], reverse=True)

        # Find what was actually played
        actual_move = moves[last_move_idx] if last_move_idx < len(moves) else None

        instance.close()

        return {
            "success": True,
            "replay_id": replay_id,
            "turn": current_turn,
            "current_score": round(current_score, 2),
            "actual_move": actual_move.get("move", actual_move) if actual_move else None,
            "alternatives": alternatives[:5],
            "best_alternative": alternatives[0] if alternatives else None,
            "total_alternatives_evaluated": len(alternatives),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
