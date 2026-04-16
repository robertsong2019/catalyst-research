# Edge Agent Runtime
> 轻量级边缘 AI Agent 运行时 — 在资源受限设备上运行智能代理

## 一句话定义
Edge Agent Runtime 是专为资源受限设备（IoT、嵌入式、边缘计算）设计的 Agent 运行时，核心特点：零依赖、模块化、可插拔组件、支持 SLM（小语言模型）。

## 核心架构

```
┌─────────────────────────────────────────┐
│         Agent Loop (核心循环)            │
│  Observe → Think → Act → Learn          │
└────────┬────────────────────────┬───────┘
         │                        │
    ┌────▼────┐           ┌───────▼──────┐
    │ Memory  │           │   Tools     │
    │  (可插拔)│           │  (可插拔)   │
    └─────────┘           └─────────────┘
         │                        │
    ┌────▼────────────────────────▼────┐
    │      Model Loader (可插拔)        │
    │  - ONNX Runtime (MLReasoner)     │
    │  - TinyLlama / Phi-3 (SLM)       │
    └───────────────────────────────────┘
```

## 三大设计原则

1. **零依赖核心** — 纯 Python/Node.js 实现，无外部依赖
2. **可插拔组件** — Memory、Tools、Model Loader 可独立替换
3. **边缘优先** — 优化内存占用、启动速度、功耗

## 核心组件

### 1. Agent Loop（Agent 循环）
```python
def agent_loop():
    while True:
        # Observe: 感知环境
        observation = observe()

        # Think: 推理决策
        action = think(observation, memory)

        # Act: 执行动作
        result = act(action)

        # Learn: 记录经验
        memory.add(observation, action, result)
```

### 2. Model Loader（模型加载器）
- **ONNX Runtime**: 推理引擎，支持量化模型
- **SLM 支持**: TinyLlama-1.1B、Phi-3-mini (3.8B)
- **量化**: 4-bit/8-bit 量化，内存占用 < 1GB

### 3. Memory System（记忆系统）
- **Episodic Memory**: 事件级记忆（会话）
- **Semantic Memory**: 语义记忆（知识）
- **SQLite 持久化**: 边缘设备友好

## Edge AI 趋势（2026）

| 趋势 | 说明 | 影响 |
|------|------|------|
| **SLM 成熟** | 1-4B 模型性能提升 | 边缘设备可运行强推理 |
| **量化普及** | 4-bit 量化损失 < 2% | 内存占用降低 4 倍 |
| **本地部署** | 隐私 + 延迟优势 | 智能家居、工业物联网 |
| **MicroPython** | 嵌入式 Python 生态 | MCU 级 Agent 成为可能 |

## 关键洞察

1. **边缘 ≠ 弱化** — 通过量化 + SLM，边缘设备可实现强推理
2. **模块化 > 集成** — 可插拔组件适应不同硬件
3. **功耗是硬约束** — 边缘 Agent 必须考虑电池寿命
4. **隐私优势** — 数据不上云，本地推理

## 关联
- [[agent-memory-architecture]] — 边缘 Agent 的简化记忆系统
- [[edge-ai-trends]] — 边缘 AI 的整体趋势分析
- [[agent-engineering]] — 边缘 Agent 是 Agentic Engineering 的场景之一

---
_最后更新：2026-04-16_
