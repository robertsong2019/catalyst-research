# 🔍 Code Archaeologist — 创意项目笔记

**日期:** 2026-04-06
**方向:** AI 快速原型开发

## 项目概念

**Code Archaeologist** — 将 git 历史转化为可读的"考古发掘报告"。

每个代码仓库都藏着一段故事，但 `git log --oneline` 只告诉你发生了什么，不告诉你故事的脉络。这个工具就像考古学家一样，逐层分析代码历史：

### 核心功能
1. **地层分析 (Phase Detection)** — 自动识别开发阶段：基础期、增长期、重构期等
2. **贡献者画像 (Contributor Profiles)** — 谁写了什么，谁是关键人物
3. **热点挖掘 (Hotspot Analysis)** — 哪些文件被修改最多（技术债务指标）
4. **文物分类 (Artifact Classification)** — 自动分类 commit：feature/fix/refactor/test/docs
5. **洞察生成 (Insights)** — Bus factor、周末活动、加速/减速趋势

### 设计哲学
- **零依赖** — 纯 Python，只依赖 git CLI
- **人类可读** — 输出是故事，不是数据表
- **通用适用** — 对任何 git 仓库都能运行

### 扩展想法
- 接入 LLM 生成更深入的故事叙述（"2024年夏天，这个项目经历了一次重大的架构转型..."）
- 生成可视化时间线（HTML/CSS）
- 对比分析：两个仓库的故事对比
- CI 集成：每次 release 自动生成发掘报告

### 与 AI Agent 的结合点
- Agent 可以定期对项目运行考古分析，追踪健康度
- 多仓库分析：Agent 巡检整个组织的技术演进
- 配合 code review：PR 合入后自动更新"最新地层"

## 关键学习
- git log 格式化解析技巧
- 时间序列分段算法（滑动窗口）
- commit message 分类的启发式规则
- 用统计方法检测项目健康指标

## 文件位置
`code-lab/code-archaeologist/` — 完整实现，已推送到 GitHub
