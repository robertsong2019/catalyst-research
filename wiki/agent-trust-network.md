# Agent Trust Network
> 多 Agent 系统的信任层 — 去中心化信任评估，填补 A2A 协议的安全缺口

## 一句话定义
Agent Trust Network 用 PageRank 式信任传播算法，为多 Agent 系统提供去中心化的信任评估机制，解决 A2A 协议缺失的身份验证和信任评估问题。

## 问题背景

A2A 协议的三层架构缺少第四层：
```
当前：MCP(工具) + A2A(Agent) + WebMCP(Web)
缺失：Trust Layer（信任层）
```

关键问题：
- Agent A 如何验证 Agent B 的身份？
- 如何防止恶意 Agent 注入虚假信息？
- 跨组织协作时的权限如何管理？

## 信任传播模型

### 核心算法：PageRank 变体
```
Trust(A) = (1-d) + d × Σ [Trust(Bi) / OutDegree(Bi)]
```
- d = 阻尼因子（通常 0.85）
- Bi = 所有信任 A 的 Agent
- OutDegree(Bi) = Bi 信任的 Agent 总数

### 四种 Agent 行为模型

| 行为 | 描述 | 信任影响 |
|------|------|---------|
| **Cooperative（合作）** | 提供真实信息，诚实反馈 | 正向 |
| **Neutral（中立）** | 参与但不主动贡献 | 中性 |
| **Malicious（恶意）** | 提供虚假信息 | 负向 |
| **Adversarial（对抗）** | 主动攻击信任系统 | 强负向 |

### 信任衰减
```
Trust(t) = Trust(0) × e^(-λt)
```
不活跃的 Agent 信任度随时间衰减，活跃 Agent 通过正向互动维持信任。

## 与 A2A 的集成方案

### Agent Card 扩展
```json
{
  "name": "trusted-agent",
  "url": "https://agent.example.com",
  "trust": {
    "score": 0.87,
    "certified_by": ["agent-alpha", "agent-beta"],
    "last_verified": "2026-04-14T00:00:00Z"
  }
}
```

### 信任验证流程
```
1. 发现 Agent Card
2. 查询 Trust Network 获取信任分数
3. 低于阈值 → 拒绝合作 / 要求额外验证
4. 合作后 → 根据结果更新信任分数
```

## 关键洞察

1. **信任是 A2A 的缺失层** — 没有信任的联邦 = 没有安全的互联网
2. **去中心化 > 中心化** — 无单点故障，自组织
3. **衰减机制必要** — 防止"一次性信任"被滥用
4. **行为驱动** — 信任基于实际行为而非声明的能力

## 关联
- [[a2a-protocol]] — A2A 缺少信任层，Trust Network 填补缺口
- [[multi-agent-framework-integration]] — 多 Agent 系统需要信任评估
- [[agent-engineering]] — 信任是 Agent 联邦的基础

---
_最后更新：2026-04-16_
