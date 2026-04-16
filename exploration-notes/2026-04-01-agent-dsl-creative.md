# 🧬 AgentDSL — 声明式 AI Agent 工作流 DSL

> 日期：2026-04-01
> GitHub: https://github.com/robertsong2019/agent-dsl

## 灵感来源

GitHub 本周趋势项目：
- **bytedance/deer-flow** (55k⭐) — 长周期 SuperAgent 框架
- **SakanaAI/AI-Scientist-v2** (4.2k⭐) — 自动科学发现
- **microsoft/VibeVoice** (33k⭐) — 开源语音 AI
- **last30days-skill** (17k⭐) — AI agent 跨平台研究技能

## 项目核心

<500 行 Python，用 YAML 定义 AI Agent 工作流：

```yaml
steps:
  - id: plan
    prompt: "Break {{topic}} into queries"
  - id: search
    parallel: true    # 并行执行
    input: queries
  - id: gate
    type: gate        # 质量关卡
    condition: "len(report) > 200"
```

### 支持的模式
| 模式 | 实现 |
|------|------|
| Chain | prompt 步骤顺序执行 |
| Parallel | parallel: true 扇出/扇入 |
| Gate | 条件检查 + 重试 |
| Loop | gate 的 retry 指向上游步骤 |
| Code | 注册 Python 函数 |

### 设计决策
1. **YAML 而非 Python DSL** — 非程序员也能定义工作流
2. **模板引擎内建** — `{{var | filter}}` 语法，无需 Jinja2
3. **LLM 后端可插拔** — 默认 OpenAI，可替换任何 provider
4. **无依赖核心** — 仅需 PyYAML

## 与现有框架对比

| 框架 | 代码量 | 学习曲线 | 灵活性 |
|------|--------|----------|--------|
| LangChain | ~50k LOC | 陡峭 | 高 |
| CrewAI | ~10k LOC | 中等 | 中 |
| **AgentDSL** | **<500 LOC** | **10分钟** | **中** |

## 下一步
- [ ] 添加流式输出支持
- [ ] 添加 subgraph 步骤（嵌套工作流）
- [ ] 添加 CLI: `agent-dsl run workflow.yaml --input topic=AI`
- [ ] 添加 observability（步骤耗时、token 用量）
- [ ] 探索 MicroPython 移植（嵌入式场景）

## GitHub Trending 观察
- AI Agent 框架方向持续火热，deer-flow 一周 13k star
- 语音 AI 方向（VibeVoice）也在爆发
- AI 科研自动化（AI-Scientist-v2）是新兴方向
- 简洁实用的小工具比大框架更受欢迎
