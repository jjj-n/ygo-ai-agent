# YGO AI Agent — Demo 运行指南与开发路线图

> 最后更新: 2026-05-21

---

## 当前状态

**Demo 可运行。** 核心引擎层、Python Bridge、MCP Server 全部打通。

```
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code (Agent Layer)                     │
│              ReAct Loop: 观察 → 思考 → 工具调用 → 行动            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ MCP Protocol
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MCP Tool Layer (15 Tools)                      │
│  ygo-state(4)  ygo-action(3)  ygo-analysis(3)  ygo-battle(4)    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Python subprocess
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              ygo-engine-bridge (Python 共享库)                    │
│          GameInstance · EngineProcess · JSON 协议                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │ stdin/stdout JSON
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              ygopro-engine (C++ 子进程)                           │
│          ocgcore 规则引擎 · 完整 Master Rule 实现                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Demo 运行步骤

### 前置条件

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | 3.11+ | MCP Server 运行环境 |
| Visual Studio | 2026 (v18) | C++ 编译器 (MSVC 1451) |
| cmake | 3.20+ | C++ 构建系统 |
| ninja | 任意 | C++ 构建后端 |
| mcp | 1.27+ | MCP Python SDK |

### 第一步: 编译 C++ 引擎

```bash
cd libs/ygopro-engine

# 配置 (首次)
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release

# 编译
cmake --build build
```

产出: `libs/ygopro-engine/build/ygopro-engine.exe` (约 2.4MB)

### 第二步: 验证引擎可用

```bash
echo '{"cmd":"init","deck_p1":[89631139,89631139,89631139,4007,4007,4007],"deck_p2":[89631139,89631139,89631139,4007,4007,4007]}' | libs/ygopro-engine/build/ygopro-engine.exe libs/ygopro-core/cards.cdb libs/ygopro-scripts
```

应输出: `{"ok":true,...}`

### 第三步: 验证 Python Bridge

```bash
cd ygo
python -c "
import sys; sys.path.insert(0, 'packages/ygo-engine-bridge/src')
from ygo_engine_bridge.instance import GameInstance
game = GameInstance.create(
    deck_p1=[89631139]*15+[4007]*15+[7902349]*10,
    deck_p2=[89631139]*15+[4007]*15+[7902349]*10,
)
print('Game:', game.game_id)
moves = game.get_legal_moves()
print('Moves:', moves[0]['type'], 'sset:', moves[0].get('sset_count'))
game.close()
"
```

应输出: `Game: xxxxxxxx` 和 `Moves: idlecmd sset: 5`

### 第四步: 启动 MCP Server

```bash
# 安装 MCP 包 (如未安装)
pip install mcp

# 测试单个 Server 启动
cd ygo
python -m ygo_state.server
```

Server 会在 stdin/stdout 上监听 MCP 协议消息。

### 第五步: 在 Claude Code 中使用

重启 Claude Code，`.mcp.json` 会自动注册 4 个 MCP Server。然后直接对话：

```
> 帮我创建一局游戏王对局，用默认卡组
> 查看当前局面
> 覆盖一张魔法卡到后场
> 结束回合
```

Claude Code 会通过 MCP Tool 调用引擎，返回结果。

---

## 已完成的任务

### Layer 1: C++ 规则引擎 (100%)

| 任务 | 状态 |
|---|---|
| 编译 ocgcore 静态库 (libocgcore.a) | ✅ |
| 编译 ygopro-engine.exe | ✅ |
| 实现 bridge.cpp (ocgcore API 封装) | ✅ |
| 实现 protocol.cpp (JSON 协议处理) | ✅ |
| 实现 main.cpp (stdin/stdout 主循环) | ✅ |
| CDB 卡牌数据库加载 | ✅ |
| init 命令 | ✅ |
| get_state 命令 | ✅ |
| get_legal_moves 命令 | ✅ |
| do_move 命令 (summon/sset/place/to_ep 等) | ✅ |
| respond_chain 命令 (activate/pass) | ✅ |
| query_field 命令 | ✅ |
| 消息缓冲区 size-prefix 帧解析 | ✅ |
| SELECT_IDLECMD 响应格式 (packed i32) | ✅ |
| SELECT_CHAIN 响应格式 (-1=pass) | ✅ |
| 多回合对战流程验证 | ✅ |

### Layer 2: Python Engine Bridge (100%)

| 任务 | 状态 |
|---|---|
| EngineProcess 子进程管理 | ✅ |
| GameInstance 注册表 | ✅ |
| JSON 协议通信 | ✅ |
| GameState 数据结构 | ✅ |
| 类型定义 (Phase, CardType, MoveType 等) | ✅ |
| CardDatabase 卡牌查询 | ✅ |
| 端到端集成验证 | ✅ |

### Layer 3: MCP Server 框架 (100%)

| 任务 | 状态 |
|---|---|
| ygo-state Server (4 Tools) | ✅ |
| ygo-action Server (3 Tools) | ✅ |
| ygo-analysis Server (3 Tools) | ✅ |
| ygo-battle Server (4 Tools) | ✅ |
| FastMCP API 迁移 | ✅ |
| .mcp.json 注册 | ✅ |

### Layer 4: MCP Tool 实现 (框架完成, 未端到端验证)

| Tool | 实现 | 引擎集成 | 端到端测试 |
|---|---|---|---|
| get_game_state | ✅ | ⚠️ | ❌ |
| get_legal_moves | ✅ | ⚠️ | ❌ |
| get_zone_detail | ✅ | ⚠️ | ❌ |
| get_card_info | ✅ | ⚠️ | ❌ |
| execute_move | ✅ | ⚠️ | ❌ |
| respond_chain | ✅ | ⚠️ | ❌ |
| declare_attack | ✅ | ⚠️ | ❌ |
| simulate_move | ✅ | ⚠️ | ❌ |
| evaluate_position | ✅ | ⚠️ | ❌ |
| find_best_line | ✅ | ⚠️ | ❌ |
| start_battle | ✅ | ⚠️ | ❌ |
| ai_decide | ✅ | ⚠️ | ❌ |
| auto_play | ✅ | ⚠️ | ❌ |
| get_battle_log | ✅ | ⚠️ | ❌ |

> ⚠️ = 框架代码已写，但未与真实引擎联调，可能存在数据格式不匹配

---

## 开发路线图

### Stage 1: MCP 端到端验证 (Demo 级别)

**目标**: Claude Code 能通过 MCP Tool 完成一局完整对战。

**任务**:
1. 验证 ygo-state MCP Server 端到端工作
   - `start_battle` 创建对局
   - `get_game_state` 返回完整局面
   - `get_legal_moves` 返回合法操作
2. 验证 ygo-action MCP Server
   - `execute_move` 执行操作 (sset/summon/to_ep)
   - `respond_chain` 连锁响应
3. 验证 ygo-battle MCP Server
   - `auto_play` 自动对战一局
   - `get_battle_log` 获取对战日志
4. 修复联调中发现的数据格式不匹配
5. 在 Claude Code 中完成一次完整对战演示

**验收标准**:
- Claude Code 能创建对局、执行操作、查看局面
- 能完成至少一局完整对战 (双方轮流操作直到一方 LP 归零)

**预计工作量**: 2-3 天

---

### Stage 2: 状态序列化完善 (LLM 友好)

**目标**: 引擎返回的原始数据转换为 LLM 可理解的中文/英文格式。

**任务**:
1. 完善 `get_state` 序列化
   - 场上怪兽: 名称/ATK/DEF/位置/效果文本
   - 手牌: 名称/效果文本 (对手隐藏)
   - 墓地/除外区: 卡牌列表
   - LP/回合/阶段
2. 完善 `get_legal_moves` 序列化
   - 每个操作包含可读描述
   - 操作来源/目标信息
3. 完善 `get_zone_detail` 序列化
   - 指定区域的详细卡牌信息
4. 卡牌名称中英文映射 (从 CDB 读取)
5. 效果文本加载 (从 CDB 的 `texts` 表)

**验收标准**:
- `get_state` 返回的 JSON 包含中文卡名和效果文本
- LLM 仅看 JSON 就能理解当前局面

**预计工作量**: 3-5 天

---

### Stage 3: 对战循环完善 (可玩性)

**目标**: 对战流程顺畅，支持完整的回合制操作。

**任务**:
1. 完善阶段切换 (DP/SP/MP1/BP/MP2/EP)
2. 完善攻击系统 (选择攻击目标/直接攻击)
3. 完善连锁处理 (多层连锁/强制连锁/错过时点)
4. 完善特殊召唤 (融合/同调/超量/灵摆/连接)
5. 完善解放召唤 (1/2/3 解放)
6. 完善效果发动 (选目标/选对象/选位置)
7. 处理 MSG_RETRY (非法操作重试)

**验收标准**:
- 能用标准 40 卡卡组完成一局对战
- 支持常见的召唤方式和效果处理
- 连锁处理正确

**预计工作量**: 1-2 周

---

### Stage 4: AI 决策 Agent (自动化)

**目标**: LLM 能自主分析局面并做出合理决策。

**任务**:
1. 完善 `ai_decide` 的 prompt 设计
   - 局面分析框架 (场面/手牌/资源/LP)
   - 操作优先级 (展开/互动/防守)
2. 实现 Agent 人格系统
   - aggressive: 优先展开和攻击
   - control: 优先互动和资源积累
   - combo: 寻找 OTK/FTK 机会
3. 实现局面评估函数
   - LP 差距/场上价值/手牌质量/墓地资源
4. 实现 `simulate_move` 沙盒模拟
   - 不修改实际状态
   - 支持深度推演 (depth > 1)
5. 实现 `find_best_line` 搜索
   - 贪心搜索最优 2-3 步展开

**验收标准**:
- AI 能自动完成一局对战，不出现明显错误操作
- 不同人格的 AI 有不同的决策风格
- 局面评估分数合理 (0-100)

**预计工作量**: 2-3 周

---

### Stage 5: 教学与复盘系统 (增值功能)

**目标**: 系统能讲解局面、分析失误、提供改进建议。

**任务**:
1. 教学 Agent
   - `explain_card`: 讲解卡牌效果和用法
   - `explain_move`: 解释某个操作的意图
   - `quiz_position`: 基于当前局面出题
   - `check_answer`: 检查答案并解释
2. 复盘系统
   - 对局记录存储 (JSON 格式)
   - `get_turn_state`: 获取指定回合的状态
   - `analyze_mistakes`: 分析关键失误
   - `suggest_improvement`: 给出改进建议
3. 多 Agent 对战
   - 两个不同人格的 Agent 互相对战
   - 对战编排和同步
   - 对战结果统计

**验收标准**:
- 教学 Agent 能正确讲解局面和卡牌
- 复盘系统能分析对局中的关键失误
- 两个 Agent 能自动完成一局对战

**预计工作量**: 2-3 周

---

### Stage 6: 产品化 (落地)

**目标**: 从命令行工具变为可用的产品。

**任务**:
1. Web UI
   - 对战画面渲染 (场上/手牌/墓地/动画)
   - 操作面板 (点击/拖拽)
   - 实时状态更新
2. 卡组编辑器
   - 卡牌搜索和筛选
   - 卡组构建和保存
   - 合法性检查 (禁限卡表)
3. 用户系统
   - 登录/注册
   - 对局历史
   - 段位系统
4. 部署
   - Docker 容器化
   - 多实例支持
   - 性能优化

**验收标准**:
- 用户可以通过 Web UI 完成对战
- 支持卡组编辑和保存
- 可以部署到服务器

**预计工作量**: 1-2 月

---

## 目录结构

```
ygo/
├── demo.md                         # 本文件
├── CLAUDE.md                       # Claude Code 指令
├── SESSION.md                      # 开发进度跟踪
├── .mcp.json                       # MCP Server 注册表
├── pyproject.toml                  # Python 项目配置
│
├── libs/
│   ├── ygopro-core/                # 规则引擎源码 (git submodule)
│   │   ├── cards.cdb               # 卡牌数据库 (14,468 张卡)
│   │   └── build/libocgcore.a      # 编译产物
│   ├── ygopro-engine/              # C++ wrapper
│   │   ├── src/                    # 源码 (bridge/protocol/main)
│   │   └── build/ygopro-engine.exe # 编译产物
│   └── ygopro-scripts/             # Lua 卡牌脚本 (9050 个)
│
├── packages/
│   ├── ygo-engine-bridge/          # Python 共享库
│   │   └── src/ygo_engine_bridge/
│   │       ├── process.py          # 子进程管理
│   │       ├── instance.py         # GameInstance 注册表
│   │       ├── state.py            # GameState 数据结构
│   │       ├── types.py            # 类型定义
│   │       └── cards.py            # 卡牌数据库查询
│   ├── ygo-state/                  # MCP Server: 局面查询
│   │   └── src/ygo_state/
│   │       ├── server.py           # FastMCP 入口
│   │       └── tools/              # 4 个 Tool
│   ├── ygo-action/                 # MCP Server: 操作执行
│   │   └── src/ygo_action/
│   │       ├── server.py
│   │       └── tools/              # 3 个 Tool
│   ├── ygo-analysis/               # MCP Server: 推演评估
│   │   └── src/ygo_analysis/
│   │       ├── server.py
│   │       └── tools/              # 3 个 Tool
│   └── ygo-battle/                 # MCP Server: 自动对战
│       └── src/ygo_battle/
│           ├── server.py
│           └── tools/              # 4 个 Tool
│
└── data/
    └── replays/                    # 对局录像 (待实现)
```

---

## 关键技术决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 规则引擎 | ygopro-core (C++) | 完整 Master Rule 实现，社区验证 |
| 引擎通信 | JSON stdin/stdout 子进程 | 跨语言、易调试、进程隔离 |
| Agent 框架 | Claude Code MCP | 标准 Tool Calling，零代码集成 |
| MCP SDK | FastMCP (Python) | 装饰器 API，开发效率高 |
| 消息格式 | size-prefixed 帧 | ygopro-core 原生格式，无需转换 |
| 响应格式 | packed 32-bit int | ygopro-core 原生格式，引擎直接解析 |

---

## 已知限制

1. **无卡牌效果执行** — Lua 脚本加载失败 (CardDatabase 未从 CDB 读取 setcode)，效果卡会 fallback 到无效果状态
2. **状态序列化不完整** — `get_state` 返回的数据缺少卡名和效果文本
3. **无 UI** — 纯 CLI / MCP 交互，无图形界面
4. **单实例** — 每个 GameInstance 独占一个子进程，不支持并发
5. **无持久化** — 对局状态不保存，进程结束即丢失
