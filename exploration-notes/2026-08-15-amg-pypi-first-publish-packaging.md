# Research #066: amg PyPI 首发打包 — 从过期 June 尝试到可一键发布的现代配置

> Date: 2026-08-15 (Sat) 20:30 · Catalyst deep-exploration-evening
> 主题来源: HEARTBEAT.md 中优先级 "amg PyPI publish (Python-first strategy)" — 发布关键路径上唯一没做过前置研究的项
> 前序: #065（GraphRAG-Bench 首跑）· #063（分发渠道）· #061（MCP server）
> 状态: **pyproject 现代化 + 真实构建 + twine check + 新 venv 安装冒烟全绿，已 commit** ✅
> 成功标准达成: 可运行代码 = 已在本机验证的构建+冒烟脚本（下文 §2）

---

## 0. TL;DR

amg Python 的 PyPI 首发今晚已完成全部技术前置：**`agent-memory-graph` 包名在 PyPI 真实可用（HTTP 404 = 未被占用）**，54,293 行 stdlib-only 巨型模块打包后 wheel 仅 564KB，新 venv 安装后 GraphRAG 全家族 API 实测存活。仓库里躺着的 June 打包尝试（1.0.0 / 70KB wheel）已过期两个半月——已用 PEP 639 SPDX license + `[mcp]` extra 现代化并重新构建。**距真实发布只剩 3 个人工动作：建 GitHub 独立仓库（可选）、PyPI 账号 2FA + Trusted Publisher 登记、`twine upload`（或推 tag 触发 CI）。** 竞争窗口：TencentDB-Agent-Memory 在 GitHub 21.5k★ 但**不在 PyPI**——Python 生态的 `pip install agent-memory-graph` 入口目前是真空。

## 1. 核心概念 (5)

### 1.1 Trusted Publishing = 无 token 发布（2026 标准姿势）
PyPI 官方原生支持 OIDC 短期凭证：在 pypi.org 后台登记仓库 `owner/repo` + workflow 文件名 + environment，GitHub Actions 里用 `pypa/gh-action-pypi-publish@release/v1` 即可上传，**全程无长期 API token**（token 泄漏面归零，PyPI help 页已把 Trusted Publishers 列为推荐通道）。对 amg 意味着：发布凭证永不进 workspace，罗嵩只需在 GitHub 网页点一次 publish workflow。

### 1.2 PEP 639 SPDX license 表达式（setuptools≥77 新规范）
旧写法 `license = {text = "MIT"}` + `License :: OSI Approved` classifier 已废弃；新写法 `license = "MIT"` + `license-files = ["LICENSE"]`，构建时进 METADATA 2.4。June 版 pyproject 用的正是旧写法——今晚已修。twine 6.2 对两种都 PASS，但旧格式在 setuptools 80+ 会告警，首发就用新规范。

### 1.3 巨型单文件模块的打包哲学：`py-modules` 平铺 > 仓促重组
54k 行单文件 `memory_graph.py` 打包不需要包目录改造——`[tool.setuptools] py-modules = [...]` 平铺安装，用户 `from memory_graph import MemoryGraph` 零迁移成本。**教训**：README 里 "940+ APIs" 的分发形态（单文件平铺）本身就是差异化卖点（sqlite3 单依赖、无 namespace 污染），等 v1.0 前再评估是否重组包目录。

### 1.4 `[mcp]` optional extra：MCP server 的正确打包位
`mcp_server.py` 依赖外部 `mcp` 包，不能进 core（会破坏零依赖卖点）。解法：模块进 wheel + 依赖进 extra——`pip install agent-memory-graph[mcp]` 才拉 `mcp>=1.0`，核心安装仍是 0 依赖解析。16 个 MCP tools 分发面与 library 面解耦，同一个 wheel 服务两类用户。

### 1.5 版本语义决策：0.9.0 vs 1.0.0（发布前最后一问）
June 尝试写的 1.0.0 从未发布，版本号免费重选。**论点**：292 天零回滚 + 8942 tests 撑得起 1.0.0；但 940+ API 面仍在日更（TS port 落后、Python 是 API 源头），semver 的 1.0.0 承诺 = 后续每次破坏性改动都要 major bump。**今晚选择 0.9.0**（pre-1.0 诚实信号），改回 1.0.0 只是一行——这是罗嵩发布前的最终决策点，非技术问题。

## 2. 可运行代码 ✅（今晚全部实际执行通过）

### 2.1 构建三连（已在 projects/agent-memory-graph 执行）

```bash
cd projects/agent-memory-graph
python3 -m build --sdist --wheel .   # → agent_memory_graph-0.9.0-py3-none-any.whl (564KB) + sdist (687KB)
twine check dist/*                    # → PASSED / PASSED
```

产物事实：wheel 仅含 `memory_graph.py` + `mcp_server.py` + dist-info/LICENSE；970KB 的 test_memory_graph.py、200+ 测试文件、node_modules、experiments.tsv **全部自动排除**（py-modules 显式列举的天然效果）。

### 2.2 新 venv 安装冒烟（验证的不是构建而是"用户拿到手能用"）

```python
# 在全新 venv 中: pip install dist/agent_memory_graph-0.9.0-py3-none-any.whl
from memory_graph import MemoryGraph   # 零依赖解析，无任何警告

g = MemoryGraph(':memory:')
g.link(g.add('ReLU', tags=['activation']).id, g.add('GELU').id, 'smooth-variant-of')
g.recall('ReLU', limit=3)              # → 1 hit ✅
g.search_bm25('activation', limit=3)   # → 2 hits ✅ (FTS5)

g2 = MemoryGraph(':memory:')
g2.extract_from_text('Karpathy created autoresearch. Karpathy wrote Software 2.0.',
                     kind='entity', tags=['test'])
# → {'nodes_created':…, 'edges_created':…, 'entities':…, 'relations':…, 'sentences':…} ✅
ctx = g2.graphrag_query('What did Karpathy create?', max_hops=2, top_k=5)  # ctx 901 chars ✅
g2.graphrag_explain('What did Karpathy create?')    # 2080 chars ✅
g2.graphrag_coverage_report()                        # 915 chars ✅
g2.graph_entropy()                                   # ✅
```

### 2.3 发布日脚本（Trusted Publishing 版，存档备用）

```yaml
# .github/workflows/publish.yml（放进将来的 agent-memory-graph 独立仓库）
name: Publish
on:
  release: {types: [published]}          # 或 tag push
jobs:
  pypi:
    runs-on: ubuntu-latest
    environment: pypi                    # PyPI Trusted Publisher 登记时填同名 environment
    permissions: {id-token: write}       # OIDC
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pipx run build && pipx run twine check dist/*
      - uses: pypa/gh-action-pypi-publish@release/v1   # 无 token，OIDC 直传
```

## 3. 关键洞察 (4)

### 3.1 ⚠️ workspace 存在 amg Python 三副本漂移——差点打包了过期代码
`code-lab/agent-memory-graph`（22.5k 行，停在 08-10/C424）、`code-lab/projects/agent-memory-graph`（只有 README）、`projects/agent-memory-graph`（54k 行，08-15/C440 活跃真身）。**我第一轮构建打的是 C424 过期副本**——冒烟时 `extract_from_text(mode=...)` 签名对不上才暴露。教训已入 error-patterns：对多副本项目，动手前先 `find -name memory_graph.py -printf "%T@ %p"` 按 mtime 认主。HEARTBEAT 的 "experiments.tsv 结构性缺口" 条目其实早已暗示（C410+ 记在项目仓内）。

### 3.2 PyPI 名称真空 = 竞争对手的分发盲区
`agent-memory-graph`（主选）、`agent-memory-graph-py`、`amg-memory-graph` 全部 HTTP 404 可注册；对手 `tencentdb-agent-memory` 等也全 404——**TencentDB-Agent-Memory 的 21.5k★ 完全没有转化成 Python 生态入口**。`memory-graph` 已被占（200）需避开。GitHub 星数与 pip install 可达性是两条战线，Python-first 策略恰好卡位后者。

### 3.3 API 签名的文档-代码漂移：HEARTBEAT 记忆 ≠ 源码事实
HEARTBEAT 写 "extract_from_text + graphrag_query"，源码真名确实是这俩，但参数是 `kind=`（不是我以为的 `mode=`），`chunk_text` 其实在 `run_amg.py`（不在 memory_graph.py），`spreading_activation`/`MultiAgentMemoryGraph` 在 54k 行版本里不是顶层导出。**冒烟必须用 `inspect.signature`/`dir()` 现场发现，不能凭记忆写 demo**——这对未来 README/TUTORIAL 的示例代码正确性同样适用。

### 3.4 零依赖是发布叙事的核心资产，不是巧合
两代源码（22.5k 与 54k 行版本）imports 完全一致：collections/dataclasses/datetime/json/math/re/sqlite3/time/typing/uuid——**纯 stdlib**。`pip install agent-memory-graph` 的依赖解析成本为零，离线可装，供应链攻击面为零（无传递依赖可投毒）。这在 OWASP 安全叙事之上又添一层：README 发布时应在第一屏明示 "zero dependencies, stdlib only"。

## 4. 下一步行动

1. **（本周，人工）发布三步**：① 建独立 GitHub 仓库 `robertsong2019/agent-memory-graph`（当前在 openclaw-workspace monorepo 内，PyPI Homepage 指向的地址还不存在）；② pypi.org 注册 + 2FA + Trusted Publisher 登记；③ 决定 0.9.0/1.0.0 后 `twine upload dist/*`（或先传 TestPyPI 演练一遍）
2. **（下次 dev cycle）副本收敛**：确认 `code-lab/agent-memory-graph` 是否可归档（它有 projects/ 缺的 telemetry.py 独立模块 + amg_bench.py——先 diff 决定合并方向再删）
3. **（发布前）README 首屏补三件事**：pip install 一行示例 / "zero dependencies" 徽章 / `pip install agent-memory-graph[mcp]` 的 extra 说明（167KB README 已有 API 文档，缺安装叙事）

## 5. 质量自评

| 标准 | 状态 |
|---|---|
| 可运行代码 | ✅ §2.1-2.2 全部今晚实际执行通过（build/twine/venv 冒烟），非伪代码 |
| 独到见解 | ✅ 三副本漂移警示、PyPI 名称真空竞争分析、零依赖=供应链叙事、签名漂移教训 |
| 与现有项目关联 | ✅ 直接推进 amg PyPI publish 待办；产出已 commit 进活跃仓库 |
| autoresearch 积累性 | ✅ 在 #063（分发渠道）与 #065（GraphRAG 首跑）之间补上"安装入口"一环 |

---
*实验记录: 已按规范 commit（keep）。下一循环候选: TestPyPI 演练 workflow 或副本收敛 diff。*
