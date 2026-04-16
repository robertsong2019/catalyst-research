# Tool Design Principles
> 工具设计三原则：零依赖、AI 友好、结构化输出

## 一句话定义
好的 Agent 工具遵循：零依赖优先（纯 Python/Node.js）、AI 友好（结构化 I/O）、同时输出 Markdown + JSON。

## 三大原则

### 1. 零依赖优先
- 纯 Python 3 / Node.js 标准库实现
- 外部依赖仅在必要时引入
- 开箱即用，无需复杂安装

### 2. AI 友好
- 结构化输入/输出（JSON Schema）
- 清晰的错误信息
- 同时输出 Markdown（人类）+ JSON（机器）

### 3. 渐进增强
- 核心功能零配置可用
- 高级功能可自定义
- 不强制用户做选择

## 工具接口规范

```python
def tool_function(input: str, **options) -> dict:
    """每个工具返回统一格式"""
    return {
        "success": True,
        "data": {...},
        "markdown": "人类可读的摘要",
        "metadata": {"source": "...", "timestamp": "..."}
    }
```

## 关联
- [[agent-engineering]] — 工具是 Agent 的核心能力
- [[mcp-protocol]] — MCP 标准化了工具的访问方式
- [[harness-engineering]] — Harness 的工具安全约束
- [[project-lessons]] — 工具设计的实践经验

---
_最后更新：2026-04-16_
