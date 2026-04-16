# Agent Security & Safety
> AI Agent 的安全威胁与防护 — 从 Prompt Injection 到权限控制

## 一句话定义
AI Agent 安全包括 Prompt 注入防护、工具权限控制、数据泄露防护和沙箱执行，是 Agent 生产化的必要条件。

## 五大威胁模型

| 威胁 | 攻击方式 | 危害等级 |
|------|---------|---------|
| **Prompt Injection** | 通过用户输入注入恶意指令 | 🔴 高 |
| **Tool Misuse** | 滥用工具访问未授权资源 | 🔴 高 |
| **Data Exfiltration** | 通过输出泄露敏感数据 | 🟡 中 |
| **指令劫持** | 覆盖 Agent 的系统提示 | 🟡 中 |
| **权限提升** | 从受限操作跳转到高权限操作 | 🔴 高 |

## 防护模式

### 1. 输入验证层
```
用户输入 → 意图检测 → 恶意过滤 → 安全上下文 → Agent
```
- 检测间接注入（邮件/文档中的隐藏指令）
- 限制单次输入长度
- 对已知攻击模式做模式匹配

### 2. 工具权限层
```
Agent → 工具调用请求 → 权限检查 → 审计日志 → 执行/拒绝
```
- 最小权限原则：工具只能访问必要资源
- 白名单机制：只允许预定义的操作
- 审计日志：记录所有工具调用

### 3. 沙箱执行层
```
Agent 代码 → 沙箱环境 → 隔离执行 → 结果返回
```
- 文件系统隔离（chroot/docker）
- 网络隔离（只允许白名单域名）
- 资源限制（CPU/内存/时间）

### 4. 输出过滤层
```
Agent 输出 → 敏感信息检测 → 脱敏处理 → 用户
```
- PII 检测和脱敏
- 防止通过输出通道泄露数据
- 输出格式约束

## Guardrail 模式

```python
class Guardrail:
    """输入/输出安全守卫"""
    
    def check_input(self, user_input: str) -> bool:
        # 1. 检测注入攻击
        if self._detect_injection(user_input):
            return False
        # 2. 检查输入长度
        if len(user_input) > self.max_length:
            return False
        return True
    
    def check_output(self, agent_output: str) -> str:
        # 1. PII 脱敏
        output = self._redact_pii(agent_output)
        return output
```

## 安全检查清单

- [ ] 输入验证：检测 Prompt 注入
- [ ] 工具权限：最小权限 + 白名单
- [ ] 沙箱执行：隔离环境
- [ ] 输出过滤：PII 脱敏
- [ ] 审计日志：记录所有操作
- [ ] 速率限制：防止资源滥用
- [ ] 人工确认：高风险操作需人类批准

## 关键洞察

1. **安全不是附加功能** — 必须从架构层面内建
2. **深度防御** — 多层防护，单点失效不导致系统崩溃
3. **Agent 越强大，安全越重要** — 能力越大，滥用风险越大
4. **红队测试** — 定期模拟攻击，验证防护有效性

## 关联
- [[agent-engineering]] — 安全是 Agentic Engineering 的关键维度
- [[harness-engineering]] — Harness 的核心就是给 AI 装缰绳
- [[edge-agent-runtime]] — 边缘设备的安全约束更严格

---
_最后更新：2026-04-16_
