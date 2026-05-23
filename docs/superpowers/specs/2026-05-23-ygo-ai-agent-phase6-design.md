# YGO AI Agent — Phase 6 设计文档

> 效果文本理解 + Combo Solver + 额外卡组感知

**日期**: 2026-05-23
**状态**: 已实现

---

## 1. 概述

### 1.1 目标

Phase 6 的核心目标是让 AI 能够：
1. **理解卡牌效果文本** — 解析效果关键词，评估卡牌战略价值
2. **搜索最优展开路线** — 使用 Beam Search 在游戏状态空间中搜索最优操作序列
3. **感知额外卡组** — 识别 Fusion/Synchro/XYZ/Link 怪兽，优先选择额外卡组召唤

### 1.2 核心改动

| 组件 | 改动 |
|---|---|
| `bridge.cpp` | 修复 TYPE_PENDULUM/LINK 常量错误 |
| `instance.py` | 暴露额外卡组卡牌详情，包含 effect_text |
| `effects.py` | 新增：效果文本解析工具 |
| `auto_play.py` | 额外卡组召唤意识，效果文本决策 |
| `find_best_line.py` | 从静态启发式重写为 Beam Search |
| `simulate_move.py` | 支持 depth > 1 多步模拟 |

---

## 2. 效果文本解析系统

### 2.1 设计理念

游戏王卡牌效果文本遵循固定的文本模式（如 "destroy all"、"draw 2 cards"、"negate the activation"）。通过关键词匹配而非完整 NLP，可以高效地分类效果并估算价值。

### 2.2 关键词检测

支持中英文关键词，分为以下类别：

| 类别 | 英文模式 | 中文模式 | 价值分数 |
|---|---|---|---|
| board_wipe | "destroy all" | "破坏.*全部" | 9.0-9.5 |
| destroy | "destroy 1" | "破坏.*1张" | 6.0 |
| draw | "draw 2 cards" | "抽.*卡" | 7.0 |
| search | "add 1...from Deck" | "从卡组.*加入手牌" | 8.0 |
| negate | "negate the activation" | "无效.*发动" | 8.5 |
| summon_from_deck | "special summon...from Deck" | "从卡组.*特殊召唤" | 8.0 |
| banish | "banish" | "除外" | 6.0 |
| burn | "inflict damage" | "给予.*伤害" | 5.5 |
| protection | "cannot be destroyed" | "不会被破坏" | 7.0 |

### 2.3 核心函数

```python
# packages/ygo-engine-bridge/src/ygo_engine_bridge/effects.py

def classify_effect(effect_text: str) -> dict:
    """分类卡牌效果。返回 keywords, value_score, summary"""

def estimate_card_value(effect_text: str, card_type: int) -> float:
    """估算战略价值 (0-10)"""

def get_effect_priority(effect_text: str) -> int:
    """获取发动优先级（用于多卡选择）"""

def summarize_effect(effect_text: str) -> str:
    """单行摘要"""
```

### 2.4 应用场景

1. **`_pick_best_activate_index()`** — 使用 `get_effect_priority()` 选择最优发动
2. **`_pick_best_sset_index()`** — 使用 `estimate_card_value()` 选择最优覆盖
3. **`evaluate_position()`** — 可用于评估场上怪兽的价值（ATK + 效果价值）

---

## 3. Beam Search 树搜索

### 3.1 为什么选择 Beam Search

| 算法 | 优点 | 缺点 |
|---|---|---|
| Alpha-Beta | 理论最优 | 需要两玩家交替结构，游戏王回合复杂 |
| Monte Carlo Tree Search | 适合不确定环境 | 需要大量模拟，clone 成本高 |
| **Beam Search** | 简单、可控、稳健 | 不保证全局最优 |

游戏王的回合结构（Main Phase → Battle Phase → End Phase）、连锁系统、非确定性因素（抽卡）使得 Beam Search 是最实用的选择。

### 3.2 算法流程

```
beam_search(root_state, player, depth, beam_width):
    beam = [(score, [], root_state)]  # (score, move_path, state)

    for d in range(depth):
        candidates = []
        for score, path, state in beam:
            moves = get_legal_moves(state)
            concrete_moves = extract_all_moves(moves)

            for move in concrete_moves[:beam_width]:
                clone = state.clone()
                result = clone.execute_move(move)
                if result.success:
                    new_state = clone.get_state()
                    new_score = evaluate_position_sync(new_state, player)
                    candidates.append((new_score, path + [move], new_state))
                clone.close()

        beam = top_k(candidates, beam_width)

    return beam
```

### 3.3 关键设计

- **`evaluate_position_sync()`** — 同步版本的评估函数，避免 MCP 异步开销
- **`_extract_all_moves()`** — 提取所有具体操作（包括多个索引），而非只取 index: 0
- **超时机制** — 默认 10 秒超时，避免搜索时间过长
- **Beam Width** — 默认 5，控制每层保留的状态数

### 3.4 性能考虑

- 每次 clone 需要 spawn 新进程并 replay 历史，O(n) 成本
- Beam Width 限制在 3-5，Depth 限制在 2-3
- 超时后回退到当前最优结果

---

## 4. 额外卡组感知

### 4.1 问题

ygopro-core 在初始化时自动将 Fusion/Synchro/XYZ/Link 卡牌从主卡组路由到额外卡组。但 Python bridge 之前只暴露 `extra_deck_count`，丢弃了实际卡牌数据。

### 4.2 解决方案

**C++ 层面** (bridge.cpp):
- 修复 TYPE_PENDULUM (0x1000000) 和 TYPE_LINK (0x4000000) 的常量错误

**Python 层面** (instance.py):
- `build_player_state()` 增加 `extra_deck` 字段
- 己方额外卡组可见，对手默认隐藏

**AI 层面** (auto_play.py):
- 新增 `_pick_best_spsummon_index()` 函数
- 优先选择额外卡组怪兽（Fusion/Synchro/XYZ/Link）中 ATK 最高的

### 4.3 卡牌类型常量

```python
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000
TYPE_PENDULUM = 0x1000000
EXTRA_DECK_TYPES = TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK
```

---

## 5. 文件清单

### 5.1 新增文件

| 文件 | 用途 |
|---|---|
| `packages/ygo-engine-bridge/src/ygo_engine_bridge/effects.py` | 效果文本解析 |
| `tests/test_phase6.py` | Phase 6 集成测试 |
| `Phase6.md` | Phase 6 开发文档 |
| `docs/superpowers/specs/2026-05-23-ygo-ai-agent-phase6-design.md` | 本文档 |

### 5.2 修改文件

| 文件 | 改动 |
|---|---|
| `libs/ygopro-engine/src/bridge.cpp` | 修复 TYPE_PENDULUM (line 49) 和 TYPE_LINK (line 58) 常量 |
| `packages/ygo-engine-bridge/src/ygo_engine_bridge/instance.py` | `build_player_state()` 增加 extra_deck 字段；`_format_card()` 增加 effect_text |
| `packages/ygo-battle/src/ygo_battle/tools/auto_play.py` | 新增 `_pick_best_spsummon_index()`、`_card_effect_value()` 等函数；策略函数使用效果文本决策 |
| `packages/ygo-analysis/src/ygo_analysis/tools/find_best_line.py` | 从静态启发式完全重写为 Beam Search |
| `packages/ygo-analysis/src/ygo_analysis/tools/simulate_move.py` | 支持 depth > 1 多步模拟 |

---

## 6. 测试方案

### 6.1 单元测试

- `TestEffectClassification` — 12 个测试覆盖所有关键词类别

### 6.2 集成测试

- `test_auto_play_aggro_vs_control` — aggressive vs control 对战
- `test_auto_play_combo_vs_aggro` — combo vs aggressive 对战
- `test_game_state_has_extra_deck` — 验证 extra_deck 字段
- `test_game_state_has_effect_text` — 验证 effect_text 字段
- `test_find_best_line` — 验证 Beam Search
- `test_evaluate_position` — 验证局面评估
- `test_multi_game_statistics` — 多局统计

### 6.3 运行测试

```bash
cd c:\Users\22956\Desktop\ygo
python -m pytest tests/test_phase6.py -v
```

---

## 7. 未来改进方向

1. **效果文本解析精度** — 目前基于关键词匹配，可以考虑使用 LLM 进行更精确的效果理解
2. **Beam Search 优化** — 添加 alpha-beta 剪枝或 Monte Carlo Tree Search
3. **开局库** — 预定义常见卡组的开局操作序列
4. **Agent 学习** — 从对局记录中学习策略
5. **连锁响应策略** — 目前自动 pass，可以添加连锁判断逻辑
