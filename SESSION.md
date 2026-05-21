# YGO AI Agent — 开发进度跟踪

> 最后更新: 2026-05-21

---

## Phase 0: ygopro-core 调研 ✅ 已完成

### 完成的任务
- [x] 调研 ygopro-core 仓库 (Fluorohydride vs edo9300)
- [x] 确认使用 edo9300/ygopro-core 新 API (v11.0)
- [x] 分析 OCG API 函数签名 (13 个导出函数)
- [x] 确认集成方案: 子进程 + JSON stdin/stdout 通信
- [x] 发现 yuki 项目有 Python ctypes 参考实现
- [x] 确认编译方式: premake5 或 meson

### 关键发现
- 规则引擎核心是 `ocgcore.dll` / `libocgcore.so`
- 需要三个回调: DataReader (卡牌数据), ScriptReader (Lua 脚本), LogHandler
- 需要卡牌数据库 `cards.cdb` (SQLite) 和 Lua 脚本 (`ygopro-scripts`)

---

## Phase 1: 项目结构 & 基础框架 ✅ 已完成

### 完成的任务
- [x] 创建项目目录结构
- [x] 创建 pyproject.toml (根项目 + 4 个子包)
- [x] 创建 CLAUDE.md (项目说明)
- [x] 创建 .mcp.json (MCP Server 注册表)

### 目录结构
```
ygo/
├── .mcp.json                    # MCP Server 注册表
├── CLAUDE.md                    # 项目说明
├── SESSION.md                   # 开发进度跟踪 (本文件)
├── INSTALL_COMPILER.md          # 编译器安装指南
├── pyproject.toml               # 根项目配置
├── libs/
│   ├── ygopro-core/             # edo9300/ygopro-core 源码 (已克隆)
│   ├── ygopro-engine/           # C++ wrapper ✅ 编译成功
│   └── ygopro-scripts/          # Lua 脚本 (已克隆)
├── packages/
│   ├── ygo-engine-bridge/       # Python 共享库 ✅
│   ├── ygo-state/               # Phase 1 MCP Server ✅
│   ├── ygo-action/              # Phase 2 MCP Server ✅
│   ├── ygo-analysis/            # Phase 3 MCP Server ✅
│   └── ygo-battle/              # Phase 4 MCP Server ✅
└── data/
```

---

## Phase 2: C++ Engine Wrapper ✅ 编译成功

### 完成的任务
- [x] 创建 CMakeLists.txt
- [x] 实现 bridge.h / bridge.cpp (ocgcore API 封装)
- [x] 实现 protocol.h / protocol.cpp (JSON 协议处理)
- [x] 实现 main.cpp (stdin/stdout 主循环)
- [x] 下载 nlohmann/json 头文件
- [x] 编译 ocgcore 静态库 (libocgcore.a, 130MB, Release 模式)
- [x] 编译 ygopro-engine.exe (1.4MB)
- [x] 端到端验证: 引擎启动、JSON 协议、init/get_state/query_field 全部工作

### 编译修复记录
- meson.build: 去掉 `'c'` 语言声明 (不需要 C 编译器，Lua .c 文件复制为 .cpp)
- meson.build: 修复 Python 复制命令 range 少一次迭代的 bug (lzio 未生成)
- libocgcore.a: 必须用 `-Dbuildtype=release` 编译，否则与 ygopro-engine 的 /MD 不匹配
- cards.cdb: 创建了包含 6 张基础测试卡的 SQLite 数据库

### 关键文件
- `libs/ygopro-engine/build/ygopro-engine.exe` — 编译产物
- `libs/ygopro-engine/build/cards.cdb` — 测试卡牌数据库
- `libs/ygopro-core/build/libocgcore.a` — 规则引擎静态库

---

## Phase 3: Python Engine Bridge ✅ 已完成

### 完成的任务
- [x] 实现 types.py (枚举: Phase, CardType, MoveType, Zone 等)
- [x] 实现 state.py (数据结构: GameState, Card, Move, MoveResult)
- [x] 实现 process.py (EngineProcess 子进程管理)
- [x] 实现 instance.py (GameInstance 注册表)
- [x] 实现 cards.py (CardDatabase 卡牌数据库查询)
- [x] 所有模块导入测试通过

### 关键文件
- `packages/ygo-engine-bridge/src/ygo_engine_bridge/types.py` — 类型定义
- `packages/ygo-engine-bridge/src/ygo_engine_bridge/state.py` — 状态数据结构
- `packages/ygo-engine-bridge/src/ygo_engine_bridge/process.py` — 子进程管理
- `packages/ygo-engine-bridge/src/ygo_engine_bridge/instance.py` — 游戏实例

---

## Phase 4: ygo-state MCP Server ✅ 已完成

### 完成的任务
- [x] 实现 server.py (MCP Server 入口)
- [x] 实现 get_game_state.py (完整局面快照)
- [x] 实现 get_legal_moves.py (合法操作列表)
- [x] 实现 get_zone_detail.py (区域详情)
- [x] 实现 get_card_info.py (卡牌信息查询)
- [x] 实现 prompts/system.py (分析 Prompt 模板)
- [x] 5 个测试全部通过

### MCP Tools
| Tool | 描述 | 测试 |
|---|---|---|
| get_game_state | 完整局面快照 | ✅ |
| get_legal_moves | 合法操作列表 | ✅ |
| get_zone_detail | 区域详情 | ✅ |
| get_card_info | 卡牌信息查询 | ✅ |

---

## Phase 5: ygo-action MCP Server ✅ 已完成

### 完成的任务
- [x] 实现 server.py (MCP Server 入口)
- [x] 实现 execute_move.py (执行操作)
- [x] 实现 respond_chain.py (连锁响应)
- [x] 实现 declare_attack.py (攻击宣言)
- [x] 实现 prompts/system.py (对战 Prompt 模板)
- [x] 5 个测试全部通过

### MCP Tools
| Tool | 描述 | 测试 |
|---|---|---|
| execute_move | 执行操作 | ✅ |
| respond_chain | 连锁响应 | ✅ |
| declare_attack | 攻击宣言 | ✅ |

---

## Phase 6: ygo-analysis MCP Server ✅ 已完成

### 完成的任务
- [x] 实现 server.py (MCP Server 入口)
- [x] 实现 simulate_move.py (沙盒模拟)
- [x] 实现 evaluate_position.py (局面评分)
- [x] 实现 find_best_line.py (最优路线搜索)
- [x] 实现 prompts/system.py (分析 Prompt 模板)
- [x] 4 个测试全部通过

### MCP Tools
| Tool | 描述 | 测试 |
|---|---|---|
| simulate_move | 沙盒模拟 | ✅ |
| evaluate_position | 局面评分 (0-100) | ✅ |
| find_best_line | 最优路线搜索 | ✅ |

---

## Phase 7: ygo-battle MCP Server ✅ 已完成

### 完成的任务
- [x] 实现 server.py (MCP Server 入口)
- [x] 实现 start_battle.py (创建对局)
- [x] 实现 ai_decide.py (AI 决策)
- [x] 实现 auto_play.py (自动对战)
- [x] 实现 get_battle_log.py (对战日志)
- [x] 实现 prompts/system.py (对战 Prompt 模板)
- [x] 实现 Agent 人格配置 (aggressive/control/combo)
- [x] 6 个测试全部通过

### MCP Tools
| Tool | 描述 | 测试 |
|---|---|---|
| start_battle | 创建对局 | ✅ |
| ai_decide | AI 决策 | ✅ |
| auto_play | 自动对战 | ✅ |
| get_battle_log | 对战日志 | ✅ |

---

## 测试汇总

```
packages/ygo-state/tests/      5 passed ✅
packages/ygo-action/tests/     5 passed ✅
packages/ygo-analysis/tests/   4 passed ✅
packages/ygo-battle/tests/     6 passed ✅
─────────────────────────────────────
Total:                        20 passed ✅
```

---

## 下一步任务 (优先级排序)

### P0: 获取完整卡牌数据库和脚本 ✅ 已完成
- [x] 创建测试 cards.cdb (6 张基础卡)
- [x] **获取完整的 cards.cdb** (ProjectIgnis/BabelCDB, 14,468 张卡, 7.3MB)
- [x] **确认 ygopro-scripts** (edo9300/ygopro-scripts, 9050 个脚本)
- [x] 验证 engine + cards.cdb + scripts 完整集成

### P1: Python ↔ Engine 集成验证 ✅ 已完成
- [x] 更新 process.py 自动检测引擎路径
- [x] 更新 instance.py 默认 paths
- [x] 修复 stderr 管道死锁问题
- [x] 测试 GameInstance.create → init → get_state 完整流程

### P2: 完善 C++ Wrapper 功能 ✅ 已完成
- [x] 完善 protocol.cpp 的 get_legal_moves 实现
- [x] 完善 protocol.cpp 的 do_move 实现
- [x] 完善 bridge.cpp 的 card_db_ 加载逻辑 (从 CDB 读取)
- [x] 完善状态查询序列化
- [x] 修复消息缓冲区解析 (size prefix framing)
- [x] 修复 SELECT_IDLECMD/SELECT_BATTLECMD 响应格式 (packed 32-bit int)
- [x] 修复 respond_chain pass 响应 (-1 而非 0)
- [x] 添加所有已知消息类型的 skip 逻辑 (防止死循环)
- [x] 多回合对战流程验证通过

### P2 技术修复记录

**消息缓冲区格式**: `OCG_DuelGetMessage` 返回的 buffer 是 size-prefixed 帧格式:
```
[uint32_t size][message payload of size bytes]  (重复)
```
每个消息帧有 4 字节 little-endian 长度前缀。`parse_messages` 和 `parse_legal_moves` 都需要先读取这个前缀。

**SELECT_IDLECMD 响应格式**: int32_t = `(index << 16) | type`
- type: 0=summon, 1=spsummon, 2=reposition, 3=mset, 4=sset, 5=activate, 6=to_bp, 7=to_ep

**SELECT_CHAIN 响应格式**: int32_t = -1 (pass) 或 0+ (chain index)

**SELECT_CHAIN 消息格式**:
```
player(u8) + spe_count(u8) + forced(u8) + hint_timing[0](u32) + hint_timing[1](u32) + count(u32) + chains...
每个 chain: code(u32) + ctrl(u8) + loc(u8) + seq(u32) + pos(u32) + desc(u64) + mode(u8) = 23 bytes
```

**关键教训**: `OCG_DuelGetMessage` 每次调用都会清空 buffer，必须缓存消息。

### P3: MCP Server 端到端测试
- [ ] 测试 ygo-state MCP Server 连接真实引擎
- [ ] 测试 ygo-action MCP Server
- [ ] 测试 ygo-analysis MCP Server
- [ ] 测试 ygo-battle MCP Server
- [ ] 在 Claude Code 中调用 MCP Tool

### P4: 完善 AI 策略
- [ ] 优化局面评估函数权重
- [ ] 实现深度推演 (simulate_move depth>1)
- [ ] 完善 ai_decide 的策略逻辑
- [ ] 添加更多 Agent 人格

### P5: 教学 & 复盘系统
- [ ] 实现 ygo-teaching MCP Server
- [ ] 实现 ygo-replay MCP Server
- [ ] 对局记录存储

---

## 已知问题

1. **模拟功能未完整** — simulate_move 目前会修改实际状态，需要实现状态克隆
2. **AI 决策简单** — ai_decide 使用基础启发式，需要 LLM 集成

---

## 技术债务

- [ ] 添加 type hints 到所有 Python 文件
- [ ] 添加 docstring 到所有公共函数
- [ ] 实现错误处理和重试机制
- [ ] 添加日志系统
- [ ] 配置 CI/CD
