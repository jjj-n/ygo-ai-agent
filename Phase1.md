# YGO-AI-Platform

基于 ygopro-core 的 AI 游戏王对战与智能助手，通过 MCP 协议与 Claude Code 集成。让大语言模型能够理解游戏王规则、分析对局局面、执行合法操作，并自主进行策略决策与自动对战。

---

## 特性

- **局面实时查询** — 通过 MCP 工具获取完整游戏快照，包括双方生命值、手牌、场上怪兽/魔法/陷阱、墓地、除外区等全部信息
- **合法操作推荐** — 自动枚举当前回合所有合法操作（召唤、特殊召唤、发动效果、攻击宣言等），帮助 LLM 做出正确决策
- **规则自动判断** — 由 ygopro-core 规则引擎处理所有游戏规则验证，确保每一步操作都符合官方规则
- **AI 辅助决策** — 内置局面评估函数与最优路线搜索，支持沙盒模拟推演未来局面
- **自动对战系统** — 支持 AI vs AI 自动对战，可配置不同人格策略（激进型 / 控制型 / 连击型）
- **可扩展的 MCP 工具生态** — 四个独立 MCP Server 各司其职，新增功能只需添加新的 MCP Server 目录并注册
- **完整的卡牌数据库** — 兼容 ProjectIgnis/BabelCDB（14,000+ 张卡）与 edo9300/ygopro-scripts（9000+ 个 Lua 脚本）

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                   Agent Layer                            │
│              Claude Code (ReAct Loop)                    │
│         LLM 思考 → 选择工具 → 执行 → 观察              │
└──────────────┬──────────────────────────────────────────┘
               │ MCP Protocol (JSON-RPC over stdio)
┌──────────────▼──────────────────────────────────────────┐
│                  MCP Tool Layer                          │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │
│  │ ygo-state │ │ygo-action │ │ygo-analysis│ │ygo-battle││
│  │ 局面查询  │ │ 操作执行  │ │ 分析评估  │ │ 自动对战 ││
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────┬────┘ │
└────────┼─────────────┼─────────────┼─────────────┼──────┘
         │             │             │             │
┌────────▼─────────────▼─────────────▼─────────────▼──────┐
│                 Engine Bridge                            │
│        ygo-engine-bridge (Python Library)                │
│   EngineProcess ─ JSON stdin/stdout ─ GameInstance       │
└──────────────────────┬──────────────────────────────────┘
                       │ Subprocess + JSON
┌──────────────────────▼──────────────────────────────────┐
│                   Rule Engine                            │
│            ygopro-engine (C++ Wrapper)                   │
│         ┌─────────────────────────────┐                  │
│         │   ygopro-core (ocgcore)     │                  │
│         │   规则引擎 + Lua 脚本执行   │                  │
│         └─────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

**数据流**：Claude Code 作为 Agent 通过 ReAct 循环运行。当需要了解游戏状态时，它通过 MCP 协议调用 `ygo-state` 的工具；需要执行操作时调用 `ygo-action`；需要分析局面时调用 `ygo-analysis`；需要自动对战时调用 `ygo-battle`。每个 MCP Server 内部通过 `ygo-engine-bridge` Python 库与 ygopro-engine C++ 子进程通信，引擎再调用 ygopro-core 规则引擎验证所有操作的合法性。**LLM 负责思考，规则引擎负责验证，MCP 负责连接。**

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| Agent | Claude Code | ReAct 循环、自然语言理解与决策 |
| MCP Protocol | Python MCP SDK (`mcp>=1.0.0`) | 工具注册、JSON-RPC 通信 |
| 数据验证 | Pydantic (`pydantic>=2.0.0`) | 类型安全的数据结构 |
| 规则引擎 | ygopro-core (C++) | 官方游戏王规则实现 |
| 引擎封装 | ygopro-engine (C++) | JSON stdin/stdout 协议桥接 |
| 卡牌脚本 | Lua (ygopro-scripts) | 卡牌效果逻辑 |
| 卡牌数据 | SQLite (cards.cdb) | 卡牌属性数据库 |
| 测试 | pytest + pytest-asyncio | 异步单元测试 |
| 构建 | CMake / Meson / Ninja | C++ 编译 |

---

## 前置条件

- **Python 3.10+**
- **Claude Code** — 已安装并配置
- **C++ 编译器** — Windows: Visual Studio Build Tools (MSVC)；Linux/macOS: GCC/Clang
- **Meson + Ninja** — 用于编译 ygopro-core
- **CMake** — 用于编译 ygopro-engine

---

## 安装

### 1. 克隆仓库

```bash
git clone <your-repo-url> ygo
cd ygo
```

### 2. 编译 ygopro-core（规则引擎）

```bash
# Windows: 使用 x64 Native Tools Command Prompt
cd libs/ygopro-core
meson setup build --default-library=static
ninja -C build
```

> 详细编译指南请参阅 [INSTALL_COMPILER.md](INSTALL_COMPILER.md)

### 3. 编译 ygopro-engine（JSON 协议封装）

```bash
cd libs/ygopro-engine
cmake -B build
cmake --build build
```

编译产物位于 `libs/ygopro-engine/build/ygopro-engine.exe`。

### 4. 准备卡牌数据

```bash
# 卡牌数据库 (SQLite)
# 已包含测试用 cards.cdb，完整版可从 ProjectIgnis/BabelCDB 获取
# 放置于 libs/ygopro-engine/build/cards.cdb

# Lua 脚本
# 已克隆 edo9300/ygopro-scripts 至 libs/ygopro-scripts/
```

### 5. 安装 Python 依赖

```bash
pip install -e ".[dev]"
```

### 6. 验证安装

```bash
# 运行全部测试
pytest

# 预期输出: 20 passed
```

---

## 配置与运行

### MCP Server 注册

项目通过 `.mcp.json` 注册四个 MCP Server。Claude Code 启动时会自动读取此文件并加载所有工具。

```json
{
  "mcpServers": {
    "ygo-state": {
      "command": "python",
      "args": ["-m", "ygo_state.server"],
      "env": {
        "YGOPRO_ENGINE_PATH": "./libs/ygopro-engine/build/ygopro-engine"
      }
    },
    "ygo-action": {
      "command": "python",
      "args": ["-m", "ygo_action.server"],
      "env": {
        "YGOPRO_ENGINE_PATH": "./libs/ygopro-engine/build/ygopro-engine"
      }
    },
    "ygo-analysis": {
      "command": "python",
      "args": ["-m", "ygo_analysis.server"],
      "env": {
        "YGOPRO_ENGINE_PATH": "./libs/ygopro-engine/build/ygopro-engine"
      }
    },
    "ygo-battle": {
      "command": "python",
      "args": ["-m", "ygo_battle.server"],
      "env": {
        "YGOPRO_ENGINE_PATH": "./libs/ygopro-engine/build/ygopro-engine"
      }
    }
  }
}
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `YGOPRO_ENGINE_PATH` | ygopro-engine 可执行文件路径 | `./libs/ygopro-engine/build/ygopro-engine` |

### 启动方式

直接在项目根目录启动 Claude Code，MCP Server 会按需自动启动：

```bash
claude
```

---

## 使用指南

### 示例：让 Claude Code 分析局面并执行操作

在 Claude Code 中，你可以用自然语言与 AI 对话：

```
> 帮我初始化一局游戏王对局，然后查看当前局面

Claude: 我来帮你初始化对局并查看局面。
[调用 start_battle 工具]
[调用 get_game_state 工具]

当前局面：
- 双方生命值: 8000
- 当前回合: 第1回合，玩家1的抽牌阶段
- 手牌: 5张
- 场上: 空

> 我有哪些合法操作？

Claude: [调用 get_legal_moves 工具]

当前合法操作：
1. 通常召唤 "青眼白龙" (需要解放2只怪兽)
2. 覆盖一张魔法/陷阱卡
3. 结束回合

> 结束主要阶段，进入战斗阶段

Claude: [调用 execute_move 工具，参数: { "move_type": "phase_end" }]
```

### MCP 工具一览

#### ygo-state — 局面查询

| 工具 | 说明 |
|------|------|
| `get_game_state` | 获取完整游戏快照（生命值、手牌、场上、墓地等） |
| `get_legal_moves` | 列出当前所有合法操作 |
| `get_zone_detail` | 查询指定区域的详细信息 |
| `get_card_info` | 查询卡牌属性（攻击力、效果、种族等） |

#### ygo-action — 操作执行

| 工具 | 说明 |
|------|------|
| `execute_move` | 执行一个游戏操作（召唤、发动效果等） |
| `respond_chain` | 连锁响应（对应对手的效果发动） |
| `declare_attack` | 攻击宣言（选择攻击怪兽与攻击目标） |

#### ygo-analysis — 分析评估

| 工具 | 说明 |
|------|------|
| `simulate_move` | 沙盒模拟：在不修改实际状态的情况下推演操作结果 |
| `evaluate_position` | 局面评分（0-100），评估当前优劣势 |
| `find_best_line` | 最优路线搜索，寻找未来 N 步的最佳操作序列 |

#### ygo-battle — 自动对战

| 工具 | 说明 |
|------|------|
| `start_battle` | 创建新的对局 |
| `ai_decide` | AI 策略决策（根据局面选择最优操作） |
| `auto_play` | 自动对战（AI vs AI 运行完整对局） |
| `get_battle_log` | 获取对战日志与历史记录 |

---

## 开发路线图

### Phase 0: 调研与设计 ✅

- ygopro-core API 分析与集成方案确定
- 项目架构设计（四层 MCP 插件架构）

### Phase 1: 基础框架 ✅

- 项目目录结构搭建
- pyproject.toml 配置（根项目 + 4 个子包）
- MCP Server 注册表 `.mcp.json`

### Phase 2: C++ 引擎封装 ✅

- ygopro-core 编译（静态库 libocgcore.a）
- ygopro-engine JSON 协议封装（stdin/stdout）
- 引擎启动与基本通信验证

### Phase 3: Python 引擎桥接 ✅

- EngineProcess 子进程管理
- GameInstance 游戏实例注册表
- CardDatabase 卡牌数据库查询
- 完整的类型系统（Phase, CardType, Zone, MoveType 等）

### Phase 4: ygo-state 局面查询 ✅

- 完整局面快照工具
- 合法操作枚举工具
- 区域详情与卡牌信息查询

### Phase 5: ygo-action 操作执行 ✅

- 操作执行工具
- 连锁响应工具
- 攻击宣言工具

### Phase 6: ygo-analysis 分析评估 ✅

- 沙盒模拟推演
- 局面评分函数
- 最优路线搜索

### Phase 7: ygo-battle 自动对战 ✅

- 对局创建与管理
- AI 决策引擎（支持多种人格策略）
- 自动对战与日志记录

### 进行中 / 未来计划

- **P2**: 完善 C++ Wrapper（get_legal_moves / do_move 完整实现、卡牌数据库加载）
- **P3**: MCP Server 端到端集成测试（连接真实引擎）
- **P4**: AI 策略优化（深度推演、LLM 集成决策）
- **P5**: 教学与复盘系统（ygo-teaching / ygo-replay MCP Server）

---

## 项目结构

```
ygo/
├── .mcp.json                          # MCP Server 注册表
├── CLAUDE.md                          # Claude Code 项目说明
├── README.md                          # 本文件
├── SESSION.md                         # 开发进度跟踪
├── INSTALL_COMPILER.md                # C++ 编译器安装指南
├── pyproject.toml                     # 根项目配置
│
├── libs/
│   ├── ygopro-core/                   # edo9300/ygopro-core 规则引擎源码
│   ├── ygopro-engine/                 # C++ JSON 协议封装
│   │   ├── src/                       #   bridge.cpp, protocol.cpp, main.cpp
│   │   └── build/                     #   编译产物 (ygopro-engine.exe, cards.cdb)
│   └── ygopro-scripts/                # Lua 卡牌效果脚本
│
├── packages/
│   ├── ygo-engine-bridge/             # Python 引擎桥接库
│   │   └── src/ygo_engine_bridge/
│   │       ├── types.py               #   类型定义 (Phase, CardType, Zone...)
│   │       ├── state.py               #   状态数据结构 (GameState, Card, Move)
│   │       ├── process.py             #   子进程管理 (EngineProcess)
│   │       ├── instance.py            #   游戏实例注册表 (GameInstance)
│   │       └── cards.py               #   卡牌数据库查询 (CardDatabase)
│   │
│   ├── ygo-state/                     # Phase 1: 局面查询 MCP Server
│   │   ├── src/ygo_state/
│   │   │   ├── server.py              #   MCP Server 入口
│   │   │   ├── tools/                 #   get_game_state, get_legal_moves...
│   │   │   └── prompts/               #   分析 Prompt 模板
│   │   └── tests/
│   │
│   ├── ygo-action/                    # Phase 2: 操作执行 MCP Server
│   │   ├── src/ygo_action/
│   │   │   ├── server.py              #   MCP Server 入口
│   │   │   ├── tools/                 #   execute_move, respond_chain...
│   │   │   └── prompts/               #   对战 Prompt 模板
│   │   └── tests/
│   │
│   ├── ygo-analysis/                  # Phase 3: 分析评估 MCP Server
│   │   ├── src/ygo_analysis/
│   │   │   ├── server.py              #   MCP Server 入口
│   │   │   ├── tools/                 #   simulate_move, evaluate_position...
│   │   │   └── prompts/               #   分析 Prompt 模板
│   │   └── tests/
│   │
│   └── ygo-battle/                    # Phase 4: 自动对战 MCP Server
│       ├── src/ygo_battle/
│       │   ├── server.py              #   MCP Server 入口
│       │   ├── tools/                 #   start_battle, ai_decide, auto_play...
│       │   └── prompts/               #   对战 Prompt 模板
│       └── tests/
│
└── data/                              # 卡牌数据库、对局录像等
```

---

## 贡献指南

### 添加新的 MCP Server

1. 在 `packages/` 下创建新目录，如 `packages/ygo-teaching/`
2. 按照现有结构创建 `src/ygo_teaching/server.py` 和 `tools/` 目录
3. 在 `.mcp.json` 中注册新的 MCP Server
4. 编写测试文件 `tests/test_teaching_tools.py`
5. 更新根 `pyproject.toml` 如需新增依赖

### 运行测试

```bash
# 运行全部测试
pytest

# 运行特定模块测试
pytest packages/ygo-state/tests/

# 运行单个测试文件
pytest packages/ygo-state/tests/test_state_tools.py -v
```

### 代码规范

- Python 代码使用 type hints
- MCP 工具函数需有清晰的 docstring
- 测试覆盖所有新增的 MCP 工具

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

ygopro-core 遵循其原始许可证 (AGPL-3.0)。使用本项目时请同时遵守 ygopro-core 的许可条款。
