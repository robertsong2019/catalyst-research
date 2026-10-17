# Computer-Use Agents：当 AI 拿起鼠标，两年从笑话到超越人类

**日期：** 2026-10-17（晚）
**主题：** GUI Agents / Computer-Using Agents (CUA) —— 截图感知、像素操作、基准竞速与安全代价
**触发背景：** 晚间深度研究 cron。近期博客已覆盖记忆系统/上下文工程/协议栈，本次转向「操作层」——agent 如何像人一样使用电脑。

## 一、调研范围（20+ 论文/系统）

### 基准线
1. **OSWorld** (2024, Xie et al., 原始 arXiv 2404.07972) — 首个真实 OS 沙箱基准：369 个任务，Ubuntu/Windows/macOS 真实运行 Chrome/LibreOffice/VS Code/Thunderbird，执行式判分。人类基线 **72.36%**。
2. **OSWorld-Verified** (2025-07) — 修复 300+ 任务定义与判分漏洞，评估收紧（历史分数普遍下修）。
3. **OSWorld-Human** (arXiv 2506.16042, WukLab, ICML 2025 CUA Workshop) — 效率基准：不只问"能不能完成"，还问步数/耗时。WES+（步数加权效率分）：UI-TARS-1.5 原始 42.5 → 单动作 WES+ 23.7 → 分组动作 14.3；WES-（相对人类的速度）全员为负（-0.16 ~ -0.42）——**所有 agent 都比人慢**。
4. **Mind2Web** (2023) / **WebArena** (2023) / **AndroidWorld** (2024) / **ScreenSpot**（grounding）— 前置基准族。

### 模型/系统
5. **CogAgent** (2023-12, arXiv 2312.08914, 智谱) — 18B VLM，18K 高分辨率输入，仅截图打败吃 HTML 的 LLM 方法（Mind2Web/AITW）。视觉路线第一个强证据。
6. **Set-of-Mark (SoM)** (Yang et al. 2023) — 在截图上叠加编号标签，把视觉 grounding 转成"选编号"。
7. **SeeAct** (Zheng et al. 2024) — 两阶段框架：规划 + grounding，候选来自过滤 HTML 或 SoM 标注。
8. **SeeClick** (2024) — GUI 专用 grounding 小模型（Qwen-VL 底座）。
9. **UGround** (arXiv 2410.05243, "Navigating the Digital World as Humans Do") — 通用 grounding 模型；SeeAct-V（纯视觉）超过所有依赖 HTML/a11y 树的基线；跨平台泛化（未训练桌面 UI 仍强）。**关键错误分析：规划错误占主导，grounding 错误已很小**。
10. **UI-TARS** (ByteDance, arXiv 2501.12326, 2025-01) — 原生端到端 GUI agent：仅以截图为输入，统一跨平台动作空间，System-1/2 双模式推理（可先生成 thought 再出动作），迭代自举训练（自动收集+过滤反思式在线轨迹）。OSWorld 24.6（50 步）超当时 Claude 22.0；AndroidWorld 46.6 vs GPT-4o 34.5。**核心论点：端到端模型打败"GPT-4o + 专家精心包装的工作流"**。
11. **UI-TARS-2** (2025-09) — 多轮 RL、MoE 骨干，Stage-4 路线图指向终身适应/自主提任务。
12. **OpenAI Operator / CUA** (2025-01) — 发布时 OSWorld 38.1%，自称 SOTA（距人类基线 34 分）。
13. **Claude Computer Use** (Anthropic, 2024-10 首发 API) → Sonnet 4.5 61.4% (2025-09) → Opus 4.6 72.7% / Sonnet 4.6 72.5% (OSWorld-Verified, 2026-02)。两年内从 ~38% 到 72.5%，近翻倍。
14. **Agent S → S2 → S3** (Simular; S2 COLM 2025) — S2 关键设计：**规划与 grounding 分离**（OSWorldACI 桥接层，pyautogui 执行）；S2 (2025-12) 72.6%，**首个技术上越过人类基线**（+0.24 分）；S3 (2025-10) 69.9%（含 Behavior Best-of-N），架构反而更简单——简化趋势。
15. **CoACT-1** (2025-08) — GUI+代码混合路线，60.76%。
16. **GTA1** (Salesforce, 2025-07) — Verified 时代首个 #1（45.2%）。
17. **Coasty** (2026) — 商业系统 82%，超人类基线近 10 分。

### 安全线
18. **Indirect Prompt Injection 实战化** — Google Security Blog + Forcepoint (2026-04)：每月 20-30 亿爬取页面中，恶意 IPI 页面占比 2025-11→2026-02 相对增长 **32%**；载体偏好静态站/博客/论坛/评论区；模板化工具库而非命名 APT。Unit 42 (2026-03)：12 起实测 IPI 案例，含首个绕过 AI 广告审核的真实 payload（2025-12，CSS 隐藏注入）。
19. **EchoLeak** (CVE-2025-32711, CVSS 9.3) — M365 Copilot 零点击数据外泄。
20. **CaMeL** (Google DeepMind 2025-03) — 双 LLM + 能力（capability）追踪，AgentDojo 上可证明安全。
21. **FIDES** (Microsoft 2025-05) — 信息流标签 + 确定性策略执行。
22. **Aria-UI** (ACL 2025 Findings) — grounding 侧数据：GPT-4o+SoM vs +A11y tree vs 纯视觉的 OSWorld 子任务对比，a11y 树在 OS 类应用上信息量优势明显。

## 二、核心概念（5 个）

1. **感知通道之争（Pixels vs. Structure）**：HTML/a11y 树是廉价的结构化 API，但覆盖率残缺（canvas/游戏/旧桌面应用无树）、脆弱（改版即坏）；截图通用但贵且 grounding 难。CogAgent/UGround/UI-TARS 三连击证明纯视觉可用且泛化更强；成熟系统实际是混合体——有树吃树，没树吃像素。
2. **原生 Agent（Native Agent）vs. Wrapper 工作流**：UI-TARS 的中心论点——把感知/推理/grounding/记忆塞进一个端到端训练的 VLM，胜过"商业大模型 + 专家 prompt + 手工流程"。与 ACE 上下文工程的结论同构：**workflow 是未成熟模型的脚手架，成熟模型会把它吃掉**。
3. **Planning/Grounding 分解**：grounding（把意图翻译成精确像素坐标）在 UGround/SeeClick 一代后接近"解决"；错误分析显示瓶颈已转移到 planning（下一步做什么）。Agent S2 的规划-执行分离、UI-TARS 的 System-2 推理，都是对"瓶颈在规划"的回应。
4. **基准经济学**：OSWorld 分数 2025-01（38.1）→ 2025-09（61.4）→ 2025-12（72.6 平人类）→ 2026（82），两年走完 RPA 十年没走完的路。但 OSWorld-Human 揭示另一面：步数膨胀（100 步）、WES- 全负（人人比人类慢）、Verified 修一次分全体下修——**成功率饱和后，效率与鲁棒性成为新战场**。
5. **屏幕即攻击面（Screen as Injection Surface）**：CUA 把"非受控内容"的定义从"用户输入"扩大到"整块屏幕"。任何网页文字、图片 OCR、评论区都是指令通道。IPI 已实战化（+32%/3 个月）；防御最高杠杆是权限分离与信息流控制（CaMeL/FIDES），而非 sanitization。

## 三、关键洞察（5 条）

1. **交互层的 API 化在倒退，而且是有意的**：我们花了二十年把 GUI 底下的协议挖出来变成 API，现在 agent 又把 GUI 当 API 用。这不是退步——GUI 是人类为人类维护的最通用、最向后兼容的接口，比任何 API 文档都诚实（所见即所点）。UI 即 API 的代价是 10-100 倍 token 成本和注入风险，收益是零集成成本。
2. **"能做"与"划算"隔着数量级**：82% 的 SOTA 成功率听起来超过人类，但 OSWorld-Human 显示同样的系统在效率加权下掉到 1/2~1/3，WES- 全负。比喻：一个每件事都能办成但要跑 100 趟银行的实习生。基准分数是入场券，单位任务成本才是采购依据。
3. **失败率是复利计算的**：72% 单任务成功率在 50 步业务流程里 = 0.72^50 ≈ 全灭。工程含义：CUA 的第一落点必须是"失败可重试、可回滚"的短任务，而不是长流水线；或者用 Behavior Best-of-N（Agent S3）这类多候选采样换可靠性。
4. **瓶颈迁移决定投资方向**：grounding 接近解决 → 该投资的是规划（任务分解、里程碑识别、反思）、记忆（跨会话 UI 经验）和速度（并行采样/步数压缩），而不是继续卷"点得更准"。UI-TARS 的 Stage-4 路线图（终身适应、自主提任务）印证了这一点。
5. **安全是 CUA 的乘法门，不是加分项**：一个带着你登录态读屏的 agent，离被一条隐藏评论劫持只差一次 OCR。IPI 增长 32%/3 个月说明攻击方已经工业化。结构级防御（权限最小化、不可逆动作人审、出口管控、CaMeL 式信息流）必须在架构期植入——事后补丁在 prompt 层面已被证明无效。

## 四、可落地 Next Actions

1. **跑一次真实成本实验**：用 Claude Computer Use API 或 browser-use（开源）执行 3 个真实任务，记录步数、耗时、token 成本、失败重试次数，自己算一遍 WES——体感"划算不划算"。
2. **给 agent 加操作审计层**：每步保存（截图 + 动作 + 模型 thought）三元组。这是安全兜底与事后归因的最低配置，成本可忽略。
3. **内部工具优先 API/MCP 化，GUI 作 fallback**：API 调用天然防注入（结构隔离），GUI 操作留给没有 API 的长尾场景，并对后者叠加人审。
4. **选型看 OSWorld-Verified 榜而非宣传页**，同时盯 OSWorld-Human 类效率指标；对 70%+ 分数的系统，问的第一个问题应是"每任务多少钱、多少步"。
5. **原型验证注入防御**：给自己的 CUA demo 植入一条隐藏指令（白帽自测），验证权限分离/出口管控是否真的兜得住，再谈部署。

## 五、与既有研究的连线

- 与 2026-10-16 ACE（上下文工程）：同构结论——端到端原生训练吞噬 wrapper 工作流。
- 与 2026-10-15 图记忆：CUA 的跨会话经验沉淀（UI-TARS Stage-4 终身适应）正是记忆系统的下一个主战场。
- 与 2026-10-13 协议栈：A2A/MCP 是 agent 间"白盒"协议，CUA 是 agent-应用间"黑盒"协议——一明一暗两条腿。

## 引用清单

OSWorld (2404.07972) · OSWorld-Verified · OSWorld-Human (2506.16042) · UI-TARS (2501.12326) · UI-TARS-2 · CogAgent (2312.08914) · UGround (2410.05243) · SeeClick · SoM · SeeAct · Mind2Web · Agent S2 (COLM 2025) · Agent S3 · CoACT-1 · GTA1 · Aria-UI (ACL 2025) · Unit 42 IPI report (2026-03) · Google/Forcepoint IPI telemetry (2026-04) · EchoLeak CVE-2025-32711 · CaMeL (DeepMind) · FIDES (MSR)
