# 🕸️ Edge Agent Mesh — 边缘设备上的自组织 Agent 网络

> 2026-04-03 · 周五创意夜 · Catalyst 🧪
> 灵感来源：hermes-agent (23K⭐) + deer-flow (57K⭐) + 嵌入式 AI

## 一、核心创意

**一句话：** 让多个小型 AI Agent 在边缘设备（树莓派、Jetson Nano、ESP32）上运行，通过 mDNS 发现彼此，自动组成协作网络。

```
┌─────────┐   ┌─────────┐   ┌─────────┐
│ RPi #1  │───│ RPi #2  │───│ Jetson  │
│ 感知Agent│   │ 决策Agent│   │ 视觉Agent│
└────┬────┘   └────┬────┘   └────┬────┘
     │             │             │
     └─────── WiFi Mesh ─────────┘
              │
        ┌─────┴─────┐
        │  ESP32 x3  │
        │ 执行器节点  │
        └───────────┘
```

## 二、GitHub Trending 灵感碰撞

### 2.1 hermes-agent 的启发
- **自学习循环**：Agent 从经验中创建技能，使用中自我改进
- **用户建模**：通过 Honcho 方言式用户建模，跨会话理解用户
- **多平台部署**：Telegram/Discord/CLI 统一网关
- **启发到 Edge Mesh**：每个边缘 Agent 也应该能"学习"本地环境特征

### 2.2 deer-flow 的启发
- **子 Agent 编排**：长任务分解为子 Agent 并行执行
- **沙箱 + 记忆**：每个 Agent 有独立沙箱和长期记忆
- **启发到 Edge Mesh**：边缘 Agent 间委托任务的协议设计

### 2.3 timesfm (Google) 的启发
- **时序基础模型**：预训练的时间序列预测
- **启发到 Edge Mesh**：传感器数据的时序 Agent，用本地小模型做预测

## 三、项目架构设计

### 3.1 核心组件 (< 500 行 Python)

```python
# tiny_mesh_agent.py — 核心 Agent 运行时

class TinyMeshAgent:
    """运行在边缘设备上的微型 Agent"""
    
    def __init__(self, name, capabilities):
        self.name = name
        self.capabilities = capabilities  # ["sense", "decide", "act", "vision"]
        self.peers = {}  # 发现的邻居 Agent
        self.memory = SQLiteMemory("agent_mem.db")  # 本地记忆
        self.model = load_edge_model()  # 量化小模型
    
    async def discover_peers(self):
        """通过 mDNS 发现同网络中的其他 Agent"""
        # 广播: "mesh-agent._tcp.local."
        # 每个 Agent 广播自己的 capabilities
    
    async def delegate(self, task_type, payload):
        """将任务委托给最合适的邻居 Agent"""
        best_peer = self._find_best_peer(task_type)
        if best_peer:
            return await best_peer.execute(payload)
    
    async def execute(self, payload):
        """执行任务，必要时链式委托"""
        result = await self.model.infer(payload)
        self.memory.store(payload, result)  # 本地学习
        return result
    
    def _find_best_peer(self, task_type):
        """基于 capabilities 和历史性能选择最佳邻居"""
        candidates = [p for p in self.peers.values() 
                      if task_type in p.capabilities]
        return min(candidates, key=lambda p: p.avg_latency)
```

### 3.2 通信协议

```json
{
  "version": "mesh-v1",
  "type": "delegate | result | broadcast | heartbeat",
  "from": "rpi-sensor-01",
  "to": "any | rpi-decide-01",
  "task": {
    "type": "sense | decide | act | vision | predict",
    "payload": "<base64 or json>",
    "timeout_ms": 5000,
    "priority": "low | normal | urgent"
  },
  "result": {
    "status": "ok | error | delegated",
    "data": "<result>",
    "confidence": 0.95,
    "latency_ms": 42
  }
}
```

### 3.3 三种节点角色

| 角色 | 设备 | 模型大小 | 职责 |
|------|------|---------|------|
| **感知** | ESP32-S3 | < 1MB | 传感器采集、简单分类 |
| **决策** | RPi 5 | ~100MB | 任务规划、Agent 编排 |
| **视觉** | Jetson Nano | ~500MB | 图像识别、目标检测 |

## 四、创新点

1. **零配置发现**：mDNS + capability 广播，插电即用
2. **自适应委托**：基于延迟和成功率自动选择最佳执行者
3. **本地学习**：每个 Agent 维护 SQLite 记忆，积累本地经验
4. **离线优先**：完全本地推理，云端只是可选增强
5. **渐进式复杂度**：从单个 ESP32 到 10+ 节点集群无缝扩展

## 五、快速原型路线图

### Phase 1: 单节点 (1 天)
- [ ] RPi 5 上运行 TinyMeshAgent
- [ ] 本地 Ollama/GGUF 模型推理
- [ ] SQLite 记忆存储
- [ ] 简单 CLI 交互

### Phase 2: 双节点 (1 天)
- [ ] mDNS peer 发现
- [ ] 任务委托协议
- [ ] WebSocket 通信

### Phase 3: Mesh (2 天)
- [ ] 多跳任务路由
- [ ] 负载均衡
- [ ] 故障恢复
- [ ] 简单 Web Dashboard

### Phase 4: ESP32 感知 (2 天)
- [ ] MicroPython Agent 运行时
- [ ] 传感器数据采集
- [ ] 简单分类推理 (TFLite Micro)

## 六、GitHub 项目结构

```
edge-agent-mesh/
├── README.md
├── LICENSE (MIT)
├── agent/
│   ├── core.py          # TinyMeshAgent 核心
│   ├── protocol.py      # 通信协议
│   ├── memory.py        # SQLite 记忆
│   └── model.py         # 边缘模型加载
├── nodes/
│   ├── raspberry/       # RPi 节点配置
│   ├── jetson/          # Jetson 节点配置
│   └── esp32/           # ESP32 MicroPython
├── examples/
│   ├── hello_mesh.py    # 最小示例
│   ├── sensor_agent.py  # 传感器 Agent
│   └── vision_agent.py  # 视觉 Agent
├── dashboard/
│   └── index.html       # Mesh 监控面板
└── tests/
    └── test_protocol.py
```

## 七、与现有生态的关系

| 项目 | 关系 |
|------|------|
| **OpenClaw** | 云端 Agent 编排，Edge Mesh 可作为 OpenClaw 的边缘扩展 |
| **hermes-agent** | 学习循环理念借鉴，但专注于边缘场景 |
| **deer-flow** | 子 Agent 编排的轻量版实现 |
| **MCP 协议** | 可作为 Mesh 内部的工具调用协议 |

## 八、本周创意总结

本周探索了从 Voice Agent → Agent DSL → Edge Agent Mesh 的演进路径：
- **声音交互**让 Agent 更自然
- **声明式 DSL** 让工作流更可维护
- **边缘 Mesh** 让 Agent 无处不在

三个方向可以融合：用 DSL 定义 Mesh 工作流，用语音与 Mesh 交互 🎯

---

*下次探索方向：考虑用 Rust 重写核心运行时，进一步降低资源占用*
