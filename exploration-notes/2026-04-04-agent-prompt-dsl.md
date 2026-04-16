# 2026-04-04 Agent Prompt DSL 创意项目

## 项目
**agent-prompt-dsl** — https://github.com/robertsong2019/agent-prompt-dsl

## 核心想法
Prompt engineering 是一团糟 — 长字符串散落在代码各处，没有版本控制，难以测试。
如果 prompt 是一等公民，像程序一样可声明、可组合、可追踪呢？

## DSL 设计
```yaml
agent:    # 身份定义
triggers: # 激活条件
persona:  # 系统人设
tools:    # 可用工具
flow:     # 执行流水线 (step-by-step)
memory:   # 记忆策略
```

## 关键洞察
1. **Flow 是核心创新** — 把 agent 执行拆成可命名的步骤，每步有输入输出，可组合
2. **Persona 作为数据** — 人设文本变成可版本控制的 YAML 字段
3. **Export 能力** — 可导出为 OpenAI function schema，连接实际运行时
4. **可测试性** — validate() 函数在运行前检查结构完整性

## 下一步可能
- 添加 `memory` 策略实现（retain/ttl/filter）
- 支持多 agent 组合（agent imports agent）
- 添加 `tests` 字段 — 用例驱动的 prompt 验证
- 实现真实的 runtime 执行引擎

## 方向价值
这个项目连接了两个趋势：
1. **Prompt as Code** — prompt 工程正在软件化
2. **Agent Orchestration** — 多步骤 agent 流程需要声明式定义
