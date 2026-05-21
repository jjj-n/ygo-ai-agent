"""Tool: ai_decide - AI decides the next move."""

from __future__ import annotations
from ygo_engine_bridge import GameInstance


# AI strategy prompts
AI_STRATEGIES = {
    "aggressive": {
        "name": "Aggressive",
        "description": "优先展开，快速削减对手 LP",
        "prompt": """你是一个激进型游戏王 AI。

策略原则：
- 优先召唤高攻击力怪兽
- 尽早进入战斗阶段
- 不惜代价削减对手 LP
- 忽略防守，全力进攻

当前局面：
{state}

请分析局面并选择最激进的操作。""",
    },
    "control": {
        "name": "Control",
        "description": "优先互动，积累资源优势",
        "prompt": """你是一个控制型游戏王 AI。

策略原则：
- 优先设置陷阱和互动手段
- 打断对手的关键展开
- 积累手牌和场上资源优势
- 稳扎稳打，不冒险

当前局面：
{state}

请分析局面并选择最稳妥的操作。""",
    },
    "combo": {
        "name": "Combo",
        "description": "寻找 OTK/FTK 组合",
        "prompt": """你是一个 combo 型游戏王 AI。

策略原则：
- 寻找一次性击杀 (OTK) 的机会
- 保留关键 combo 组件
- 在合适的时机爆发
- 计算伤害是否足够击杀

当前局面：
{state}

请分析局面并寻找 combo 机会。""",
    },
}


async def ai_decide(
    game_id: str,
    strategy: str = "aggressive",
    player: int = 1,
) -> dict:
    """AI 决策当前操作。

    根据指定的策略，分析当前局面并选择最优操作。

    Args:
        game_id: 游戏实例 ID
        strategy: AI 策略 (aggressive/control/combo)
        player: AI 控制的玩家 (1 或 2)

    Returns:
        AI 决策结果，包含推荐操作和分析
    """
    if strategy not in AI_STRATEGIES:
        return {
            "success": False,
            "error": f"Invalid strategy: {strategy}. Valid: {', '.join(AI_STRATEGIES.keys())}",
        }

    try:
        instance = GameInstance.get(game_id)

        # Get current state
        state = instance.get_state(player_pov=player)

        # Get legal moves
        legal_moves = instance.get_legal_moves()

        # Build analysis based on strategy
        strategy_info = AI_STRATEGIES[strategy]

        # Simple AI decision logic
        # In a full implementation, this would use the LLM to analyze
        # For now, use basic heuristics
        recommended_move = None
        analysis = ""

        if not legal_moves:
            analysis = "没有可用的操作"
        else:
            # Find the "best" move based on strategy
            if strategy == "aggressive":
                # Prioritize attacks and summons
                for move in legal_moves:
                    if move.get("type") == "attack":
                        recommended_move = move
                        analysis = "选择攻击以削减对手 LP"
                        break
                    elif move.get("type") == "summon":
                        recommended_move = move
                        analysis = "召唤怪兽准备进攻"
                        break
            elif strategy == "control":
                # Prioritize traps and negation
                for move in legal_moves:
                    if move.get("type") == "set_trap":
                        recommended_move = move
                        analysis = "设置陷阱准备互动"
                        break
                    elif move.get("type") == "activate_effect":
                        recommended_move = move
                        analysis = "发动效果控制场面"
                        break
            elif strategy == "combo":
                # Look for special summons
                for move in legal_moves:
                    if move.get("type") == "special_summon":
                        recommended_move = move
                        analysis = "特殊召唤展开 combo"
                        break

            # Fallback: first available move
            if recommended_move is None and legal_moves:
                recommended_move = legal_moves[0]
                analysis = f"执行可用操作: {recommended_move.get('type', 'unknown')}"

        return {
            "success": True,
            "strategy": strategy,
            "strategy_description": strategy_info["description"],
            "recommended_move": recommended_move,
            "analysis": analysis,
            "legal_moves_count": len(legal_moves),
            "state": state,
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
