# A2A Protocol (Agent-to-Agent)
> Agent 间的"HTTP" — 标准化 Agent 通信协议，50+ 企业支持

## 一句话定义
A2A 是 Agent-to-Agent 通信协议，解决跨框架 Agent 互操作问题。围绕 Task 生命周期组织通信，Agent Card 提供发现机制。

## 核心概念

### 1. Agent Card — 能力声明与发现
Agent 的"名片"，JSON 格式，发布在 `/.well-known/agent.json`。

类比：**DNS for Agents** — 每个 Agent 通过标准路径宣告自己的存在和能力。

```json
{
  "name": "my-agent",
  "url": "https://my-agent.example.com",
  "capabilities": {"streaming": true, "pushNotifications": true},
  "skills": [{"id": "code-review", "name": "Code Review"}]
}
```

### 2. Task Lifecycle — 任务生命周期
```
submitted → working → input-required → working → completed
                                ↘ failed / cancelled
```
核心：A2A 围绕 **Task**（而非 Message）组织通信。每个 Task 有唯一 ID、状态机、消息历史和产出物（Artifact）。

### 3. 三层协议栈（2026 共识架构）
```
┌─────────────────────────────────┐
│  A2A Layer (Agent Network)      │  ← Agent间协作、任务委派
├─────────────────────────────────┤
│  MCP Layer (Tool Interface)     │  ← Agent访问工具/API/数据
├─────────────────────────────────┤
│  WebMCP Layer (Web Access)      │  ← Agent访问Web资源
└─────────────────────────────────┘
```

**MCP 纵向（Agent→工具），A2A 横向（Agent→Agent）。互补而非竞争。**

### 4. Transport-Agnostic 设计
- **Layer 1**: Canonical Data Model (Protocol Buffers)
- **Layer 2**: Abstract Operations (语义定义)
- **Layer 3**: Protocol Bindings (JSON-RPC / gRPC / HTTP)

### 5. Agent Federation — Agent 联邦
去中心化 Agent 协作：Agent Card Discovery → 能力匹配 → Task 委派

## 关键洞察

1. **Task-centric > Message-centric** — 围绕任务而非消息组织通信
2. **Agent Card = Agent 的 DNS** — 标准化发现机制
3. **Transport-agnostic** — 可用 JSON-RPC、gRPC 或自定义协议
4. **解决框架锁定** — ADK/CrewAI/MAF 已支持，跨框架互操作成常态
5. **信任层缺失** — 当前 A2A 缺少身份验证和信任评估机制（Agent Trust Network 可填补）

## 代码示例

### 零依赖 A2A Agent（Python）
```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

AGENT_CARD = {
    "name": "my-a2a-agent",
    "url": "http://localhost:8000",
    "capabilities": {"streaming": False},
    "skills": [{"id": "research", "name": "Research"}]
}

class A2AHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/agent.json":
            self._json_response(AGENT_CARD)

    def do_POST(self):
        if self.path == "/tasks/new":
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            task = {"id": "task-1", "status": {"state": "completed"}, 
                    "artifacts": [{"parts": [{"text": "Research complete!"}]}]}
            self._json_response(task)

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.write(json.dumps(data))

HTTPServer(("0.0.0.0", 8000), A2AHandler).serve_forever()
```

## 关联
- [[mcp-protocol]] — MCP+A2A = Agent 互联网的 TCP/IP 栈
- [[multi-agent-framework-integration]] — A2A 解决跨框架互操作
- [[agent-trust-network]] — 信任层可填补 A2A 的安全缺口
- [[agent-engineering]] — A2A 是多 Agent 系统的通信基础

---
_最后更新：2026-04-16_
