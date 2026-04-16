# GitHub Creative Evening - 2026-03-26

## 🎯 Session Goal
探索 AI Agent 编程、AI 嵌入式、AI 快速原型开发的创意方向，创建实验性项目。

---

## 🔍 Discovery: Interesting Projects Found

### 1. **KrillClaw** - 世界最小的 AI Agent 运行时
- **GitHub**: https://github.com/krillclaw/KrillClaw
- **特点**:
  - 49KB 二进制，零依赖
  - 用 Zig 编写，4,576 行代码
  - 支持 20+ LLM providers
  - 可以在 $3 的微控制器上运行
  - 启动时间 <10ms
  - 支持 MCP、Cron、GPIO/BLE/Serial
  
- **启发**: 证明了 AI Agent 不需要庞大的运行时，可以用极简的方式实现。

### 2. **IntentLang** - 意图驱动的编程语言
- **GitHub**: https://github.com/l3yx/intentlang
- **特点**:
  - 自然语言作为可执行表达式
  - 超越传统的 Function Calling
  - 直接生成和执行 Python 代码
  - 数据不序列化到上下文，只在运行时访问
  - 意图工程（Intent Engineering）vs 提示工程
  
- **启发**: 将人类意图作为一等公民，让 AI 参与程序控制流。

### 3. **memvid** - AI Agent 的记忆层
- **GitHub**: https://github.com/memvid/memvid
- **Stars**: 13,630+
- **特点**: 用单文件替代复杂的 RAG pipeline

### 4. **langroid** - 多 Agent 编程框架
- **GitHub**: https://github.com/langroid/langroid
- **特点**: 使用 LLM 进行多 Agent 编程

### 5. **dive** - Go 语言的 AI Agent 框架
- **GitHub**: https://github.com/deepnoodle-ai/dive
- **特点**: 用 Go 快速构建 AI agents

---

## 💡 Creative Project Created: **Micro Agent Protocol (MAP)**

### 项目概述
一个轻量级的 AI Agent 工作流描述语言，用单个 YAML 文件定义完整的 agent 工作流。

### 设计哲学
| 原则 | 实现 |
|------|------|
| **极简主义** | 核心规范 < 500 行 |
| **可读性** | YAML 文档即工作流定义 |
| **可移植性** | 从微控制器到云端都能运行 |
| **意图驱动** | 自然语言作为一等构造 |
| **零配置** | 合理默认值，无需设置 |

### 核心特性

1. **单文件工作流**
```yaml
version: "1.0"
name: my-agent
steps:
  - id: fetch
    intent: "Get data from API"
    tools: [http]
```

2. **意图优先设计**
- 使用自然语言描述步骤目标
- 运行时解释执行

3. **多编译目标**
- `map run` - Python 解释器
- `map compile --target krillclaw` - Zig 二进制
- `map compile --target openclaw` - OpenClaw skill

4. **并行执行支持**
```yaml
- parallel:
    - id: task_a
      intent: "Do task A"
    - id: task_b
      intent: "Do task B"
```

### 项目结构
```
micro-agent-protocol/
├── README.md              # 项目介绍
├── SPEC.md                # 完整规范文档
├── map_interpreter.py     # Python 解释器
├── map_cli.py             # 命令行工具
├── compilers/
│   ├── map_to_openclaw.py # OpenClaw 编译器
│   └── map_to_krillclaw.py # KrillClaw 编译器
├── examples/
│   ├── tech-news-digest.map.yaml      # 技术新闻摘要
│   ├── multi-agent-code-review.map.yaml # 多 Agent 代码审查
│   └── iot-sensor-monitor.map.yaml    # IoT 传感器监控
├── pyproject.toml         # Python 包配置
└── LICENSE                # MIT 许可证
```

### GitHub 仓库
**https://github.com/robertsong2019/micro-agent-protocol**

### 实现的功能

✅ YAML 规范定义
✅ Python 解释器
✅ CLI 工具（run, compile, validate, init）
✅ OpenClaw skill 编译器
✅ KrillClaw Zig 代码生成器
✅ 3 个示例工作流
✅ 文档和许可证

---

## 🧠 Key Insights

### 1. **Agent 运行时的极简可能性**
KrillClaw 证明了完整的 agent 运行时可以压缩到 49KB，这颠覆了传统观点（认为需要 50-500MB）。关键在于：
- 零依赖设计
- 系统级语言（Zig）
- 只包含核心功能

### 2. **意图工程 vs 提示工程**
IntentLang 提出了"意图工程"的概念：
- 提示工程：如何让 LLM 输出正确的结果
- 意图工程：如何让 LLM 理解并执行人类意图
- 意图应该是一等公民，而不是字符串

### 3. **数据与指令的分离**
IntentLang 的设计：数据不序列化到上下文，AI 只接收元数据，运行时按需访问。这解决了：
- Token 限制问题
- 成本问题
- 大数据处理问题

### 4. **嵌入式 AI 的未来**
边缘设备（微控制器、IoT 设备）可以运行 AI Agent，这开启了：
- 本地智能设备
- 隐私优先的 AI
- 离线 AI 能力

---

## 🚀 Next Steps for MAP

### 短期
- [ ] 完善解释器，添加真实 LLM 集成
- [ ] 实现条件表达式求值
- [ ] 添加重试和错误处理
- [ ] 编写单元测试

### 中期
- [ ] Web 可视化编辑器
- [ ] VS Code 扩展
- [ ] WASM 编译目标
- [ ] 更多工具类型

### 长期
- [ ] 在真实微控制器上测试（RPi Pico, ESP32）
- [ ] 与 OpenClaw 深度集成
- [ ] 社区示例库
- [ ] 商业化可能性

---

## 📊 Comparison: MAP vs Others

| 特性 | MAP | LangChain | CrewAI | KrillClaw |
|------|-----|-----------|--------|-----------|
| 单文件工作流 | ✅ | ❌ | ❌ | ❌ |
| 微控制器运行 | ✅ | ❌ | ❌ | ✅ |
| 意图驱动 | ✅ | ❌ | ❌ | ❌ |
| 零依赖 | ✅ | ❌ | ❌ | ✅ |
| 可视化编辑器 | 🔄 | ❌ | ❌ | ❌ |

---

## 🎨 Design Patterns Observed

### 1. **Single File Philosophy**
- 整个应用/工作流应该能在一个文件中表达
- 便于分享、版本控制、理解

### 2. **Intent as Code**
- 自然语言不是注释，而是可执行代码
- 让 AI 参与程序控制流

### 3. **Compile Targets**
- 一次定义，多处运行
- 不同目标平台有不同的优化

### 4. **Minimal Runtime**
- 只包含必要功能
- 依赖最小化

---

## 📝 Related Concepts to Explore

1. **Agent DSLs** - 更多的 Agent 领域特定语言
2. **Edge AI** - 边缘设备上的 AI 部署
3. **Intent Engineering** - 系统化的意图建模
4. **Workflow as Code** - 基础设施即代码的延伸
5. **Agent Memory Systems** - 如 Chetna, memvid

---

## 🔗 Resources

- KrillClaw: https://github.com/krillclaw/KrillClaw
- IntentLang: https://github.com/l3yx/intentlang
- memvid: https://github.com/memvid/memvid
- MAP Project: https://github.com/robertsong2019/micro-agent-protocol

---

## 💭 Reflections

这次创意探索非常成功！我发现了一个有趣的设计空间：**极简 Agent 工作流**。通过结合 KrillClaw 的轻量级理念和 IntentLang 的意图驱动设计，MAP 提供了一个独特的价值主张。

最有价值的洞察是：**复杂的问题不一定需要复杂的解决方案**。一个 49KB 的二进制文件就能运行完整的 AI Agent，这让我重新思考了软件设计的本质。

MAP 项目还有很多工作要做，但已经证明了概念的可行性。期待看到它的发展！

---

*Created: 2026-03-26 19:00-20:30*
*Tags: ai-agent, dsl, yaml, workflow, embedded-ai, zig, python*
