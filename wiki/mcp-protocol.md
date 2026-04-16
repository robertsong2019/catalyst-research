# MCP Protocol (Model Context Protocol)
> AI Agent 的"USB-C接口" — 标准化工具访问协议，97M+ 下载量

## 一句话定义
MCP 是一个开放协议，为 AI 应用与外部工具/数据源之间的**上下文交换**提供标准化方式。类似于 USB-C 统一了硬件接口，MCP 统一了 Agent 访问工具的方式。

## 核心架构

### 三层参与者
```
Host (AI应用，如 Claude Desktop / OpenClaw)
  └── Client (1:1 连接管理)
        └── Server (提供工具/资源/提示模板)
```

- **Host**: AI 应用本身，协调多个 Client
- **Client**: 每个 Client 维护一个与 Server 的 1:1 连接
- **Server**: 提供上下文和能力的程序，可本地或远程运行

### 三类能力
| 能力 | 说明 | 示例 |
|------|------|------|
| **Tools** | Agent 可调用的函数 | web_search、file_read、exec |
| **Resources** | 可读取的数据源 | 文件、数据库、API 响应 |
| **Prompts** | 预设的提示模板 | 代码审查、翻译、总结 |

### 两种 Transport
| Transport | 适用场景 | 特点 |
|-----------|---------|------|
| **stdio** | 本地进程间通信 | 最简单、最安全、Agent 集成首选 |
| **Streamable HTTP** | 远程服务 | 需要 OAuth 认证、支持无状态模式 |

## 关键洞察

1. **MCP 只管协议，不管 AI 应用** — 不涉及 LLM 如何推理或管理上下文
2. **JSON-RPC 2.0 基础** — 工具调用与 LLM function calling 高度一致
3. **stdio 最适合 Agent 集成** — 简单、安全、无需网络配置
4. **与 A2A 互补** — MCP 纵向（Agent→工具），A2A 横向（Agent→Agent）
5. **97M+ 下载量** — 已成为工具访问事实标准（2026-04）

## 代码示例

### 零依赖 MCP Server（Python）
```python
import json, sys

def handle_request(request):
    if request["method"] == "tools/list":
        return {
            "tools": [{
                "name": "web_search",
                "description": "Search the web",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"]
                }
            }]
        }
    elif request["method"] == "tools/call":
        tool_name = request["params"]["name"]
        args = request["params"]["arguments"]
        if tool_name == "web_search":
            return {"content": [{"type": "text", "text": f"Results for: {args['query']}"}]}

for line in sys.stdin:
    request = json.loads(line)
    response = {"jsonrpc": "2.0", "id": request.get("id"), "result": handle_request(request)}
    print(json.dumps(response), flush=True)
```

## 与 OpenClaw 的关联
- OpenClaw 可将自身工具（web_search、memory_search、exec）暴露为 MCP Server
- 实现路径：STDIO 模式 MVP → MCP Inspector 验证 → Streamable HTTP + OAuth
- 研究笔记：[2026-04-04-mcp-protocol-deep-dive.md](../exploration-notes/2026-04-04-mcp-protocol-deep-dive.md)

## 关联
- [[a2a-protocol]] — A2A 与 MCP 互补，三层协议栈
- [[multi-agent-framework-integration]] — MCP 作为工具层的标准接口
- [[agent-engineering]] — MCP 是 Agentic Engineering 的基础设施
- [[tool-design-principles]] — MCP Server 设计遵循零依赖原则

---
_最后更新：2026-04-16_
