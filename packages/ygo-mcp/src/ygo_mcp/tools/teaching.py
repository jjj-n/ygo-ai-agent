"""Teaching tools: explain_card, explain_move, quiz_position, check_answer.

These tools provide structured educational data that the LLM agent uses
to generate explanations and quiz questions for Yu-Gi-Oh! learners.
"""

from __future__ import annotations
import random
import uuid
from pathlib import Path
from ygo_engine_bridge import GameInstance
from ygo_engine_bridge.cards import CardDatabase
from ygo_engine_bridge.instance import _DEFAULT_CARD_DB
from ygo_engine_bridge.effects import (
    classify_effect,
    estimate_card_value,
    summarize_effect,
    get_effect_priority,
)
from ygo_engine_bridge.card_names_zh import get_card_id_by_chinese_name, search_chinese_names
from ygo_analysis.tools.find_best_line import (
    evaluate_position_sync,
    _extract_all_moves,
)

# Chinese card database path
_DEFAULT_ZH_CARD_DB = Path(_DEFAULT_CARD_DB).parent / "cards_zh.cdb"

# Lazy-loaded card database
_card_db = None

# Quiz storage (game_id -> quiz_id -> quiz data)
_quiz_store: dict[str, dict] = {}


def _get_card_db() -> CardDatabase:
    global _card_db
    if _card_db is None:
        zh_path = str(_DEFAULT_ZH_CARD_DB) if _DEFAULT_ZH_CARD_DB.exists() else None
        _card_db = CardDatabase(str(_DEFAULT_CARD_DB), zh_db_path=zh_path)
        _card_db.connect()
    return _card_db


# Card type display names
_TYPE_NAMES = {
    0x1: "怪兽",
    0x2: "魔法",
    0x4: "陷阱",
    0x10: "通常怪兽",
    0x20: "效果怪兽",
    0x40: "融合怪兽",
    0x80: "仪式怪兽",
    0x200: "灵摆怪兽",
    0x2000: "同调怪兽",
    0x800000: "超量怪兽",
    0x1000000: "灵摆",
    0x4000000: "连接怪兽",
}


def _get_type_name(card_type: int) -> str:
    """Get human-readable card type name."""
    names = []
    for flag, name in _TYPE_NAMES.items():
        if card_type & flag:
            names.append(name)
    return " / ".join(names) if names else "未知"


_STRATEGIC_TIPS = {
    "board_wipe": "全场破坏效果适合在对手场面优势时使用，可以一举扭转局面。",
    "destroy": "单体破坏效果用于去除对手关键怪兽或魔陷。",
    "draw": "抽卡效果增加手牌资源，但要注意手牌上限。",
    "search": "检索效果可以从卡组精确获取需要的卡，是展开的关键。",
    "negate": "无效效果是最强的互动手段，保留给对手的关键操作。",
    "summon_from_deck": "从卡组特召可以快速铺场，注意特召条件。",
    "summon_from_gy": "墓地特召利用已使用过的资源，注意墓地条件。",
    "special_summon": "特召不消耗通常召唤次数，合理利用可以多次展开。",
    "banish": "除外比破坏更彻底，对手难以回收。",
    "lp_recover": "回复LP可以延长对局，但通常优先级低于展开。",
    "burn": "LP伤害可以直接削减对手生命值，适合斩杀。",
    "protection": "保护效果让怪兽更难被去除，延长场面优势。",
    "bounce": "回手效果绕过破坏抗性，但对手可以再次使用。",
    "send_to_gy": "送墓效果可以触发墓地效果或清除对手资源。",
    "equip": "装备效果增强怪兽，但依赖装备卡的存续。",
    "counter_trap": "反击陷阱是最高速的互动，几乎无法被连锁。",
}


async def explain_card(
    card_name: str | None = None,
    card_id: int | None = None,
) -> dict:
    """详细讲解卡牌效果和用法。

    通过卡牌 ID 或卡名查询卡牌信息，分析其效果和战略价值。
    支持中英文卡名查询。

    Args:
        card_name: 卡牌名称 (与 card_id 二选一)，支持中文和英文
        card_id: 卡牌数据库 ID (与 card_name 二选一)

    Returns:
        卡牌详细信息和分析
    """
    try:
        db = _get_card_db()

        # Resolve card
        if card_id:
            info = db.get_card(card_id)
        elif card_name:
            # First try Chinese name lookup
            zh_card_id = get_card_id_by_chinese_name(card_name)
            if zh_card_id is not None:
                info = db.get_card(zh_card_id)
            else:
                # Try Chinese name partial search
                zh_results = search_chinese_names(card_name, limit=1)
                if zh_results:
                    info = db.get_card(zh_results[0]["id"])
                else:
                    # Fall back to English name search
                    results = db.search_cards(card_name, limit=1)
                    if results:
                        info = db.get_card(results[0]["id"])
                    else:
                        info = None
        else:
            return {"success": False, "error": "需要提供 card_name 或 card_id"}

        if not info:
            return {"success": False, "error": "未找到指定卡牌"}

        # Basic card info
        card_type = info.get("type", 0)
        effect_text = info.get("desc", "")

        card_data = {
            "name": info.get("name", ""),
            "card_id": info["id"],
            "type": _get_type_name(card_type),
            "type_raw": card_type,
            "effect_text": effect_text,
        }

        # Add Chinese name if available
        if card_name:
            zh_card_id = get_card_id_by_chinese_name(card_name)
            if zh_card_id is not None:
                card_data["name_zh"] = card_name

        # Monster-specific fields
        if card_type & 0x1:
            card_data["atk"] = info.get("atk", 0)
            card_data["def"] = info.get("def", 0)
            card_data["level"] = info.get("level", 0)
            from ygo_engine_bridge.instance import _ATTRIBUTE_NAMES, _RACE_NAMES
            attr = info.get("attribute", 0)
            race = info.get("race", 0)
            if attr:
                card_data["attribute"] = _ATTRIBUTE_NAMES.get(attr, str(attr))
            if race:
                card_data["race"] = _RACE_NAMES.get(race, str(race))

        # Effect analysis
        classification = classify_effect(effect_text)
        value = estimate_card_value(effect_text, card_type)
        priority = get_effect_priority(effect_text)

        # Strategic tips
        tips = []
        for kw in classification.get("keywords", []):
            if kw in _STRATEGIC_TIPS:
                tips.append(_STRATEGIC_TIPS[kw])

        analysis = {
            "keywords": classification["keywords"],
            "value_score": round(value, 1),
            "summary": classification["summary"],
            "activation_priority": priority,
            "strategic_tips": tips,
        }

        return {
            "success": True,
            "card": card_data,
            "analysis": analysis,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def explain_move(
    game_id: str,
    move_index: int | None = None,
) -> dict:
    """解释某个操作的意图和效果。

    获取当前可用操作，选择一个进行详细解释。
    通过模拟执行展示操作前后的状态变化。

    Args:
        game_id: 游戏实例 ID
        move_index: 要解释的操作索引。None 则选择最高优先级的操作。

    Returns:
        操作的详细解释
    """
    try:
        instance = GameInstance.get(game_id)
        state = instance.get_state()
        legal_moves = instance.get_legal_moves()

        if not legal_moves:
            return {"success": True, "message": "当前没有可用操作"}

        # Extract concrete moves
        all_moves = _extract_all_moves(legal_moves)
        if not all_moves:
            return {"success": True, "message": "没有具体操作可解释"}

        # Select move to explain
        if move_index is not None and 0 <= move_index < len(all_moves):
            chosen = all_moves[move_index]
        else:
            # Pick the first non-phase-change move
            chosen = next(
                (m for m in all_moves if m.get("type") not in ("to_ep", "to_bp", "to_ep_battle", "to_m2")),
                all_moves[0],
            )

        # Simulate the move
        clone = instance.clone()
        score_before = evaluate_position_sync(state, 1)
        state_before = state

        result = clone.do_move_raw(chosen)
        success = result.get("success", False) or result.get("ok", False)

        explanation = {
            "move": chosen,
            "move_type": chosen.get("type", "unknown"),
            "available_moves_count": len(all_moves),
        }

        if success:
            new_state = clone.get_state()
            score_after = evaluate_position_sync(new_state, 1)

            explanation.update({
                "score_before": round(score_before, 2),
                "score_after": round(score_after, 2),
                "score_change": round(score_after - score_before, 2),
                "state_before_summary": _summarize_state(state_before),
                "state_after_summary": _summarize_state(new_state),
            })
        else:
            explanation["error"] = result.get("reason", "操作执行失败")

        clone.close()

        clone.close()

        return {"success": True, **explanation}

    except KeyError:
        return {"success": False, "error": f"Game instance not found: {game_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _summarize_state(state: dict) -> dict:
    """Create a compact state summary for teaching."""
    player = state.get("player", {})
    opponent = state.get("opponent", {})

    my_monsters = [m.get("name", "?") for m in player.get("monster_zones", []) if m]
    opp_monsters = [m.get("name", "?") for m in opponent.get("monster_zones", []) if m]
    my_hand = len(player.get("hand", []))
    my_st = sum(1 for s in player.get("spell_trap_zones", []) if s)

    return {
        "turn": state.get("turn", 0),
        "phase": state.get("phase", ""),
        "my_lp": player.get("lp", 8000),
        "opp_lp": opponent.get("lp", 8000),
        "my_monsters": my_monsters,
        "opp_monsters": opp_monsters,
        "my_hand_count": my_hand,
        "my_spell_traps": my_st,
    }


async def quiz_position(
    game_id: str,
    player: int = 1,
    difficulty: str = "medium",
) -> dict:
    """基于当前局面出题。

    生成教学用的选择题，考察对局面的理解。
    题目类型包括：最优操作选择、威胁识别、资源计算等。

    Args:
        game_id: 游戏实例 ID
        player: 出题针对的玩家 (1 或 2)
        difficulty: 难度 ("easy", "medium", "hard")

    Returns:
        题目数据（含选项和正确答案）
    """
    try:
        instance = GameInstance.get(game_id)
        state = instance.get_state(player_pov=player)
        legal_moves = instance.get_legal_moves()
        score = evaluate_position_sync(state, player)

        # Determine quiz type based on game state
        player_data = state.get("player", {})
        opponent_data = state.get("opponent", {})

        my_monsters = [m for m in player_data.get("monster_zones", []) if m]
        opp_monsters = [m for m in opponent_data.get("monster_zones", []) if m]
        my_hand = player_data.get("hand", [])

        quiz_types = []
        if legal_moves:
            quiz_types.append("best_move")
        if opp_monsters:
            quiz_types.append("threat_identification")
        if my_hand:
            quiz_types.append("resource_count")
        if not quiz_types:
            quiz_types.append("resource_count")

        quiz_type = random.choice(quiz_types)
        quiz_id = str(uuid.uuid4())[:8]

        quiz_data = {
            "quiz_id": quiz_id,
            "quiz_type": quiz_type,
            "difficulty": difficulty,
            "game_id": game_id,
        }

        if quiz_type == "best_move":
            # Question: which move is best?
            all_moves = _extract_all_moves(legal_moves) if legal_moves else []
            # Filter out phase changes for cleaner options
            action_moves = [m for m in all_moves if m.get("type") not in ("to_ep", "to_bp", "to_ep_battle", "to_m2")]

            if len(action_moves) < 2:
                action_moves = all_moves[:4]

            if action_moves:
                # Evaluate each move
                move_scores = []
                for move in action_moves[:4]:
                    try:
                        clone = instance.clone()
                        result = clone.do_move_raw(move)
                        if result.get("success", False) or result.get("ok", False):
                            new_state = clone.get_state(player_pov=player)
                            move_score = evaluate_position_sync(new_state, player)
                            move_scores.append({"move": move, "score": move_score})
                        clone.close()
                    except Exception:
                        continue

                if move_scores:
                    move_scores.sort(key=lambda x: x["score"], reverse=True)
                    options = []
                    for i, ms in enumerate(move_scores):
                        label = chr(65 + i)  # A, B, C, D
                        move_desc = ms["move"].get("desc", ms["move"].get("type", "未知"))
                        options.append({"label": label, "description": move_desc, "move": ms["move"]})

                    correct_idx = 0  # The highest-scored move
                    quiz_data.update({
                        "question_context": {
                            "turn": state.get("turn", 0),
                            "phase": state.get("phase", ""),
                            "my_monsters": [m.get("name", "?") for m in my_monsters],
                            "opp_monsters": [m.get("name", "?") for m in opp_monsters],
                            "my_hand_count": len(my_hand),
                            "score": round(score, 1),
                        },
                        "options": options,
                        "correct_answer": options[correct_idx]["label"],
                        "explanation": f"选项 {options[correct_idx]['label']} 的评估分数最高 ({round(move_scores[correct_idx]['score'], 1)})",
                        "hint": "考虑哪个操作能最大程度改善你的局面分数。",
                    })

                    # Store quiz for check_answer
                    _quiz_store[f"{game_id}_{quiz_id}"] = quiz_data
                    return {"success": True, **quiz_data}

        elif quiz_type == "threat_identification":
            # Question: what's the biggest threat?
            if opp_monsters:
                # Find highest ATK opponent monster
                threats = sorted(opp_monsters, key=lambda m: m.get("atk", 0) or 0, reverse=True)
                options = []
                for i, m in enumerate(threats[:4]):
                    label = chr(65 + i)
                    options.append({
                        "label": label,
                        "description": f"{m.get('name', '?')} (ATK {m.get('atk', 0)})",
                    })

                quiz_data.update({
                    "question_context": {
                        "opp_monsters": [m.get("name", "?") for m in opp_monsters],
                        "my_lp": player_data.get("lp", 8000),
                    },
                    "options": options,
                    "correct_answer": options[0]["label"],
                    "explanation": f"{threats[0].get('name', '?')} 的 ATK 最高，是最大威胁。",
                    "hint": "ATK 最高的怪兽通常是最直接的威胁。",
                })

                _quiz_store[f"{game_id}_{quiz_id}"] = quiz_data
                return {"success": True, **quiz_data}

        # Fallback: resource count question
        quiz_data.update({
            "question_context": {
                "my_hand_count": len(my_hand),
                "my_monster_count": len(my_monsters),
                "opp_monster_count": len(opp_monsters),
                "my_lp": player_data.get("lp", 8000),
                "opp_lp": opponent_data.get("lp", 8000),
            },
            "options": [
                {"label": "A", "description": f"手牌 {len(my_hand)} 张"},
                {"label": "B", "description": f"场上怪兽 {len(my_monsters)} 只"},
                {"label": "C", "description": f"对手怪兽 {len(opp_monsters)} 只"},
            ],
            "correct_answer": "A",
            "explanation": f"当前手牌 {len(my_hand)} 张，我方场上 {len(my_monsters)} 只怪兽，对手场上 {len(opp_monsters)} 只怪兽。",
            "hint": "注意观察双方的资源差距。",
        })

        _quiz_store[f"{game_id}_{quiz_id}"] = quiz_data
        return {"success": True, **quiz_data}

    except KeyError:
        return {"success": False, "error": f"Game instance not found: {game_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def check_answer(
    game_id: str,
    quiz_id: str,
    answer: str,
) -> dict:
    """检查答案并解释。

    Args:
        game_id: 游戏实例 ID
        quiz_id: 题目 ID
        answer: 用户的答案 (如 "A", "B", "C", "D")

    Returns:
        答案是否正确，以及解释
    """
    try:
        key = f"{game_id}_{quiz_id}"
        quiz = _quiz_store.get(key)

        if not quiz:
            return {"success": False, "error": f"未找到题目 {quiz_id}，可能已过期"}

        answer = answer.strip().upper()
        correct = quiz.get("correct_answer", "").upper()
        is_correct = answer == correct

        return {
            "success": True,
            "correct": is_correct,
            "your_answer": answer,
            "correct_answer": correct,
            "explanation": quiz.get("explanation", ""),
            "quiz_type": quiz.get("quiz_type", ""),
            "next_suggestion": "尝试分析局面分数的变化来理解为什么这个操作最优。" if is_correct else "重新观察局面，考虑哪个操作能带来最大的分数提升。",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
