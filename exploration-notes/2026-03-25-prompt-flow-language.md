# Prompt Flow Language (PFL) - Creative Exploration

**探索时间:** 2026年3月25日 19:00 - 23:00  
**探索方向:** AI Agent Programming - Prompts as Programs  
**探索者:** 🤖

---

## 一、创意起源

### 1.1 问题空间

当前 Prompt Engineering 的问题：
- **文本碎片化** - Prompts 是散落的文本片段，缺乏结构
- **无类型安全** - 输入输出类型不明确，调试困难
- **难以组合** - 大型 prompt 难以模块化复用
- **版本混乱** - Prompt 版本管理靠文件名或注释
- **测试困难** - 没有单元测试框架
- **控制流弱** - 条件分支、循环靠 few-shot 硬编码

### 1.2 灵感来源

- **React/JSX** - 组件化的 UI 构建方式
- **Elm/ReasonML** - 函数式 + 类型安全的架构
- **DSL Design** - 领域特定语言设计
- **LangChain** - 但更轻量、更声明式
- **TypeScript** - 类型系统设计
- **Rust Macros** - 编译时元编程

### 1.3 核心创意

**Prompt Flow Language (PFL)** - 一种将 Prompts 视为类型安全程序的 DSL：

```
┌──────────────────────────────────────────────────────────┐
│                 Prompt Flow Language                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│   │  .pfl 源码  │───►│  PFL 编译器 │───►│ Prompt 输出 │ │
│   └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                  │                            │
│         ▼                  ▼                            │
│   ┌─────────────┐    ┌─────────────┐                   │
│   │  类型检查   │    │  优化/压缩  │                   │
│   └─────────────┘    └─────────────┘                   │
│                                                          │
│   Features:                                              │
│   ✅ 类型安全的输入输出                                  │
│   ✅ 组件化/模块化                                       │
│   ✅ 控制流 (if/else, map, filter)                      │
│   ✅ 变量插值                                            │
│   ✅ 版本管理                                            │
│   ✅ 单元测试                                            │
└──────────────────────────────────────────────────────────┘
```

---

## 二、语言设计

### 2.1 基本语法

```pfl
// hello.pfl - 基础示例

// 定义输入类型
input {
  name: string,
  language: "en" | "zh" | "ja"
}

// 定义输出类型
output {
  greeting: string,
  tone: "formal" | "casual"
}

// 主 prompt 模板
prompt greet(input) -> output {
  You are a friendly greeter.
  
  Generate a greeting for {name} in {language}.
  
  Return JSON:
  {
    "greeting": "<the greeting>",
    "tone": "<formal or casual>"
  }
}
```

### 2.2 组件系统

```pfl
// components/persona.pfl

// 可复用组件
component Persona(name: string, traits: string[]) {
  You are {name}.
  Your traits: {traits.join(", ")}.
  Respond in character.
}

// 使用组件
import { Persona } from "./components/persona.pfl"

prompt roleplay(input) {
  {Persona("Sherlock", ["analytical", "observant", "sarcastic"])}
  
  Analyze this case: {input.case_description}
}
```

### 2.3 控制流

```pfl
// control-flow.pfl

input {
  tasks: Task[],
  complexity: "simple" | "complex"
}

prompt processTasks(input) {
  You are a task processor.
  
  // 条件分支
  {if input.complexity == "complex"}
    Break down each task into subtasks.
  {else}
    Process tasks directly.
  {/if}
  
  // 循环处理
  {for task in input.tasks}
    Task: {task.name}
    Priority: {task.priority}
    ---
  {/for}
  
  // 过滤
  {let urgentTasks = input.tasks.filter(t => t.priority > 7)}
  
  Focus especially on these urgent tasks:
  {for task in urgentTasks}
    🔴 {task.name}
  {/for}
}
```

### 2.4 类型系统

```pfl
// types.pfl

// 自定义类型
type Task = {
  id: string,
  name: string,
  priority: 1..10,  // 范围类型
  status: "pending" | "in_progress" | "done",
  tags: string[]
}

type Analysis = {
  summary: string,
  confidence: 0.0..1.0,  // 浮点范围
  risks: Risk[]
}

// 泛型组件
component Analyzer<T>(data: T[]) {
  Analyze the following {T.name} items:
  {for item in data}
    - {item}
  {/for}
  
  Provide a structured analysis.
}
```

---

## 三、高级特性

### 3.1 Pipeline 组合

```pfl
// pipeline.pfl

// 定义多个阶段
prompt extract(text: string) -> { entities: Entity[] } {
  Extract all named entities from the text.
  Return as JSON with "entities" array.
}

prompt analyze(entities: Entity[]) -> { sentiment: string, topics: string[] } {
  Analyze the sentiment and topics of these entities.
  Return as JSON.
}

prompt summarize(analysis: Analysis) -> { summary: string } {
  Create a concise summary of the analysis.
}

// 组合成 pipeline
pipeline nlpPipeline(input: string) {
  extract -> analyze -> summarize
}

// 等价于:
// const entities = await extract(input)
// const analysis = await analyze(entities)
// const summary = await summarize(analysis)
```

### 3.2 条件路由

```pfl
// routing.pfl

input {
  query: string,
  userLevel: "beginner" | "intermediate" | "expert"
}

prompt route(input) {
  Route this query to the appropriate handler.
}

// 路由到不同的 prompt
route handleQuery(input) {
  beginner => explainSimple(input),
  intermediate => explainModerate(input),
  expert => explainTechnical(input)
}

prompt explainSimple(input) {
  Explain "{input.query}" in simple terms for a beginner.
  Use analogies and avoid jargon.
}

prompt explainModerate(input) {
  Explain "{input.query}" for someone with some background knowledge.
}

prompt explainTechnical(input) {
  Provide a technical explanation of "{input.query}".
  Include code examples if relevant.
}
```

### 3.3 测试框架

```pfl
// hello.test.pfl

import { greet } from "./hello.pfl"

test "greet in English" {
  input: { name: "Alice", language: "en" }
  expect: {
    greeting: contains("Alice"),
    tone: anyOf(["formal", "casual"])
  }
}

test "greet in Chinese" {
  input: { name: "李明", language: "zh" }
  expect: {
    greeting: contains("李明"),
    tone: "formal"  // 期望特定值
  }
}

// 运行测试: pfl test hello.test.pfl
```

### 3.4 版本管理

```pfl
// versioned.pfl

@version("2.0.0")
@deprecated("Use greetV2 instead")
prompt greet(input) {
  Say hello to {input.name}.
}

@version("2.1.0")
prompt greetV2(input) {
  You are a warm, friendly greeter.
  
  Generate a personalized greeting for {input.name}.
  Consider their language preference: {input.language}.
  
  Return JSON with greeting and tone.
}

// 版本锁定
import { greetV2 as greet } from "./versioned.pfl@2.1.0"
```

---

## 四、编译器架构

### 4.1 编译流程

```
┌─────────────────────────────────────────────────────────────┐
│                     PFL Compiler Pipeline                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │  Lexer   │──►│  Parser  │──►│  Type    │──►│  IR      │ │
│  │          │   │          │   │  Checker │   │  Gen     │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│       │              │              │              │       │
│       ▼              ▼              ▼              ▼       │
│   Tokens          AST         Typed AST      Prompt IR     │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│  │ Optimizer│──►│  Code    │──►│  Output  │               │
│  │          │   │  Gen     │   │          │               │
│  └──────────┘   └──────────┘   └──────────┘               │
│       │              │              │                      │
│       ▼              ▼              ▼                      │
│  Optimized IR    Target Code   Final Prompt               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 中间表示 (IR)

```typescript
// PFL IR 示例

interface PromptIR {
  type: "prompt";
  name: string;
  version: string;
  inputs: TypeDefinition[];
  outputs: TypeDefinition[];
  body: IRNode[];
}

interface IRNode {
  type: "text" | "interpolation" | "conditional" | "loop" | "component";
  // ...
}

// 编译后的 IR
const greetIR: PromptIR = {
  type: "prompt",
  name: "greet",
  version: "1.0.0",
  inputs: [
    { name: "name", type: "string" },
    { name: "language", type: "union", values: ["en", "zh", "ja"] }
  ],
  outputs: [
    { name: "greeting", type: "string" },
    { name: "tone", type: "union", values: ["formal", "casual"] }
  ],
  body: [
    { type: "text", value: "You are a friendly greeter.\n\n" },
    { type: "text", value: "Generate a greeting for " },
    { type: "interpolation", path: "name" },
    { type: "text", value: " in " },
    { type: "interpolation", path: "language" },
    // ...
  ]
};
```

### 4.3 输出格式

```typescript
// 编译输出选项

interface CompileOptions {
  format: "openai" | "anthropic" | "generic" | "executable";
  minify: boolean;
  includeTypes: boolean;
  targetRuntime: "node" | "browser" | "edge";
}

// OpenAI 格式输出
const openaiOutput = {
  messages: [
    { role: "system", content: "You are a friendly greeter." },
    { role: "user", content: "Generate a greeting for {{name}} in {{language}}..." }
  ],
  functions: [
    {
      name: "greeting_output",
      parameters: {
        type: "object",
        properties: {
          greeting: { type: "string" },
          tone: { enum: ["formal", "casual"] }
        }
      }
    }
  ]
};
```

---

## 五、实现计划

### 5.1 Phase 1: 核心语言 (MVP)

- [ ] Lexer & Parser (TypeScript + Chevrotain)
- [ ] 基础类型系统
- [ ] 变量插值
- [ ] 单个 prompt 编译

### 5.2 Phase 2: 组件系统

- [ ] import/export
- [ ] component 定义
- [ ] 组件组合
- [ ] 类型检查跨文件

### 5.3 Phase 3: 控制流

- [ ] if/else
- [ ] for 循环
- [ ] filter/map
- [ ] let 绑定

### 5.4 Phase 4: 高级特性

- [ ] Pipeline 语法
- [ ] 路由系统
- [ ] 测试框架
- [ ] 版本管理

### 5.5 Phase 5: 工具链

- [ ] VSCode 插件
- [ ] CLI 工具
- [ ] Playground
- [ ] 文档生成

---

## 六、与其他方案对比

| 特性 | PFL | LangChain | Promptfoo | DSPy |
|------|-----|-----------|-----------|------|
| **类型安全** | ✅ 编译时 | ❌ | ❌ | ✅ Python |
| **组件化** | ✅ 一等公民 | ✅ Chains | ❌ | ✅ Modules |
| **控制流** | ✅ 内置 | ✅ Python | ❌ | ✅ Python |
| **测试** | ✅ 内置 | ❌ | ✅ | ✅ |
| **版本管理** | ✅ 内置 | ❌ | ✅ | ❌ |
| **学习曲线** | 中等 | 高 | 低 | 高 |
| **运行时依赖** | 低 | 高 | 低 | 中 |
| **语言** | 专用 DSL | Python | YAML | Python |

---

## 七、创意延伸

### 7.1 PFL + Agents

```pfl
// agent.pfl

agent TaskAgent {
  capabilities: ["planning", "execution", "reflection"]
  
  state {
    currentTask: Task?,
    completedTasks: Task[],
    learnings: string[]
  }
  
  prompt plan(objective: string) -> Plan {
    Given objective: {objective}
    Current state: {state}
    
    Create a step-by-step plan.
    Break down into atomic tasks.
  }
  
  prompt execute(task: Task) -> Result {
    Execute task: {task}
    Apply relevant learnings: {state.learnings}
    
    Report progress and any issues.
  }
  
  prompt reflect(result: Result) -> Learning {
    Analyze the execution result.
    What worked? What didn't?
    Generate learnings for future tasks.
  }
  
  // Agent 循环
  loop {
    plan -> execute -> reflect -> update(state)
  }
}
```

### 7.2 PFL + RAG

```pfl
// rag.pfl

prompt rag(query: string, context: Document[]) -> Answer {
  You are a helpful assistant with access to a knowledge base.
  
  Relevant documents:
  {for doc in context | take(3)}
    [Source: {doc.source}]
    {doc.content}
    ---
  {/for}
  
  Question: {query}
  
  Answer based on the documents. Cite sources.
}
```

### 7.3 PFL + Function Calling

```pfl
// tools.pfl

tool search(query: string) -> SearchResult[] {
  description: "Search the web for information"
  // 实际实现在外部
}

tool calculator(expression: string) -> number {
  description: "Evaluate mathematical expressions"
}

prompt agentWithTools(query: string) {
  You have access to these tools:
  {tools.description}
  
  User query: {query}
  
  Decide which tools to use and in what order.
  Think step by step.
}
```

---

## 八、总结与反思

### 8.1 核心价值

1. **类型安全** - 编译时捕获错误，而不是运行时
2. **可组合性** - 小 prompt 组合成大系统
3. **可测试性** - 每个 prompt 都可以独立测试
4. **可维护性** - 版本管理，清晰的依赖关系

### 8.2 潜在挑战

1. **学习曲线** - 新 DSL 需要学习
2. **工具链成熟度** - VSCode 支持等需要时间
3. **调试复杂性** - 编译时错误可能难以理解
4. **生态系统** - 需要积累组件库

### 8.3 下一步

1. 实现 MVP 编译器
2. 创建示例组件库
3. 构建在线 Playground
4. 写详细文档和教程

---

## 九、GitHub 项目规划

### 9.1 仓库结构

```
prompt-flow-language/
├── README.md
├── packages/
│   ├── compiler/          # 核心编译器
│   ├── cli/               # CLI 工具
│   ├── runtime/           # 运行时
│   └── vscode/            # VSCode 插件
├── examples/              # 示例代码
├── stdlib/                # 标准组件库
├── docs/                  # 文档
└── tests/                 # 测试
```

### 9.2 技术栈

- **编译器**: TypeScript + Chevrotain (parser generator)
- **运行时**: TypeScript, 支持多种 LLM SDK
- **CLI**: Node.js + Commander
- **Playground**: Next.js + Monaco Editor

---

*探索结束。这是一个将 Prompt Engineering 提升为软件工程的创意方向。*
