# 2026-04-11 AI Shell Pipe - Unix哲学的AI管道

## 项目

**[ai-shell-pipe](https://github.com/robertsong2019/ai-shell-pipe)** - Unix哲学的AI Agent管道工具

## 核心洞察

Unix管道哲学 + AI Agent = 极简组合：

1. **每个Agent是一个命令** — `ai-translate`, `ai-summarize`, `ai-classify`...
2. **stdin → LLM → stdout** — 零框架开销
3. **管道组合** — `cat file | ai-summarize | ai-translate --to zh`
4. **可扩展** — 自定义agent只需继承PipeAgent

## 为什么这个方向有意义

- 当前AI Agent框架（LangChain, CrewAI等）越来越重
- 很多场景只需要单次LLM调用，不需要复杂的状态管理
- Unix管道已经证明了"组合 > 配置"的哲学
- 嵌入式/边缘场景需要轻量方案

## 内置9个Agent

translate, summarize, classify, codegen, fix, explain, sentiment, rewrite, compare

## 下一步可探索

- [ ] 添加 `ai-grep` — 自然语言搜索代码
- [ ] 添加 `ai-test` — 自动生成测试
- [ ] 支持本地模型（ollama后端）
- [ ] 添加 streaming 输出
- [ ] Shell补全脚本
