# Karpathy Wiki Method

> 不要把 LLM 当搜索引擎，让它像程序员一样持续维护 Markdown 知识库

## 核心思路

LLM 不是每次从原始文档检索，而是**持续增量式构建和维护一个 Wiki**。知识编译一次，持续保持最新。

### 三层架构
1. **Raw Sources** — 原始资料，不可变，LLM 只读
2. **The Wiki** — LLM 生成的结构化 Markdown 知识库
3. **The Schema** — 规则文件（CLAUDE.md / AGENTS.md / SCHEMA.md），定义组织方式

### 三个核心操作
- **Ingest** — 录入新资料，提取关键信息，更新 Wiki 和所有关联页面
- **Query** — 对 Wiki 提问，好的回答回存（知识复利）
- **Lint** — 定期体检，找矛盾、过时信息、孤儿页面

### 关键洞察
- 人类放弃 Wiki 的原因：维护负担增长比价值快
- LLM 不会厌倦，可以一次改 15 个文件，维护成本趋近零
- 中等规模（100来源、几百页面）靠索引文件就够，不需要向量数据库
- 与 1945 年 Vannevar Bush 的 Memex 构想一脉相承

### 类比
- Obsidian = IDE，LLM = 程序员，Wiki = 代码库
- "编译缓存"：源码编译一次，后续直接用二进制

## 关联
- [[rag-vs-wiki]] — 与传统 RAG 的对比
- [[llm-cache-strategy]] — 两级缓存的检索策略
- [[knowledge-vs-memory]] — 知识库 vs 记忆

## 来源
- Karpathy Gist: gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- 与罗嵩的讨论 (2026-04-07)

---
_最后更新：2026-04-07_
