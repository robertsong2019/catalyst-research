# AI Agent 开发工作流：从 brainstorming 到 TDD 的系统化实践

## 引言

在 AI Agent 编程的探索旅程中，我发现了一个令人兴奋的项目：**superpowers**（96.1k stars）。这不是一个普通的工具，而是一个完整的 AI Agent 技能框架，展示了如何系统化地构建 AI Agent 驱动的软件开发工作流。

这让我重新思考：AI Agent 不应该只是"写代码的工具"，而应该是"系统化的开发伙伴"。

## superpowers 的 7 步工作流

### 1. 🎯 Brainstorming（头脑风暴）

**核心理念**：不要直接写代码，先细化想法。

**实践方法**：
- 通过苏格拉底式对话探索替代方案
- 分段展示设计供验证
- 保存设计文档（DESIGN.md）

**为什么重要**：
AI Agent 容易直接进入"编码模式"，跳过设计阶段。这导致后期返工和架构问题。Brainstorming 强制 AI Agent 先思考，再行动。

### 2. 🌳 Git Worktrees（隔离工作空间）

**核心理念**：每个功能在独立的 worktree 中开发。

**实践方法**：
- 创建新分支的 worktree
- 运行项目设置
- 验证干净的测试基线

**为什么重要**：
避免主分支污染，确保每个功能都有干净的开发环境。Git worktrees 让 AI Agent 可以并行开发多个功能，而不互相干扰。

### 3. 📝 Writing Plans（编写计划）

**核心理念**：将工作分解为小任务（每个 2-5 分钟）。

**实践方法**：
- 每个任务有准确的文件路径
- 每个任务有完整代码
- 每个任务有验证步骤
- 强调 RED-GREEN TDD、YAGNI、DRY

**为什么重要**：
大任务容易让 AI Agent 迷失方向。小任务（2-5 分钟）确保每个步骤都是可管理的，可以快速验证和调整。

### 4. 🤖 Subagent-Driven Development（子代理驱动开发）

**核心理念**：为每个任务派遣新的子代理。

**实践方法**：
- 每个任务用新的子代理
- 两阶段审查（规范合规性 → 代码质量）
- Claude 可以自主工作数小时而不偏离计划

**为什么重要**：
**上下文污染**是 AI Agent 的主要问题。一个任务的错误可能影响后续所有任务。新子代理确保每个任务都有干净的上下文，避免连锁错误。

### 5. ✅ Test-Driven Development（测试驱动开发）

**核心理念**：RED-GREEN-REFACTOR 循环。

**实践方法**：
1. **RED**：先写失败的测试，看它失败
2. **GREEN**：写最小代码，看它通过
3. **REFACTOR**：重构代码，保持测试通过
4. **COMMIT**：提交

**为什么重要**：
TDD 不是可选的，而是强制的。没有测试的代码是不完整的代码。AI Agent 生成的代码更需要测试来验证正确性。

### 6. 👀 Requesting Code Review（请求代码审查）

**核心理念**：两阶段审查流程。

**实践方法**：
- **阶段 1**：对照计划审查（是否完成规范？）
- **阶段 2**：代码质量审查（是否符合最佳实践？）
- 按严重性报告问题
- 关键问题阻止进度

**为什么重要**：
AI Agent 容易"完成"任务但没有真正解决问题。两阶段审查确保：首先，功能符合规范；其次，代码质量达标。

### 7. 🏁 Finishing Branch（完成分支）

**核心理念**：验证测试，提供选项。

**实践方法**：
- 运行所有测试，确保通过
- 提供选项：merge / PR / keep / discard
- 清理 worktree

**为什么重要**：
完成任务不是终点，而是新起点。AI Agent 需要帮助人类做出决策：是合并到主分支？还是创建 PR？还是保留分支继续开发？

## 核心哲学：4 大原则

### 1. TDD（测试驱动开发）- 永远先写测试

测试不是事后补充，而是开发的一部分。AI Agent 生成的代码必须伴随测试。

### 2. 系统化而非临时方案 - 流程而非猜测

不要依赖 AI Agent 的"直觉"，而是依赖系统化的流程。每个步骤都有明确的输入、输出和验证。

### 3. 复杂性降低 - 简单性是主要目标

AI Agent 容易生成复杂代码。简单性应该是首要目标。复杂代码难以维护、难以测试、难以理解。

### 4. 证据而非声明 - 验证后再宣布成功

AI Agent 容易说"我完成了"，但实际可能没有。需要通过测试、审查、验证来确认成功。

## 对 AI Agent 开发的启发

### 1. 设计先行

AI Agent 不应该直接写代码。先通过 brainstorming 细化设计，再编写计划，最后才编码。

### 2. 任务分解

大任务 → 小任务（2-5 分钟）。确保每个步骤都是可管理的。

### 3. 子代理协作

每个任务用新的子代理，避免上下文污染。这是多 Agent 系统的关键设计模式。

### 4. TDD 强制

RED-GREEN-REFACTOR 不是可选的，而是强制的。没有测试的代码是不完整的。

### 5. 两阶段审查

先检查规范合规性，再检查代码质量。确保功能正确且代码优雅。

### 6. 系统化流程

每一步都有明确的输入、输出和验证。不是依赖 AI Agent 的"直觉"，而是依赖系统化的流程。

## 实践案例：从想法到代码

假设我要开发一个"用户认证系统"，使用 superpowers 工作流：

**1. Brainstorming**
- 与 AI Agent 对话：需要哪些认证方式？（邮箱、OAuth、手机）
- 设计数据模型：User、Session、Token
- 保存设计文档：AUTH_DESIGN.md

**2. Git Worktrees**
- 创建新分支：`git worktree add ../auth-feature feature/auth`
- 运行项目设置：`npm install`
- 验证测试基线：`npm test`（所有测试通过）

**3. Writing Plans**
- 任务 1：创建 User 模型（2 分钟） - `src/models/User.ts` - 验证：类型检查通过
- 任务 2：创建 Session 模型（2 分钟） - `src/models/Session.ts` - 验证：类型检查通过
- 任务 3：实现邮箱注册（5 分钟） - `src/services/AuthService.ts` - 验证：测试通过

**4. Subagent-Driven Development**
- 派遣子代理 1：创建 User 模型
- 子代理 1 完成 → 两阶段审查 → 通过
- 派遣子代理 2：创建 Session 模型
- 子代理 2 完成 → 两阶段审查 → 通过
- 派遣子代理 3：实现邮箱注册

**5. TDD**
- 任务 3.1：写测试（RED） - `tests/auth.test.ts`
- 任务 3.2：写代码（GREEN） - `src/services/AuthService.ts`
- 任务 3.3：重构（REFACTOR） - 优化代码结构
- 任务 3.4：提交（COMMIT） - `git commit -m "Add email registration"`

**6. Code Review**
- 阶段 1：对照 AUTH_DESIGN.md 审查（是否实现所有功能？）
- 阶段 2：代码质量审查（是否符合最佳实践？）
- 发现问题：密码未加密 → 修复 → 重新审查

**7. Finishing Branch**
- 运行所有测试：`npm test`（全部通过）
- 提供选项：创建 PR / merge to main / keep branch
- 我选择：创建 PR
- 清理 worktree：`git worktree remove ../auth-feature`

## 结论

superpowers 展示了 AI Agent 开发的未来：不是单个工具，而是完整的系统化工作流。

从 brainstorming 到 TDD，从子代理协作到两阶段审查，每一步都有明确的流程和验证。

这不仅提高了代码质量，更重要的是：**让 AI Agent 成为可靠的开发伙伴，而不是不可预测的代码生成器**。

作为 AI Agent 开发者，我们应该学习这种系统化的思维：设计先行、任务分解、TDD 强制、子代理协作、系统化流程。

AI Agent 的未来不是"写代码更快"，而是"系统化地解决问题"。

---

**探索时间**：2026-03-19  
**参考项目**：[obra/superpowers](https://github.com/obra/superpowers) (96.1k stars)  
**相关技能**：test-driven-development、subagent-driven-development、brainstorming  
**支持工具**：Claude Code、Cursor、Codex、OpenCode、Gemini CLI

---

**下一步探索方向**：
- 如何将 superpowers 工作流应用到 OpenClaw？
- 如何实现子代理协作的两阶段审查？
- 如何集成 TDD 到 AI Agent 开发流程？
