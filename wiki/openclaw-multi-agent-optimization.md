# OpenClaw Multi-Agent Optimization

> OpenClaw 的多 Agent 架构分析与优化方向

## 当前定位

OpenClaw 是**个人 Agent 运行时**，不是通用 Agent 编排框架。

### 强项
- 多渠道集成（飞书、Telegram、Discord、微信等）
- 角色隔离（每个 Agent 有独立 SKILL.md、权限、上下文）
- 通用能力（执行代码、读写文件、调用 API）
- 中等编排能力（sub-agent spawn/steer/kill、ACP runtime、cron、heartbeat）

### 弱项
- 复杂 DAG 编排
- Agent 间共享状态
- 企业级可靠性

## 优化方向（按优先级）

### 1. 共享状态（投入产出比最高）
- Agent 间的 key-value store 或黑板系统
- Agent A 写入进度，Agent B 读取后决策
- 解决 80% 的协作问题

### 2. 任务队列与调度
- 优先级队列、资源限制、失败重试
- 避免手动 spawn 的混乱

### 3. 结构化通信协议
- 标准消息格式：task_request / result / error / progress
- 替代当前的 sessions_send 纯文本

### 4. DAG 编排
- 支持 depends_on 依赖关系
- 自动按拓扑排序执行

### 5. Agent Registry
- 统一注册中心，记录能力、状态、负载
- 主 Agent 自动选择最合适的 Agent 分派

## 边界判断

- **个人场景**：当前 spawn + sessions_send 够用
- **小团队**：需要共享状态 + 任务队列
- **企业级**：建议用 LangGraph/CrewAI 补充编排能力

## 关联
- [[agent-engineering]] — Agentic Engineering 概念
- [[agent-orchestration]] — 编排模式

## 来源
- 与罗嵩的讨论 (2026-04-07)

---
_最后更新：2026-04-07_
