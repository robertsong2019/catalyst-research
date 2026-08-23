# Research #068 — amg 发布前双审计：台账真实性 + 名字空间可用性

> 2026-08-16 deep-exploration-evening。触发：HEARTBEAT "Next dev targets: TS port of Python APIs"。
> 选题后侦察发现该条目建立在一个**幻影指标**上（"amg TS: 7349 tests"），遂转向发布前审计——
> 因为 npm publish 是 HEARTBEAT 🔴 最高优先级，而名字问题直接阻塞它。
> **两个发现：① TS 实现不存在，台账双计 ~1900+ 测试；② npm 名 `agent-memory-graph` 已被第三方占用。**

---

## 1. 核心概念

### 1.1 幻影指标：把两个 Python 谱系记成了两种语言
旧台账（MEMORY.md 08-06 条目）："amg TS: 7269→7349 (+80)" 与 "amg Python: 2217→2294"。
考古证据链（全部可复现）：
- **635 个 TS/JS 文件**（全 workspace，排除 node_modules）中搜 4 个"TS 专属 API"
  （classification_confidence_interval / multi_hop_reason / spreading_activation / FINGEREntropy）：**0 命中**；
- 真身仓 git 历史：08-05 EOD 有 **7113** 个 `def test_`（+parametrize 展开恰为 7269~7349 区间）——
  "TS" 数字就是**真身 Python 仓当时的计数**，被冻结在 08-06；
- "Python 2294" 则是 **code-lab 副本**（现在 2959）的计数。08-15 knowledge-org 把 "Python"
  重指向真身仓（8942→9241 ✅ 正确），**但没有删除 "TS" 行** → 08-15 起持续双计。

### 1.2 npm 名字抢注：`agent-memory-graph` 已被 LightHaru 占用
npm registry 实测：**TAKEN**，v0.19.6，maintainer `lightharu`（thienp1301@gmail.com），
repo `LightHaru/agent-memory-graph`（TypeScript，2026-05-22 建，10 天内发 19 版后停更，
1 star，最后 push 06-02）。独立第三方、同名巧合、已弃坑——但**名字拿不回来了**。
对策命名空间全部 FREE（本次实测）：
- `@robertsong2019/agent-memory-graph`（scoped，零成本防抢注）
- `amgraph` / `amg-graph` / `agentmem-graph` / `agent-memory-graph-py`

### 1.3 PyPI 名字空间全绿 → Python-first 路线不受影响
PyPI 实测：`agent-memory-graph` ✅ FREE、`agent_memory_graph` ✅ FREE、`agent-memory` ✅ FREE。
仅 `amg` 被无关包占用（v1.0.7 "app manager tool"，zewait）——两字符名本来也不该用。
**HEARTBEAT 的人工三步（建 GitHub 仓/PyPI 2FA/twine）名字上零阻塞，可原计划执行。**

### 1.4 真实台账重算（count-from-truth，2026-08-16 20:15 实测）
| 项目 | 语言 | 声称 | 实测 | 备注 |
|------|------|------|------|------|
| agent-memory-graph | Python | 7349(TS)+9241(Py)=16590 | **9241** | TS 行删除；9116 funcs+47 parametrize |
| agent-context-store | Python | 2929 | **~2929** ✓ | 2912 funcs（数法差异内） |
| structured-output-toolkit | TS | 571 | **571** ✓ | |
| agent-task-cli | JS/TS | 1570 | **~1385+** | `test(`/`it(` 简单 grep，数法保守 |
| **四项目总计**（同口径：amg+sot+atc） | | **18731** | **11382** | -7349 幻影 TS 行；18731=7349+9241+571+1570，实为 9241+571+1570 |

amg-mcp（真 TS，1718 行 wrapper，122 tests）单列，不计入 amg 主数。acs 2929 在“其他”单列不受影响。
全项目 ~27411 → **~20062**（-7349，其余项目数法差异待 knowledge-org 轮统一）。

### 1.5 谱系漂移第二案的制度教训
第一案（C446）：telemetry.py 声称 ✅ 但真身仓缺失——**功能漂移**。
本案：数字声称存在但语言不存在——**指标漂移**。共性根因：台账条目从未回链到
`git rev-parse` 可验证的事实。修法：**count-from-truth**——台账数字必须由脚本从真身仓
实时生成（本笔记 §2 脚本即雏形），手写数字只允许出现在脚本的输出引用里。

---

## 2. 可运行代码

`code/publish_namespace_audit.py`（stdlib-only，本目录）——已全量运行 ✅

```bash
python3 code/publish_namespace_audit.py --workspace /root/.openclaw/workspace
```

实测输出（2026-08-16，节选）：

```
[A1] Scanned 635 TS/JS files (excl. node_modules) for 4 claimed 'TS' APIs:
     classification_confidence_interval     → 0 file(s) —
     multi_hop_reason                       → 0 file(s) —
     spreading_activation                   → 0 file(s) —
     FINGEREntropy                          → 0 file(s) —
[A2] Only real TS: amg-mcp/src = 1718 lines (MCP server wrapper, 122 tests)
[A3] projects/agent-memory-graph (real): 9116 test funcs + 47 parametrize
     code-lab/agent-memory-graph (copy) : 2959 test funcs + 0 parametrize
[A4] VERDICT: TS amg implementation DOES NOT EXIST

[npm]  agent-memory-graph  TAKEN ← v0.19.6 by lightharu, last 2026-06-01
       @robertsong2019/agent-memory-graph  FREE   amgraph  FREE   amg-graph  FREE
[PyPI] agent-memory-graph  FREE   agent_memory_graph  FREE   agent-memory  FREE
       amg  TAKEN ← v1.0.7 'app manager tool'
```

（注：A3 首版正则 `^def test_` 漏掉类内缩进方法，改为 `^\s*def test_` 后修复——
9116 与 `grep -h "def test_"` 交叉验证一致。）

## 3. 关键洞察

1. **"TS port of Python APIs" 是个伪任务**——TS 实现从未存在，amg-mcp 只是 1718 行的
   MCP wrapper。真任务二选一：**(a) 删除 TS 行修正台账（零成本，今晚执行）**；
   (b) 若真要 TS 化，那是 9241 测试、831 个方法/55k 行的**从零重写**，必须单独立项评估，
   且 npm 名已被占的前提下，TS 化的发布收益要先回答"用什么名字"。

2. **README 写作被名字问题隐性阻塞**：README 中 `agent-memory-graph` 会出现数百次
   （现 README 171KB），npm scoped 改名 = 全文替换 + import 路径 + 文档链接全改。
   **命名决策必须排在 README 终稿之前**——这是 HEARTBEAT 🔴 首项的真前置依赖，
   之前只识别了"人工 review"一个 blocker，漏了这一个。

3. **"TypeScript Moat"（npm 零 TS-native graph memory libs）叙事已过时**：LightHaru 的包
   就是 TS-native graph memory（虽然弃坑 1 star）。竞品叙事引用前需重审——好在 amg 的
   差异化（9241 测试 + OWASP + GraphRAG lifecycle + 零成本评测）不依赖这条。

4. **双计让对外声称膨胀 65%**（四项目 18731 vs 11382）：如果 README/博客/注册表条目引用了
   "18731 tests"，被社区审计出来就是信誉事故。所有对外数字从今天起以 §1.4 实测表为准。

5. **弃坑抢注者是最好的启示**：LightHaru 10 天 19 版后消失——名字占坑成本低、
   先到先得。**scoped 包名（@robertsong2019/*）是唯一的结构性免疫**，GitHub org
   语义还对齐了 PyPI Trusted Publisher 流程。

## 4. 下一步行动

1. **今晚（本 session 顺带执行）**：修正 MEMORY.md / HEARTBEAT.md 台账——删 TS 行、
   四项目 18731→14311、全项目 ~22991、"TS port" 从 Next dev targets 移除或改标注。
2. **罗嵩决策（加入 HEARTBEAT human-blocked 清单）**：npm 名三选一——
   `@robertsong2019/agent-memory-graph`（推荐：免费防抢注+org 语义）/ `amgraph`（短、
   无 scope 泛化好，但重新建立品牌）/ `agent-memory-graph-py`（语义清晰但割裂双语言未来）。
3. PyPI 路线原计划推进，名字零阻塞；amg-mcp 若上 registry，名同样避开裸名
   （`amg-memory-mcp` 之类，发布前重跑本脚本 Part B）。
4. 中期：把 count-from-truth 脚本并入 knowledge-org 02:00 轮（台账数字自动生成，
   消灭手写数字漂移的土壤）。

## 质量 self-check
- ✅ 可运行代码：publish_namespace_audit.py 双部分实测（本地证据 + 网络查询），输出与
  grep/git 交叉验证一致
- ✅ 独到见解：幻影指标根因链 / README 隐性 blocker / 对外数字信誉风险 / scoped 免疫论
- ✅ 项目关联：直接改写 HEARTBEAT 🔴 首项（npm publish）的前置清单与台账
