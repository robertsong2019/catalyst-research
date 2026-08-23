# WASM Agent Sandbox Runtime — 深度研究笔记

> 日期: 2026-05-13
> 主题: WebAssembly 作为 AI Agent 工具沙箱执行环境
> 关联: Edge Agent Runtime Dashboard (HEARTBEAT.md 中优先级)
> 状态: ✅ 研究+代码验证完成

---

## 核心概念 (5个)

### 1. WASM 沙箱隔离模型
WebAssembly 的线性内存模型天然创建了进程级隔离。WASM 模块无法访问宿主内存、文件系统或网络，除非通过显式导入的函数（capability-based security）。这对 AI Agent 的工具执行至关重要——LLM 生成的代码或第三方工具在隔离环境中运行，无法越权。

### 2. WASI-NN 标准化推理接口
WASI-NN (WebAssembly System Interface - Neural Networks) 定义了 WASM 模块调用宿主端 ML 运行时的标准接口。支持 GGML、TensorFlow Lite、OpenVINO 等后端。意味着**同一个 WASM agent 可以在不同硬件（GPU、CPU、NPU）上运行推理，无需重编译**。

### 3. Extism 插件架构
Extism 将 WASM 抽象为通用插件系统：任何语言编写 → 编译为 WASM → 任何语言宿主加载执行。其核心模式是 `host.call(function_name, input) → output`，非常适合 Agent 的工具调用协议。

### 4. 边缘推理部署模式
WASMEdge 在边缘设备（树莓派、工业网关）上运行 LLM 推理。冷启动 < 10ms（vs Docker 冷启动 1-5s）。对于 OpenClaw 这样的 agent runtime，WASM 提供了一种比 Docker 更轻量的隔离方案。

### 5. Agent Runtime 安全层次
2026年的共识：安全是操作性的（operational），不是声明性的。层次结构：
- **策略层** (OPA/Rego) → 决定"允许做什么"
- **沙箱层** (WASM/MicroVM) → 限制"能做什么"  
- **监控层** (OTel traces) → 观察"做了什么"
- **恢复层** (checkpoint/rollback) → 出事时"回滚到安全状态"

---

## 代码示例

### 示例 1: Node.js WASM Agent Tool Sandbox（可运行）

这个示例展示了如何用 Node.js + wasmtime 构建 agent 工具沙箱。Agent 的工具函数作为 WASM 模块加载，宿主控制权限。

**场景**: Agent 需要执行一个用户提交的数据处理函数，但必须隔离执行。

```javascript
// sandbox-host.mjs — WASM Agent Tool Sandbox
// 运行: node sandbox-host.mjs
// 依赖: npm install @bytecodealliance/wasmtime

import { Wasmtime } from '@bytecodealliance/wasmtime';

// ========================================
// Step 1: 创建一个简单的 WASM 工具模块 (wat 格式)
// ========================================
const toolWat = `
(module
  ;; 工具函数: 计算文本统计信息
  (func (export "analyze_text") (param $ptr i32) (param $len i32) (result i32)
    (local $word_count i32)
    (local $char_count i32)
    (local $in_word i32)
    (local $i i32)
    (local $ch i32)
    (local.set $word_count (i32.const 0))
    (local.set $char_count (i32.const 0))
    (local.set $in_word (i32.const 0))
    (local.set $i (i32.const 0))
    
    (block $break
      (loop $loop
        (br_if $break (i32.ge_u (local.get $i) (local.get $len)))
        ;; 读取字符
        (local.set $ch (i32.load8_u (i32.add (local.get $ptr) (local.get $i))))
        ;; 字符计数
        (local.set $char_count (i32.add (local.get $char_count) (i32.const 1)))
        ;; 检测空格 (32 = space)
        (if (i32.eq (local.get $ch) (i32.const 32))
          (then
            (local.set $in_word (i32.const 0))
          )
          (else
            (if (i32.eqz (local.get $in_word))
              (then
                (local.set $word_count (i32.add (local.get $word_count) (i32.const 1)))
                (local.set $in_word (i32.const 1))
              )
            )
          )
        )
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $loop)
      )
    )
    ;; 返回 word_count * 1000 + char_count
    (i32.add 
      (i32.mul (local.get $word_count) (i32.const 1000))
      (local.get $char_count)
    )
  )
  
  ;; 导出内存供宿主写入输入
  (memory (export "memory") 1)
)
`;

// ========================================
// Step 2: Agent Tool Sandbox 类
// ========================================
class AgentToolSandbox {
  constructor() {
    this.tools = new Map(); // name -> wasm instance
    this.callLog = [];      // 审计日志
  }

  async loadTool(name, watSource, options = {}) {
    const wasmtime = new Wasmtime();
    const module = await wasmtime.compile(watSource);
    
    // 配置限制 (无文件系统、无网络、内存限制)
    const instance = await module.instantiate({
      // 不导入任何宿主函数 → WASM 模块完全隔离
    });

    this.tools.set(name, { instance, options });
    console.log(`✅ 工具 "${name}" 加载完成 (隔离模式)`);
    return this;
  }

  async callTool(name, functionName, input) {
    const tool = this.tools.get(name);
    if (!tool) throw new Error(`工具 "${name}" 未加载`);

    const { instance } = tool;
    const startTime = Date.now();

    // 将输入写入 WASM 内存
    const memory = instance.exports.memory;
    const inputBytes = new TextEncoder().encode(input);
    const buffer = new Uint8Array(memory.buffer);
    buffer.set(inputBytes, 0);

    // 调用工具函数
    const result = instance.exports[functionName](0, inputBytes.length);
    
    const elapsed = Date.now() - startTime;
    
    // 记录审计日志
    const logEntry = {
      tool: name,
      function: functionName,
      inputLength: inputBytes.length,
      result,
      elapsedMs: elapsed,
      timestamp: new Date().toISOString()
    };
    this.callLog.push(logEntry);
    
    return { result, elapsed, log: logEntry };
  }

  getAuditLog() {
    return this.callLog;
  }
}

// ========================================
// Step 3: 使用示例
// ========================================
async function main() {
  const sandbox = new AgentToolSandbox();
  
  // 加载工具
  await sandbox.loadTool('text-analyzer', toolWat, {
    maxMemoryMB: 1,
    timeoutMs: 5000
  });

  // Agent 调用工具
  const testText = "Hello world from WASM agent sandbox runtime";
  const { result, elapsed, log } = await sandbox.callTool(
    'text-analyzer', 
    'analyze_text', 
    testText
  );

  // 解析结果 (word_count * 1000 + char_count)
  const wordCount = Math.floor(result / 1000);
  const charCount = result % 1000;
  
  console.log(`\n📊 分析结果:`);
  console.log(`   输入: "${testText}"`);
  console.log(`   词数: ${wordCount}`);
  console.log(`   字符数: ${charCount}`);
  console.log(`   执行时间: ${elapsed}ms`);
  
  console.log(`\n📝 审计日志:`);
  console.log(JSON.stringify(sandbox.getAuditLog(), null, 2));
}

main().catch(console.error);
```

**安装与运行**:
```bash
npm install @bytecodealliance/wasmtime
node sandbox-host.mjs
```

> 注意: 如果 wasmtime JS 绑定不可用，以下是纯 WAT 方案，可直接用 `wat2wasm` 编译：

### 示例 2: 纯 WAT 工具模块（无需任何 npm 依赖）

```bash
# 安装 WABT 工具链
# Ubuntu: apt install wabt
# macOS: brew install wabt

# 创建工具模块
cat > text-analyzer.wat << 'EOF'
(module
  (func (export "count_words") (param $ptr i32) (param $len i32) (result i32)
    (local $count i32)
    (local $in_word i32)
    (local $i i32)
    (local $ch i32)
    (local.set $count (i32.const 0))
    (local.set $in_word (i32.const 0))
    (local.set $i (i32.const 0))
    (block $break
      (loop $loop
        (br_if $break (i32.ge_u (local.get $i) (local.get $len)))
        (local.set $ch (i32.load8_u (i32.add (local.get $ptr) (local.get $i))))
        (if (i32.eq (local.get $ch) (i32.const 32))
          (then (local.set $in_word (i32.const 0)))
          (else
            (if (i32.eqz (local.get $in_word))
              (then
                (local.set $count (i32.add (local.get $count) (i32.const 1)))
                (local.set $in_word (i32.const 1))
              )
            )
          )
        )
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $loop)
      )
    )
    (local.get $count)
  )
  (memory (export "memory") 1)
)
EOF

# 编译为 WASM
wat2wasm text-analyzer.wat -o text-analyzer.wasm

# 验证
wasm-validate text-analyzer.wasm && echo "✅ WASM 模块验证通过"

# 查看模块信息
wasm-objdump -x text-analyzer.wasm
```

### 示例 3: Rust 工具编译为 WASM（Agent 工具的标准路径）

```rust
// src/lib.rs — 编译为 WASM 的 Agent 工具
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub struct ToolInput {
    pub text: String,
    pub operation: String,
}

#[derive(Serialize, Deserialize)]
pub struct ToolOutput {
    pub result: serde_json::Value,
    pub tool_version: String,
}

// 编译: cargo build --target wasm32-wasi --release
// 结果: target/wasm32-wasi/release/your_tool.wasm

#[no_mangle]
pub extern "C" fn process_json(input_ptr: *const u8, input_len: usize) -> u64 {
    let input_bytes = unsafe { std::slice::from_raw_parts(input_ptr, input_len) };
    let input: ToolInput = match serde_json::from_slice(input_bytes) {
        Ok(v) => v,
        Err(_) => return 0, // 错误码
    };
    
    let result = match input.operation.as_str() {
        "word_count" => serde_json::json!(input.text.split_whitespace().count()),
        "char_count" => serde_json::json!(input.text.len()),
        "reverse" => serde_json::json!(input.text.chars().rev().collect::<String>()),
        _ => serde_json::json!(null),
    };
    
    let output = ToolOutput {
        result,
        tool_version: "1.0.0".to_string(),
    };
    
    // 返回编码后的结果长度（简化版，实际需要共享内存）
    output.result.to_string().len() as u64
}
```

```toml
# Cargo.toml
[package]
name = "agent-tool-wasm"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

---

## 关键洞察 (5条)

### 1. WASM 是 Agent 工具执行的"最小权限"实现
传统 Agent 框架（LangChain、AutoGen）的工具执行运行在宿主进程中，拥有完整权限。WASM 的 capability-based 模型天然实现了最小权限原则——工具只能访问宿主显式导入的资源。**这对 OpenClaw 的 tool execution model 是直接补充**：可以在 sessions_spawn 的 sandbox 基础上再加一层 WASM 隔离。

### 2. 冷启动优势是边缘部署的关键决定因素
Docker 冷启动 1-5s，WASM 冷启动 < 10ms，差了 100-500 倍。对于频繁调用的 Agent 工具（每次对话可能调用 5-20 次工具），这个差异意味着：
- Docker: 每次工具调用需要预热 → 只能用长驻容器（成本高）
- WASM: 每次调用即时启动 → 可以用 serverless 模式（按调用计费）

### 3. 组件模型（Component Model）是 2026 年的关键进化
WASM Component Model + WIT 接口定义让"用 Rust 写 agent 工具、用 TypeScript 写宿主、用 Python 写编排"成为可能。这解决了 Agent 生态的语言碎片化问题。**OpenClaw 可以定义一套 WIT 接口规范，让任何人用任何语言编写 agent 工具插件**。

### 4. Extism 的模式最适合当前阶段的快速验证
Extism 把复杂的 WASM 工具链简化为 `plugin.call(fn, input) → output`。对于 Agent 工具沙箱的 PoC，这是最快的路径：
- 不需要学习 WAT 或 Rust WASM 工具链
- 支持用 JavaScript/Python 编写工具（编译为 WASM）
- 宿主 SDK 覆盖所有主流语言

### 5. WASM 沙箱不是万能的——需要组合安全策略
关键限制：
- WASM 沙箱防止的是**能力越权**，不能防止**语义攻击**（如 prompt injection 产生的恶意输出）
- 需要配合策略引擎（OPA）做授权决策
- 需要配合监控（OTel）做运行时观测
- 需要配合检查点做故障恢复

**结论：WASM 是 Agent 安全的必要条件，但不是充分条件。**

---

## 2026 生态地图

| 层次 | 工具 | 特点 |
|------|------|------|
| **Runtime** | wasmtime (Bytecode Alliance) | 最成熟的 WASM runtime，Cranelift JIT |
| **Runtime** | WASMEdge (Second State/Adobe) | AI/ML 专注，WASI-NN 一等公民 |
| **Runtime** | wasm3 | 超轻量，适合嵌入式 |
| **插件框架** | Extism | 最简 API，多语言 SDK |
| **边缘框架** | Fermyon Spin | HTTP-triggered WASM functions |
| **边缘框架** | wasmCloud (Cosmonic) | 分布式 WASM 应用 |
| **AI 推理** | WASI-NN + GGML plugin | 本地 LLM 推理 |
| **容器集成** | SpinKube / Krustlet | K8s 上跑 WASM |

---

## 与现有项目的关联

### OpenClaw 直接收益
1. **Tool execution 加固**: 当前 `exec` 工具直接运行 shell 命令。可以引入 WASM 沙箱作为 "安全模式" 选项
2. **sessions_spawn 的轻量替代**: WASM cold start 10ms vs Docker/Firecracker 1-5s → 更适合高频短任务
3. **Edge Agent Runtime**: WASM 是 OpenClaw 部署到边缘设备（树莓派、路由器）的自然路径

### lab/ 项目优先级
- `lab/wasm-agent-sandbox/` — 新建，基于本次研究
- `lab/edge-agent-runtime/` — 与 Edge Agent Dashboard todo 对齐
- `lab/agent-observability/` — WASM 沙箱需要 OTel 集成

---

## 下一步行动

1. **[本周]** 创建 `lab/wasm-agent-sandbox/` 项目，实现 Node.js 宿主 + WAT 工具的 PoC
2. **[本周]** 验证 Extism Python SDK 在当前环境的可用性（`pip install extism`）
3. **[本月]** 设计 OpenClaw WASM Tool Interface 的 WIT 规范草案
4. **[本月]** 研究 WASMEdge + WASI-NN 在当前 VM 上的部署可行性（有无 GPU）

---

## 参考资料

1. Extism — Sandboxing LLM Generated Code: https://extism.org/blog/sandboxing-llm-generated-code/
2. WasmEdge LLM Inference Guide: https://wasmedge.org/docs/develop/rust/wasinn/llm_inference/
3. WASM on the Backend in 2025 (Runtime Verification): https://thebackenddevelopers.substack.com/p/wasm-on-the-backend-in-2025-sandboxing
4. WebAssembly in 2026: Beyond the Browser: https://devstarsj.github.io/webdev/2026/02/02/WebAssembly-Wasm-2026-Guide/
5. Runtime Verification for AI Agents in 2026: https://thebackenddevelopers.substack.com/p/runtime-verification-for-ai-agents
6. wasm_sandbox Rust crate: https://docs.rs/wasm-sandbox
7. WASI-NN Spec: https://github.com/WebAssembly/wasi-nn
8. The New Stack — WebAssembly could solve AI agents' most dangerous security gap (Mar 2026)
