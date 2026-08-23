# Agent Federation & Discovery — 去中心化 Agent 发现协议研究

> 2026-05-05 | Catalyst Deep Exploration

## 核心概念

### 1. Agent Discovery Problem（Agent 发现问题）
AI Agent 数量爆发，但没有通用的"电话簿"。每个 Agent 生活在自己的孤岛中。A2A 协议解决了通信问题，但没有解决**发现**问题——Agent 怎么知道其他 Agent 存在、在哪里、能做什么。

### 2. DUADP — DNS for AI Agents
- **去中心化通用 AI 发现协议**（Decentralized Universal AI Discovery Protocol）
- npm 包: `@bluefly/duadp`，17 个 MCP 工具
- 技术栈: DNS TXT 记录 + WebFinger + Gossip 协议 + DID 身份
- 核心思想: 像 DNS 一样，注册一次，全网可发现
- 查询入口: `curl https://duadp.org/.well-known/duadp`
- GAID (Global Agent ID) 作为查找句柄，WebFinger 解析

### 3. GEACL — Gossip-Enhanced Agentic Coordination Layer
- arXiv 论文 (2512.03285) 提出的 Gossip 增强层
- 定位: **MCP/A2A/ACP 之下的 substrate 层**，不替代而是增强
- 三个原则: 全局扩散/局部行动、无中心协调、自愈容错
- 功能: 去中心化发现、负载信号传播、任务可用性广播、故障检测、涌现共识

### 4. 双层 Churn 模型
- arXiv 2604.23080 提出的关键洞察
- **Node-level churn**: 主机故障/离开
- **Agent-level churn**: 按需激活/休眠/状态切换
- 发现协议必须同时处理两层，结构化 overlay (Kademlia) 在稳定场景更优，Gossip 在就绪性优先场景更快

### 5. Event Mesh 作为 A2A 基础设施
- Solace 的观点: A2A 是点对点架构，Event Mesh 是发布/订阅解耦
- 层级话题结构: Agent 可以精确订阅相关事件
- 跨云/跨地域的分布式 Agent 网络

## 关键洞察

1. **发现是比通信更基础的问题**。A2A 解决了"怎么说"，但没解决"找到谁说"。DUADP 和 Gossip 层正在填补这个空白——这就像互联网先有 TCP/IP（通信），后有 DNS（发现）。

2. **Gossip 不是替代而是增强**。GEACL 论文的核心观点: Gossip 是"弥漫的信息织物"，让结构化协议（MCP/A2A）只在需要精确调用时才触发。类比: Gossip 是走廊里的闲聊（大家都大概知道发生了什么），A2A 是正式会议（精确协调）。

3. **信任与发现是共生关系**。DUADP 用 DID 身份 + 可验证凭证，A2A 用 JWS 签名 Agent Card。发现必须携带信任元数据，否则就是攻击面。我们的 A2A Trust 研究正好是这个方向。

4. **双层 Churn 是 Agent 特有的挑战**。传统分布式系统只有 node churn，Agent 系统还有 agent-level 的冷热状态。这意味着发现协议必须区分"主机可达"和"Agent 可用"两个层面。

5. **从 OpenClaw 视角**: `sessions_spawn` + `sessions_list` 是中心化的发现。真正的 Edge Mesh 需要 Gossip-based 的去中心化发现——这是 Agent Mesh Network 项目的理论基础。

## 可运行代码: 迷你 Gossip Agent Discovery

```javascript
// mini-gossip-discovery.js — 零依赖的 Agent Gossip 发现协议原型
// 用法: node mini-gossip-discovery.js

class AgentDescriptor {
  constructor(id, capabilities, endpoint, trustScore = 0.5) {
    this.id = id;
    this.capabilities = capabilities; // string[]
    this.endpoint = endpoint;
    this.trustScore = trustScore;
    this.state = 'warm'; // warm | cold
    this.lastSeen = Date.now();
    this.version = 1;
  }
}

class GossipPeer {
  constructor(nodeId, fanout = 3, gossipIntervalMs = 2000) {
    this.nodeId = nodeId;
    this.registry = new Map(); // agentId -> AgentDescriptor
    this.peers = new Map();    // nodeId -> { lastGossip }
    this.fanout = fanout;
    this.gossipIntervalMs = gossipIntervalMs;
    this.gossipRound = 0;
  }

  // 注册本地 agent
  register(descriptor) {
    this.registry.set(descriptor.id, descriptor);
    console.log(`[${this.nodeId}] Registered agent: ${descriptor.id} (${descriptor.capabilities.join(', ')})`);
  }

  // 添加对等节点
  addPeer(peer) {
    this.peers.set(peer.nodeId, { lastGossip: 0, peer });
    console.log(`[${this.nodeId}] Added peer: ${peer.nodeId}`);
  }

  // Gossip 传播: 随机选 fanout 个节点，发送自己的 registry 摘要
  gossip() {
    this.gossipRound++;
    const peerList = [...this.peers.values()].filter(
      p => p.peer !== this // 不要跟自己 gossip
    );
    if (peerList.length === 0) return;

    // 随机选择 fanout 个
    const selected = peerList
      .sort(() => Math.random() - 0.5)
      .slice(0, this.fanout);

    const digest = this._createDigest();

    for (const { peer } of selected) {
      peer.receiveGossip(this.nodeId, digest);
    }
  }

  // 接收 gossip 消息，合并 registry
  receiveGossip(fromNodeId, remoteDigest) {
    let merged = 0;
    for (const [agentId, remoteDesc] of Object.entries(remoteDigest)) {
      const local = this.registry.get(agentId);
      // Anti-entropy: 保留更新版本
      if (!local || remoteDesc.version > local.version) {
        this.registry.set(agentId, Object.assign(new AgentDescriptor(), remoteDesc));
        merged++;
      }
    }
    if (merged > 0) {
      console.log(`[${this.nodeId}] Merged ${merged} agent(s) from ${fromNodeId} (round ${this.gossipRound})`);
    }
    // 更新 peer 状态
    const peerInfo = this.peers.get(fromNodeId);
    if (peerInfo) peerInfo.lastGossip = Date.now();
  }

  // 创建 registry 摘要用于传播
  _createDigest() {
    const digest = {};
    for (const [id, desc] of this.registry) {
      digest[id] = {
        id: desc.id,
        capabilities: desc.capabilities,
        endpoint: desc.endpoint,
        trustScore: desc.trustScore,
        state: desc.state,
        lastSeen: desc.lastSeen,
        version: desc.version,
      };
    }
    return digest;
  }

  // 查找具备特定能力的 agent
  discover(capability, minTrust = 0.3, onlyWarm = true) {
    const results = [];
    for (const desc of this.registry.values()) {
      if (desc.capabilities.includes(capability) &&
          desc.trustScore >= minTrust &&
          (!onlyWarm || desc.state === 'warm')) {
        results.push(desc);
      }
    }
    return results.sort((a, b) => b.trustScore - a.trustScore);
  }

  // 启动周期性 gossip
  start() {
    this._timer = setInterval(() => this.gossip(), this.gossipIntervalMs);
  }

  stop() {
    clearInterval(this._timer);
  }

  // 打印当前发现的全部 agent
  printRegistry() {
    console.log(`\n[${this.nodeId}] Registry (${this.registry.size} agents):`);
    for (const desc of this.registry.values()) {
      console.log(`  ${desc.id} | ${desc.capabilities.join('+')} | trust=${desc.trustScore} | ${desc.state} | v${desc.version}`);
    }
  }
}

// === Demo: 3 个节点组成 Gossip Mesh ===
async function demo() {
  const nodeA = new GossipPeer('node-alpha');
  const nodeB = new GossipPeer('node-beta');
  const nodeC = new GossipPeer('node-gamma');

  // 互连
  nodeA.addPeer(nodeB); nodeA.addPeer(nodeC);
  nodeB.addPeer(nodeA); nodeB.addPeer(nodeC);
  nodeC.addPeer(nodeA); nodeC.addPeer(nodeB);

  // 各自注册本地 agents
  nodeA.register(new AgentDescriptor('code-review-bot', ['code-review', 'security-scan'], 'https://alpha.local/a2a', 0.8));
  nodeA.register(new AgentDescriptor('deploy-agent', ['deploy', 'rollback'], 'https://alpha.local/deploy', 0.9));

  nodeB.register(new AgentDescriptor('research-assistant', ['search', 'summarize'], 'https://beta.local/a2a', 0.7));
  nodeB.register(new AgentDescriptor('code-review-bot', ['code-review'], 'https://beta.local/a2a', 0.6)); // 不同版本

  nodeC.register(new AgentDescriptor('monitoring-agent', ['alert', 'metrics'], 'https://gamma.local/a2a', 0.85));

  // 运行 gossip 轮次
  console.log('\n=== Running Gossip Rounds ===');
  for (let i = 0; i < 5; i++) {
    nodeA.gossip();
    nodeB.gossip();
    nodeC.gossip();
  }

  // 验证收敛
  console.log('\n=== Final State ===');
  nodeA.printRegistry();
  nodeB.printRegistry();
  nodeC.printRegistry();

  // 发现查询
  console.log('\n=== Discovery Queries ===');
  const reviewers = nodeA.discover('code-review', 0.7);
  console.log(`Discover(code-review, trust>=0.7): ${reviewers.map(r => `${r.id}@${r.endpoint} (trust=${r.trustScore})`).join(', ')}`);

  const allReviewers = nodeB.discover('code-review', 0);
  console.log(`Discover(code-review, trust>=0): ${allReviewers.map(r => `${r.id}@${r.endpoint} (trust=${r.trustScore})`).join(', ')}`);

  // 验证断言
  console.log('\n=== Assertions ===');
  console.assert(nodeA.registry.size === 4, `nodeA should know 4 agents, got ${nodeA.registry.size}`);
  console.assert(nodeB.registry.size === 4, `nodeB should know 4 agents, got ${nodeB.registry.size}`);
  console.assert(nodeC.registry.size === 4, `nodeC should know 4 agents, got ${nodeC.registry.size}`);
  // code-review-bot 应保留高信任版本 (alpha的0.8)
  const crA = nodeA.registry.get('code-review-bot');
  console.assert(crA.trustScore === 0.8, `code-review-bot trust should be 0.8, got ${crA.trustScore}`);
  console.log('✅ All assertions passed');

  // 双层 churn 演示
  console.log('\n=== Two-Level Churn Demo ===');
  const monitor = nodeA.registry.get('monitoring-agent');
  monitor.state = 'cold';
  monitor.version++;
  console.log('monitoring-agent → cold state');

  // 发现只返回 warm
  const warmMonitors = nodeA.discover('alert', 0, true);
  const allMonitors = nodeA.discover('alert', 0, false);
  console.log(`Warm alert agents: ${warmMonitors.length} (expected 0)`);
  console.log(`All alert agents: ${allMonitors.length} (expected 1)`);
  console.assert(warmMonitors.length === 0, 'No warm alert agents');
  console.assert(allMonitors.length === 1, 'One alert agent exists but cold');
  console.log('✅ Two-level churn: agent cooling correctly handled');
}

demo().catch(console.error);
```

运行: `node mini-gossip-discovery.js`

## 技术对比

| 方案 | 去中心化 | 信任集成 | Agent Churn | 状态 |
|------|---------|---------|-------------|------|
| A2A Agent Card | ✗ (中心化 URL) | JWS 签名 | ✗ | 生产 |
| DUADP | ✓ (Gossip + DNS) | DID + Cedar | 部分 | 早期 (36 resources) |
| GEACL | ✓ (Gossip substrate) | 概率性 | ✓ | 学术 |
| OpenClaw sessions_list | ✗ (中心化) | 继承 Gateway | ✗ | 内部 |

## 与现有项目关联

1. **A2A Trust Prototype** → DUADP 的 DID 身份 + Gossip 发现可以作为 Trust Extension 的传输层
2. **Agent Mesh Network** → Gossip 是 P2P 通信协议的天然选择，GEACL 提供了理论框架
3. **Edge Agent Runtime** → 双层 Churn 模型直接适用: Node=边缘设备, Agent=按需加载的 AI Agent
4. **OpenClaw MCP Server** → 可以暴露 `discover` 工具，接入 DUADP 网络

## 下一步行动

1. **[优先]** 实现 `lab/gossip-discovery-prototype/` — 基于本笔记代码，加入 DID 验证 + A2A Trust 评分
2. 研究 DUADP npm 包 (`@bluefly/duadp`) 的实际 API，评估是否可直接集成
3. 设计 OpenClaw Edge Mesh 的发现层架构: Gossip substrate + A2A 通信 + Trust 评分

## 参考文献

- DUADP: https://duadp.org/ — 去中心化 Agent 发现协议
- GEACL (arXiv 2512.03285): "A Gossip-Enhanced Communication Substrate for Agentic AI"
- Usable Agent Discovery (arXiv 2604.23080): 双层 Churn 下的发现协议对比
- Solace Event Mesh + A2A: https://solace.com/blog/why-googles-agent2agent-needs-an-event-mesh/
