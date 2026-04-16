# Project Lessons
> 项目经验教训和设计决策记录 — 从实践中学习

## 一句话定义
各项目中积累的设计决策、经验教训和技术洞察，避免重复犯错，加速新项目启动。

## 设计决策记录

### 零依赖优先
- **决策**: 所有项目核心功能使用纯 Python/Node.js 标准库
- **原因**: 减少环境依赖、提高可移植性、降低维护成本
- **适用**: agent-memory-service, prompt-weaver, ctxgen, tiny-agent-workshop

### JSON > SQLite（原型阶段）
- **决策**: 早期用 JSON 文件持久化而非 SQLite
- **原因**: 更简单、可读性好、容易调试
- **权衡**: 性能和并发能力较低，但原型阶段够用
- **适用**: agent-memory-service

### n-gram > Embedding（离线场景）
- **决策**: 语义搜索用 n-gram 而非 embedding
- **原因**: 离线可用、无外部依赖、启动快
- **权衡**: 语义理解不如 embedding 精确
- **适用**: local-embedding-memory

### Append-only Changelog
- **决策**: 变更追踪用 append-only log 而非 diff
- **原因**: 简单、可审计、无冲突
- **适用**: agent-memory-service

## 经验教训

### 测试驱动开发
- **教训**: 先写测试再实现，效率更高
- **数据**: prompt-router 8→15 tests (87.5% 增加)，零回退

### 时间盒约束
- **教训**: 20-30 分钟一个 cycle，评估后继续或转向
- **原因**: 防止过度投入，保持快速迭代

### 简洁 > 灵活
- **教训**: 不要为不可能的场景写错误处理
- **引用**: "Add features when you need them, not when you think you might." — Karpathy

## 关联
- [[tool-design-principles]] — 工具设计的通用原则
- [[agent-engineering]] — Agentic Engineering 的实践经验

---
_最后更新：2026-04-16_
