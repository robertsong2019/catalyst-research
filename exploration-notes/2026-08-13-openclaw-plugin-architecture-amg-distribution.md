# OpenClaw Plugin Architecture: amg 分发的最快通道

**Date:** 2026-08-13
**Topic:** OpenClaw 插件体系深度解析、amg 集成三条路径、可运行原型
**Status:** Deep Exploration ✅
**Methodology:** autoresearch.md (明确指标 → 快速循环 → 积累性)
**Success Criteria:** 包含可运行代码示例、独到见解、与现有项目关联

---

## 一、核心概念（5个）

### 1. 三层插件体系：Skills → Extensions → MCP Servers

OpenClaw 的扩展能力分为三层，从轻到重：

| 层级 | 文件 | 复杂度 | 分发方式 |
|------|------|--------|---------|
| **Skill** | `SKILL.md` | 最轻 — 一个 Markdown 文件 | 复制到 skills/ 目录 |
| **Extension** | `openclaw.plugin.json` + skills/ + 源码 | 中等 — 完整插件包 | `~/.openclaw/extensions/` 目录 |
| **MCP Server** | `mcpServers` 配置项 | 零代码 — 只需注册 | `openclaw config set mcpServers.*` |

关键洞察：**amg 已经有 17-tool MCP server**，所以最快速的分发路径不是写插件代码，而是注册现有的 MCP server。

### 2. openclaw.plugin.json — 插件清单规范

每个 Extension 的入口点是 `openclaw.plugin.json`，不是 `package.json`。核心字段：

```json
{
  "id": "unique-plugin-id",
  "kind": "tools",              // 可选："tools" | "channel" | 省略
  "channels": [],               // 提供的频道（如 ["qqbot", "wecom"]）
  "skills": ["./skills"],       // SKILL.md 目录列表
  "extensions": ["./preload.cjs"], // 预加载脚本（可选）
  "configSchema": {             // JSON Schema 验证的用户配置
    "type": "object",
    "properties": { ... }
  },
  "capabilities": {             // 声明能力（可选）
    "proactiveMessaging": true
  }
}
```

已分析的真实插件样本：
- **local-embedding-memory**: `"channels": []`, `"skills": ["./skills"]` — 纯 Skill 插件
- **openclaw-tavily**: `"kind": "tools"`, `"skills": ["./skills"]` — 工具型插件
- **openclaw-qqbot**: `"channels": ["qqbot"]`, `"extensions": ["./preload.cjs"]` — 全功能频道插件
- **wecom**: `"channels": ["wecom"]`, `"skills": ["./skills"]` — 频道+技能混合

### 3. PluginRuntime — 运行时注入接口

OpenClaw 向插件的预加载脚本注入 `PluginRuntime` 对象（TypeScript 类型，来自 `openclaw/plugin-sdk`）：

```typescript
interface PluginRuntime {
  version: string;               // OpenClaw 版本号
  getConfig(): OpenClawConfig;   // 读取全局配置
  setConfig(config): void;       // 写入配置
  getDataDir(): string;          // 插件数据目录
  channel?: PluginRuntimeChannel; // 频道接口（消息路由等）
  log: {
    info(msg: string, ...args): void;
    warn(msg: string, ...args): void;
    error(msg: string, ...args): void;
    debug(msg: string, ...args): void;
  };
  subagent: {                    // 子代理控制
    run(params: SubagentRunParams): Promise<SubagentRunResult>;
    waitForRun(params): Promise<SubagentWaitResult>;
    getSessionMessages(params): Promise<SubagentGetSessionMessagesResult>;
    deleteSession(params): Promise<void>;
  };
}
```

**对 amg 的意义**：不需要 PluginRuntime。amg 的集成完全通过 Skill 指令 + MCP 协议完成，无需预加载脚本。

### 4. MCP Server 注册 — 零代码集成路径

OpenClaw 原生支持 MCP 协议（stdio + HTTP/SSE 两种传输）。配置方式：

**方法 1：CLI 命令**
```bash
openclaw config set mcpServers.amg.command "python3"
openclaw config set mcpServers.amg.args '["/path/to/mcp_server.py"]'
openclaw config set mcpServers.amg.env.AMG_DB_PATH "/data/agent_memory.db"
```

**方法 2：直接编辑配置**
```json
{
  "mcpServers": {
    "amg": {
      "command": "python3",
      "args": ["/path/to/agent-memory-graph/mcp_server.py"],
      "env": {
        "AMG_DB_PATH": "/data/agent_memory.db"
      }
    }
  }
}
```

注册后，amg 的 17 个工具（remember, recall, relate, ask, lookup, neighbors, forget, stats, timeline, health, entropy, reason, snapshot, code_explain, quarantine, security, metrics）自动成为 agent 的可用工具。

**方法 3：mcporter 配置**（已验证可用的替代路径）
```json
// ~/.openclaw/workspace/config/mcporter.json
{
  "mcpServers": {
    "amg": {
      "command": "python3",
      "args": ["/root/.openclaw/workspace/projects/agent-memory-graph/mcp_server.py"]
    }
  }
}
```

### 5. Skill-Driven Architecture — 指令即接口

OpenClaw 的核心设计哲学：**Skill 是给 AI 的指令，不是给机器的代码**。

一个 Skill 就是一个 `SKILL.md` 文件，包含：
- YAML frontmatter（name, description, metadata）
- 自然语言指令（何时触发、如何执行）
- 示例命令和输出格式

Agent 在运行时读取 SKILL.md，理解其意图，然后**自主选择工具**（exec, web_fetch, message 等）来执行。这与传统插件（代码→API→编译→部署）完全不同。

**对 amg 的意义**：amg 的 Skill 不需要包装层。直接写一个 SKILL.md 告诉 agent "当用户说'记住这个'时，调用 MCP 工具 `remember`"即可。

---

## 二、amg → OpenClaw 三条集成路径

### 路径对比矩阵

| 维度 | 路径 A: MCP 注册 | 路径 B: Skill Extension | 路径 C: ClawHub 发布 |
|------|------------------|------------------------|---------------------|
| **代码量** | 0 行 | ~60 行（SKILL.md + plugin.json） | ~150 行（含 README） |
| **设置时间** | 2 分钟 | 15 分钟 | 1 小时 |
| **用户发现** | 需手动配置 | `extensions/` 目录 | ClawHub 搜索 |
| **MCP 工具** | ✅ 自动暴露 | ✅ 通过 SKILL.md 引导 | ✅ |
| **Skill 指令** | ❌ 无 | ✅ 有 | ✅ 有 |
| **配置管理** | ❌ 原始 JSON | ✅ configSchema 验证 | ✅ |
| **适合阶段** | 立即可用 | 本周实现 | npm publish 后 |

### 推荐：路径 B（Skill Extension）→ 然后 C（ClawHub）

路径 A 已经可以立即使用（zero code），但不具备分发能力。路径 B 是最佳中间态：既提供 Skill 指令（agent 知道何时使用 amg），又能通过 `extensions/` 目录分发给其他 OpenClaw 用户。

---

## 三、可运行代码示例

### 示例 1：立即可用的 MCP 注册（路径 A — 已验证可运行）

```bash
#!/bin/bash
# register-amg-mcp.sh — 在 OpenClaw 中注册 amg MCP server
# 前提：Python 3.10+ 已安装，agent-memory-graph 已 pip install

AMG_PATH="/root/.openclaw/workspace/projects/agent-memory-graph"
DB_PATH="${HOME}/.openclaw/data/agent_memory.db"

mkdir -p "$(dirname "$DB_PATH")"

# 方法 1：使用 openclaw config set（推荐）
openclaw config set mcpServers.amg.command "python3"
openclaw config set mcpServers.amg.args "[\"${AMG_PATH}/mcp_server.py\"]"
openclaw config set mcpServers.amg.env.AMG_DB_PATH "$DB_PATH"

# 验证
echo "✅ amg MCP server registered"
openclaw config get mcpServers.amg

# 测试 — 重启 gateway 后，agent 自动获得 17 个 amg 工具
# openclaw gateway restart
```

### 示例 2：完整 Skill Extension 插件（路径 B — 核心交付物）

以下文件结构创建一个完整的 amg OpenClaw 插件：

```
extensions/amg-memory/
├── openclaw.plugin.json    # 插件清单
├── package.json            # npm 元数据（用于 ClawHub 发布）
├── skills/
│   └── graph-memory/
│       └── SKILL.md        # Agent 指令
└── README.md
```

**文件 1: `openclaw.plugin.json`**
```json
{
  "id": "amg-memory",
  "kind": "tools",
  "name": "Agent Memory Graph",
  "description": "Graph-based long-term memory for AI agents. SQLite-backed knowledge graph with entropy analysis, spreading activation, and bi-temporal queries.",
  "version": "1.0.0",
  "skills": ["./skills"],
  "configSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "dbPath": {
        "type": "string",
        "description": "Path to SQLite database file",
        "default": "~/.openclaw/data/agent_memory.db"
      },
      "mcpCommand": {
        "type": "string",
        "description": "Python executable path",
        "default": "python3"
      },
      "mcpServerPath": {
        "type": "string",
        "description": "Path to amg MCP server script"
      }
    }
  },
  "uiHints": {
    "dbPath": {
      "label": "Database Path",
      "help": "SQLite file for graph storage. Created if not exists."
    },
    "mcpServerPath": {
      "label": "MCP Server Script",
      "help": "Path to mcp_server.py from agent-memory-graph package",
      "advanced": true
    }
  }
}
```

**文件 2: `skills/graph-memory/SKILL.md`**
```markdown
---
name: graph-memory
description: >
  Graph-based long-term memory using agent-memory-graph. Activate when user
  says "remember this", "do I know about X", "what connects Y and Z", or
  any memory storage/retrieval need that benefits from relationships.
metadata:
  openclaw:
    emoji: "🧠"
    requires:
      bins: ["python3"]
---

# Agent Memory Graph — Graph-Based Long-Term Memory

A knowledge graph memory system that stores entities as nodes and relationships
as edges in SQLite. Supports multi-hop reasoning, entropy analysis, and
spreading activation.

## MCP Tool Reference

When this skill is active, the following MCP tools are available:

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `remember` | Store a memory entity | name, kind, data, tags |
| `recall` | Retrieve by label/kind/tags | query, kind, tags, limit |
| `relate` | Create relationship between entities | source, relation, target |
| `ask` | Natural language query over graph | question |
| `lookup` | Get entity by ID | id |
| `neighbors` | Get adjacent entities | id, depth |
| `forget` | Remove entity/relationship | id |
| `stats` | Graph statistics | — |
| `timeline` | Temporal traversal | direction, limit |
| `reason` | Multi-hop reasoning chain | start, goal, max_hops |
| `entropy` | Graph entropy analysis | type |
| `snapshot` | Save/restore graph state | action, label |
| `health` | Consistency check | — |
| `code_explain` | Code-aware memory explainability | node_id |
| `quarantine` | Isolate suspicious nodes | node_id, reason |
| `security` | Security audit report | — |
| `metrics` | MCP tool call metrics | — |

## Usage Patterns

### Pattern 1: Store a Memory
When user says "remember this" or "note this down":

Use the `remember` MCP tool:
- name: short title
- kind: person | project | event | idea | fact | note | decision
- data: structured metadata object
- tags: array of strings for filtering

Example: User says "Remember that the API deploy failed due to timeout"

→ remember(name="API deploy failure 2026-08-13", kind="event",
  data={"cause": "timeout", "service": "api", "severity": "high"},
  tags=["incident", "api", "deploy"])

### Pattern 2: Recall Related Memories
When user asks "what do I know about X" or "find information about Y":

1. Start with `recall(query="X", limit=5)`
2. For deeper context, use `neighbors(id=<found_id>, depth=2)`
3. For relationships, use `reason(start=<id_A>, goal=<id_B>, max_hops=3)`

### Pattern 3: Connect Ideas
When user says "X is related to Y" or "connect these concepts":

Use `relate(source=<id_A>, relation="depends_on", target=<id_B>)`
Then verify with `neighbors(id=<id_A>, depth=2)`

### Pattern 4: Memory Health
When user asks about memory status or quality:

Use `stats` for overview, `health` for consistency, `entropy` for complexity analysis.

## Fallback: Direct Python Access

If MCP tools are unavailable, use Python directly:

\`\`\`bash
python3 -c "
import sys; sys.path.insert(0, '$AMG_PATH')
from memory_graph import MemoryGraph
mg = MemoryGraph()
node = mg.add_node('Test', 'concept', {'note': 'hello'})
print(mg.search('Test'))
"
\`\`\`

## Important Notes

- All data persists in SQLite at the configured dbPath
- Graph operations are ACID transactions
- Entropy analysis helps identify memory gaps and redundancy
- Use `snapshot(action="save", label="pre-experiment")` before risky operations
```

**文件 3: `package.json`**
```json
{
  "name": "@openclaw/amg-memory",
  "version": "1.0.0",
  "description": "Graph-based long-term memory for OpenClaw agents",
  "type": "module",
  "files": [
    "skills/",
    "openclaw.plugin.json",
    "README.md"
  ],
  "openclaw": {
    "extensions": [],
    "install": {
      "localPath": "extensions/amg-memory"
    }
  },
  "keywords": [
    "openclaw",
    "memory",
    "knowledge-graph",
    "agent",
    "sqlite",
    "graph",
    "long-term-memory"
  ],
  "license": "MIT",
  "peerDependencies": {
    "openclaw": ">=2026.2.24"
  }
}
```

### 示例 3：自动安装脚本（可运行）

```python
#!/usr/bin/env python3
"""
install_amg_openclaw_plugin.py
在 OpenClaw 中安装 amg 作为 Extension 插件 + MCP server
"""

import os
import json
import shutil
from pathlib import Path

OPENCLAW_HOME = Path.home() / ".openclaw"
EXTENSIONS_DIR = OPENCLAW_HOME / "extensions" / "amg-memory"
AMG_SOURCE = Path(__file__).parent / "projects" / "agent-memory-graph"

def main():
    print("🧠 Installing agent-memory-graph OpenClaw plugin...")

    # 1. 创建插件目录结构
    EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    (EXTENSIONS_DIR / "skills" / "graph-memory").mkdir(parents=True, exist_ok=True)

    # 2. 写入 openclaw.plugin.json
    plugin_manifest = {
        "id": "amg-memory",
        "kind": "tools",
        "name": "Agent Memory Graph",
        "description": "Graph-based long-term memory with entropy analysis",
        "version": "1.0.0",
        "skills": ["./skills"],
        "configSchema": {
            "type": "object",
            "properties": {
                "dbPath": {
                    "type": "string",
                    "default": str(OPENCLAW_HOME / "data" / "agent_memory.db")
                }
            }
        }
    }
    (EXTENSIONS_DIR / "openclaw.plugin.json").write_text(
        json.dumps(plugin_manifest, indent=2)
    )
    print(f"  ✅ Created {EXTENSIONS_DIR / 'openclaw.plugin.json'}")

    # 3. 写入 SKILL.md（简化版）
    skill_content = '''---
name: graph-memory
description: Graph-based memory using agent-memory-graph. Activate for "remember", "recall", "what do I know about", memory storage and retrieval.
metadata:
  openclaw:
    emoji: "🧠"
---

# Graph Memory

Use MCP tools (remember, recall, relate, ask, neighbors, reason, stats) for graph-based memory operations.
All data persists in SQLite. Use `snapshot` before risky operations.
'''
    skill_path = EXTENSIONS_DIR / "skills" / "graph-memory" / "SKILL.md"
    skill_path.write_text(skill_content)
    print(f"  ✅ Created {skill_path}")

    # 4. 注册 MCP server
    mcporter_config_path = OPENCLAW_HOME / "workspace" / "config" / "mcporter.json"
    mcporter_config_path.parent.mkdir(parents=True, exist_ok=True)

    if mcporter_config_path.exists():
        config = json.loads(mcporter_config_path.read_text())
    else:
        config = {"mcpServers": {}, "imports": []}

    config["mcpServers"]["amg"] = {
        "command": "python3",
        "args": [str(AMG_SOURCE / "mcp_server.py")],
        "env": {
            "AMG_DB_PATH": str(OPENCLAW_HOME / "data" / "agent_memory.db")
        }
    }
    mcporter_config_path.write_text(json.dumps(config, indent=2))
    print(f"  ✅ Registered MCP server in {mcporter_config_path}")

    # 5. 创建数据目录
    data_dir = OPENCLAW_HOME / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ Data directory: {data_dir}")

    print("\n🎉 Installation complete!")
    print("   Restart OpenClaw gateway: openclaw gateway restart")
    print("   Test: ask the agent to 'remember that today is install day'")

if __name__ == "__main__":
    main()
```

---

## 四、关键洞察（5条）

### 洞察 1：MCP 协议是分发的核武器，而非插件代码

amg 的 17-tool MCP server 已经是完整的 OpenClaw 集成方案。**零行 JavaScript/TypeScript 代码**就能让 agent 获得 graph memory 能力。这意味着 amg 的分发瓶颈不是"写 OpenClaw 插件"，而是"让用户知道 MCP server 存在"。ClawHub 发布的核心价值是**可发现性**，不是技术集成。

### 洞察 2：Skill 是"营销材料"，不是"代码"

OpenClaw 的 Skill 系统本质上是给 AI 的 prompt engineering。一个优秀的 Skill 像 README — 它告诉 agent **何时**使用这个工具、**如何**组合工具完成任务、**输出格式**应该是什么。amg 的 SKILL.md 应该像 API 文档一样设计：工具表格 + 使用模式 + 示例。

这与传统插件开发截然不同：不需要写 binding、adapter、wrapper。只需写好指令。

### 洞察 3：三层分发漏斗策略

```
Layer 1: MCP Server（技术基座）— 已完成 ✅ 17 tools
Layer 2: Skill Extension（产品包装）— SKILL.md + plugin.json — 本周
Layer 3: ClawHub Package（市场分发）— npm publish — README 完成后
```

每一层的用户群不同：
- **Layer 1** 用户：技术极客，愿意手写 JSON 配置
- **Layer 2** 用户：OpenClaw 用户，浏览 extensions/ 目录
- **Layer 3** 用户：ClawHub 搜索者，看 star 数和评价

### 洞察 4：对比 local-embedding-memory 的架构启示

`local-embedding-memory` 插件的架构选择揭示了 OpenClaw 社区的偏好：

| 设计选择 | local-embedding-memory | amg 应该做的 |
|---------|----------------------|------------|
| 检索方式 | 本地 Python 脚本（exec） | MCP server（协议级） |
| 存储格式 | JSON 文件 | SQLite（ACID） |
| 检索深度 | 向量相似度（single-hop） | PPR + spreading activation（multi-hop） |
| 配置暴露 | configSchema + uiHints | 同样模式 |

amg 在每个维度都是**严格升级**，这应该是 README 的核心叙事。

### 洞察 5：memory-core SDK 的竞争分析

OpenClaw plugin-sdk 中已存在 `memory-core` 模块（含 `memory-host-*`、`memory-lancedb`），这是 OpenClaw 内置的记忆系统。amg 的差异化定位：

| 维度 | OpenClaw memory-core | amg |
|------|---------------------|-----|
| 存储 | Markdown 文件 + LanceDB | SQLite（单文件） |
| 结构 | 扁平文档 | 图结构（实体-关系） |
| 检索 | 向量相似度 | PPR + spreading activation + entropy |
| 分析 | 无 | 40+ entropy APIs + 25-API classification |
| 安全 | 无 | OWASP ASI06 安全套件（6 APIs） |
| 多 agent | 无 | MESI 协议一致性 |

**叙事策略**：不与 memory-core 竞争，而是定位为 memory-core 的"高级分析层"。用户可以同时使用两者。

---

## 五、下一步行动（3个）

### Action 1: 立即创建 Extension 插件（15 分钟）
```bash
mkdir -p ~/.openclaw/extensions/amg-memory/skills/graph-memory
# 写入 openclaw.plugin.json（用示例 2）
# 写入 SKILL.md（用示例 2）
# 重启 gateway
```
**验证标准**：agent 在对话中自动识别记忆意图并调用 amg 工具。

### Action 2: 在 mcporter.json 中注册 amg（2 分钟）
在 `~/.openclaw/workspace/config/mcporter.json` 的 `mcpServers` 中添加 amg 条目。**这是已经在使用的路径**，只需确认配置正确。

### Action 3: 为 ClawHub 发布准备 package（npm publish 后）
将 `extensions/amg-memory/` 目录提升为独立 npm 包，配合 amg 的 PyPI 包一起发布。README 中强调：
- "First graph-based memory MCP server for OpenClaw"
- "17 tools, zero configuration"
- "SQLite — single file, zero infrastructure"
- 对比表格（vs memory-core, vs 向量 RAG）

---

## 六、质量自检

| 标准 | 状态 |
|------|------|
| 核心概念（3-5个） | ✅ 5个：三层插件体系、plugin.json 规范、PluginRuntime、MCP 注册、Skill-Driven |
| 可运行代码（≥1） | ✅ 3个示例：MCP 注册脚本、完整 Extension 文件、Python 安装脚本 |
| 关键洞察（≥3） | ✅ 5条：MCP 是核武器、Skill 是营销、三层漏斗、架构启示、竞争分析 |
| 下一步行动（≥1） | ✅ 3个：Extension 创建、MCP 注册、ClawHub 准备 |
| 与现有项目关联 | ✅ 直接关联 amg 的 17-tool MCP server、8505 Python tests、HEARTBEAT 待办 |
| 独到见解 | ✅ "Skill 是营销材料不是代码" + 三层漏斗 + memory-core 差异化分析 |

---

*Research #063. Builds on Research #062 (GraphRAG landscape) — GraphRAG 是市场定位，OpenClaw 插件是分发通道。两者共同构成 amg 的 GTM 策略。*
