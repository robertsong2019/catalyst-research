# Harness Engineering

> 在 Agent-First 时代，软件工程的核心产出不再是代码，而是让 Agent 高效产出高质量代码的系统

## 定义

OpenAI 2026年2月发布，披露了如何让 Codex Agent 从零构建完整内部产品——5个月、0行手写代码、100万行生成代码，效率是传统开发的10倍。

**核心类比：**
- 马 = AI 模型，拥有强大执行力
- 缰绳与马具 (Harness) = 约束、反馈回路、文档、Linter、生命周期管理
- 骑手 = 工程师，提供方向和判断力

**本质：** 约束 + 反馈回路 + 文档 + Linter + 生命周期管理

**角色转变：** 工程师从"写代码"变成"设计让 Agent 高效工作的环境"。你不再是码农，你是 Agent 的架构师。

---

## 六大痛点（为什么需要 Harness）

1. **架构漂移失控** — Agent 不理解架构意图，悄悄越过模块边界，依赖图面目全非
2. **技术债务指数增长** — Agent 不会主动清理废代码，反而基于它继续构建，债务滚雪球
3. **上下文黑洞** — Agent 看不到的信息等于不存在，同一个项目出现三种日志规范
4. **人工 QA 瓶颈** — 一天几十个 PR，review 还是那几个人，质量关口形同虚设
5. **文档代码脱节** — README 是上个月的架构，Agent 基于过时信息做决策

**共同根因：** 有了强大的 Agent，却没有约束和引导它的系统。

---

## 六大实践

### 1. Context Engineering — 上下文工程

**核心原则：** Agent 无法在上下文中访问到的信息，对它来说等于不存在。

**OpenAI 做法：** 88 个 AGENTS.md 文件，根文件定义全局默认规则，子目录文件覆盖本地规则。不是一本大手册，而是一张导航地图。

**渐进式披露（Progressive Disclosure）：**
```
项目根目录/
├── AGENTS.md              ← 全局入口，精简，指向子目录
├── src/
│   ├── api/AGENTS.md      ← API 层约定
│   ├── service/AGENTS.md  ← Service 层约定
│   └── infra/AGENTS.md    ← 基础设施层规则
```

**机械化保鲜：**
- Linter 和 CI 自动验证知识库正确性和时效性
- "doc-gardening" Agent 定期扫描过时文档，自动发 PR 修复
- 文档被当作代码一样持续维护

### 2. Architectural Constraints — 架构约束

**关键设计：** Linter 不只是让构建失败，还将修复指令注入回 Agent 上下文。

```
Agent 生成代码 → Linter 检测违规 → 构建失败+修复指令 → Agent 自动修复 → 再次提交
```

**具体约束举例：**
- 依赖方向：service 层不能反向依赖 controller 层
- 结构化日志：禁止裸 System.out.println
- 文件大小限制：超阈值自动拒绝，倒逼模块拆分
- 命名规范：正则校验
- 循环依赖检测：依赖图分析，环路立即阻断

**三管齐下：**
- 确定性 Linter — 硬约束（import 方向、命名）
- 结构化测试 — 运行时行为验证（依赖图环路）
- LLM-based Agent — 软约束（"这个类的职责是否越界？"）

### 3. Garbage Collection — 技术债 GC

**传统方式：** 技术债累积 → 某天爆发 → 停下来还债（痛苦）
**Harness 方式：** GC Agent 持续运行 → 小增量清理 → 代码库自我清洁（像 JVM GC）

**GC Agent 工作内容：**
- 扫描并修复架构约束违规
- 清理未使用代码、过时接口
- 统一不一致的编码风格
- 修复文档与代码偏差

### 4. Agent Legibility — Agent 可观测性

**三大通道：**
- **UI 通道** — Chrome DevTools Protocol，截取 DOM 快照、截图、操作页面
- **日志通道** — LogQL 查询，按 traceId/错误级别过滤
- **指标通道** — PromQL 查询，延迟/吞吐量/错误率

Agent 可以自己启动服务→查询指标→定位瓶颈→优化→验证，全程无人工介入。

### 5. Bootable per Worktree — 环境隔离

每个 Git Worktree 一个完全隔离的应用实例：
```
Agent-1 (feature-A) → 独立实例-1 → 独立数据库
Agent-2 (feature-B) → 独立实例-2 → 独立数据库
Agent-3 (bugfix-C)  → 独立实例-3 → 独立数据库
```

### 6. Autonomous Workflow — 端到端自治

```
Prompt → 验证代码库 → 复现Bug/理解需求 → 实现修复 → 驱动验证(UI+API+指标)
→ 录制演示 → 开PR → 响应Review → 自动修复构建失败 → 合并
```

仅判断力需人类介入。Agent 处理 90% 机械性工作，人类聚焦 10% 决策。

---

## Catalyst 的 Harness 实践对照

| OpenAI 实践 | Catalyst 实现 | 成熟度 |
|---|---|---|
| Context Engineering | AGENTS.md + SOUL.md + USER.md + wiki/ | ✅ 已有 |
| 渐进式披露 | workspace 根目录 + wiki/index.md | 🟡 基础版 |
| Architectural Constraints | AGENTS.md 红线规则 | 🟡 待加强 Linter 闭环 |
| GC Agent | 手动 memory 整理 | 🔴 可自动化 |
| Agent Legibility | exec + 测试输出 | 🔴 待建设 |
| Bootable per Worktree | 无（单 workspace） | 🔴 不适用当前规模 |
| Autonomous Workflow | 部分实现（spawn + test） | 🟡 可演进 |

---

## 关键洞察

### 双面性：缰绳也是翅膀
Harness 不只是约束（缰绳），也是能力放大器（翅膀）：
- 记忆系统 → 比普通 LLM 更有连续性
- 工具链 → 能实际行动而非只输出文本
- Wiki → 知识可复利增长

### 核心金句
> 你设计的不是功能，而是约束、反馈和环境。

---

## 来源
- 掘金文章《Harness Engineering — AI 时代的工程最佳实践》(https://juejin.cn/post/7615250753935048723)
- OpenAI Harness Engineering 原文 (2026-02)
- 今日头条《Harness Engineering：AI时代的全新开发范式》
- Catalyst 自身实践经验
- 与罗嵩的讨论 (2026-04-08)

## 关联
- [[agent-engineering]] — Agentic Engineering 概念
- [[agent-communication-entropy]] — 多 Agent 治理
- [[knowledge-vs-memory]] — 记忆机制设计
- [[tool-design-principles]] — 工具设计原则

---
_最后更新：2026-04-08_
