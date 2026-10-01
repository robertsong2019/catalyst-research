# 具身智能的 VLA 模型：机器人正在重演 LLM 的全部剧本

**日期：** 2026-10-01（晚间深研）
**主题：** Vision-Language-Action (VLA) 机器人基础模型 —— 架构收敛、数据墙、评测危机与记忆转向
**触发：** 博客 399 篇未覆盖具身智能/VLA；与已有 agent 记忆系列形成强对照

---

## 一、为什么现在看 VLA

- 2026-05：Figure 03 + Helix 02 完成 >17 小时全自动仓库班次，分拣 >22,000 个包裹，24h 直播记录 >30,000 件，零遥操作。
- 2026-04：Physical Intelligence 发布 π0.7——steerable 基础模型，涌现跨本体叠衣、组合泛化能力。
- 2026-07-30：Google DeepMind 发布 Gemini Robotics 2 / ER 2（whole-body intelligence + 多机器人协作）。
- Moravec 悖论正在被反向攻破：LLM 先解决了"说话"，现在整个行业在用 LLM 的方法论攻"动手"。

## 二、系统与论文清单（15+）

### 2.1 Physical Intelligence π 家族（闭源但论文开放）
| 版本 | 时间 | 核心贡献 |
|---|---|---|
| π0 | 2024-10 | flow-matching action expert，openpi 开源 |
| π0.5 | 2025-04 | 3.3B（SigLIP 400M + Gemma 2.6B + 动作专家 300M），开放世界泛化：未见过家庭的厨房整理/洗衣，400+ 小时移动操作数据 + 异构共训 |
| Knowledge Insulation | NeurIPS 2025 | 快速训练不破坏 VLM 知识：动作专家隔离，"Train Fast, Run Fast, Generalize Better" |
| π0.6 + RECAP | 2025-11 | **从自身经验学习**：on-robot RL 吃部署数据，难任务失败率减半，浓缩咖啡/洗衣/装箱 >90% |
| MEM | 2026-03 | Multi-Scale Embodied Memory：长短时记忆支撑 >10 分钟任务 |
| RL Token | 2026-03 | 从 VLA 中抽出 RL token，数小时数据做快速在线 RL，吞吐 2x |
| π0.7 | 2026-04 | ~5B（4B Gemma3 VLM + MEM 式视频历史编码器 + 860M flow-matching 专家）；**多模态上下文条件化**（子任务语言/子目标图像/episode 元数据/控制模式）；把 specialist 性能蒸馏回单一 generalist；涌现：复杂指令跟随、跨本体叠衣、教新家电、组合泛化 |

关键结构性事实：**openpi 已落后闭源 4 代**——模拟基准上几乎看不出差距，零样本开放世界差距巨大。

### 2.2 NVIDIA 全栈（全部 Apache 2.0）
- GR00T N1（2025-03）：双系统——System 2 = VLM（Eagle + SmolLM 1.7B，10Hz），System 1 = Diffusion Transformer flow-matching（实时）。合成数据（Omniverse）叠加真机数据 **+40%**。Newton 物理引擎（与 DeepMind/Disney 合作，MuJoCo-Warp 提速 70x）。
- GR00T N1.5（2025-05）：数据与后训练升级。
- Cosmos Predict 2.5：14B 视频基座，200M 视频片段。
- DreamDojo（2026-02，GEAR）：**44,711 小时**第一人称人类视频预训练世界模型（迄今最大），连续 latent actions 作代理动作标签（VAE 从相邻帧提取），分块注入防动作泄漏；蒸馏后 10 FPS 实时交互 >1 分钟；**世界模型当裁判：策略评估与真实结果相关 r=0.995**。
- DreamZero（2026-02）：视频+动作联合预测，零样本策略。
- EgoScale：人类视频小时数与机器人性能 **R²=0.9983** 的 scaling law。
- GR00T N2：2026 年底，产品化"机器人脑"。

### 2.3 Google DeepMind Gemini Robotics
- 1.5（2025-09）：双模型协作——ER 1.5（thinking VLM：推理/规划/调 Google Search/多步计划，15 个学术基准 SOTA 超 GPT-5）+ Robotics 1.5（VLA 执行，think-before-act 透明推理）。跨本体技能迁移。ASIMOV 安全基准 SOTA：语义安全思考 + 板载低层碰撞避免子系统。
- ER 1.6：真实任务增强推理。
- 2 / ER 2（2026-07-30）：全身智能、视频理解、任务编排、多机器人协作（Duo & Apollo）。

### 2.4 Figure Helix（自研，弃用 OpenAI 合作后）
- Helix 01（2025-02）：首个全上半身人形 VLA，35 DoF；S1（ visuomotor，~200Hz，嵌入式低功耗 GPU）+ S2（VLM，慢速）；<500 小时遥操作数据；hindsight 指令自动标注（"什么指令会导致视频里的动作？"）；单模型控两台机器人协作。
- Helix 02（2026-01）：**System 0/1/2 三层**——S0 = 10M 参数神经先验，1kHz，1000+ 小时人体动捕重定向，管平衡与接触，**替代 109,504 行手写 C++**；S1 连接全部传感器（头部相机+掌心相机+3g 触觉指尖）到全部执行器 200Hz；S2 语义排序。4 分钟连续洗碗机任务 61 个时序动作零干预。
- 工厂 BotQ 年产能 12,000 台；家庭目标 $600/月租赁。
- ⚠️ 安全阴影：前产品安全负责人 2025-11 起诉——因提出"机器人力量足以碎人颅骨"的担忧被解雇。

### 2.5 开源生态
- OpenVLA（Stanford+TRI）：7B（Llama2 + DINOv2/SigLIP），970K OXE 轨迹，LIBERO 超 RT-2-X 且参数少 7x；MIT 许可；LoRA r=32 单卡 H100 4-6 GPU 小时微调。
- Octo：27M/93M 扩散策略，RTX 4090 上 20-30Hz，消费级显卡路线。
- SmolVLA（HF LeRobot）：450M（SmolVLM-2 + flow-matching），**异步推理解耦动作预测与执行，任务完成时间 -30%**；真实世界 ~78%；SO-100/101 机械臂全流程，Jetson Orin NX（$499）可跑；50 条 demo + 单 A100 4 小时微调。
- EO-1（上海 AI Lab + AgiBot，2025-08）：3B 统一 decoder-only，离散自回归 + 连续 flow-matching 混合解码，交错视觉-文本-动作预训练，EO-Data 1.5M；权重+训练代码+数据全开源——目前最有希望缩小开源/闭源差距。
- Being-H0.5（2026-01）：人手作为通用 embodiment（UniHand-2.0：35K 小时、30 本体），Mixture-of-Flow，LIBERO 98.9%。

### 2.6 数据基础设施
- Open X-Embodiment：22 本体、21 机构、>240 万轨迹、1.2TB；但质量/视角/本体差异大。
- Bridge V2：60K WidowX 轨迹；DROID：76K Franka demo（多视角）。
- AgiBot World Colosseo：大规模真机遥操作平台（数百台机器人并行采集），开源数据+工具链+模型。
- 遥操作经济学：leader-follower（ALOHA/GELLO）$5K-20K/站、20-40 demo/h；VR $500-2K；外骨骼 $50K-200K。**百万 demo 级瓶颈已从数据质量转为数据物流**。

### 2.7 评测危机（与 agent 评测作弊同构！）
- LIBERO 四套件接近饱和：>95% 是 Spatial/Goal/Object 的"应该"，Long/90 需 90-95%。**调好的 Diffusion Policy 不用任何 VLM 也能达到**——"你不需要互联网级预训练来解决这些"。
- Moritz Reuss（ICLR 2026 综述博客）：开源 VLA 在 LIBERO/CALVIN 上"超越"π0.5，但零样本开放世界与 Gemini/π0.5 差距显著；他自己的 FLOWER 是 CALVIN SOTA，"却远达不到 CoRL 现场 Gemini demo 的零样本鲁棒性"。**模拟基准系统性隐藏这一 delta**。
- LIBERO-Plus（CVPR 2026）：7 类扰动、21 子维度、10,030 任务实例——近饱和模型在光照/视角/纹理扰动下显著崩塌。
- 评测瓶颈综述（2026-06）：指标一维（只报成功率），效率/安全/轨迹一致性少报；真实世界评测碎片化、每任务试次少；**模拟分与真机性能弱相关（除非针对目标物理装置校准）**。
- VLA-REPLICA：低成本可复现真机评测的尝试。
- 2026 侧写：甚至出现"GPT-6 Astra 在 StationeryBench 上打赢 SOTA VLA"式结果——通用 VLM 直接输出动作码的路线开始搅局。

### 2.8 世界模型与经验学习
- LAPA（ICLR 2025）：VQ-VAE 从视频帧差学离散 latent actions，无真值动作标签预训练 VLA，预训练效率比 OpenVLA 路线高 ~30-40x。
- LAWM / CLAP / AdaWorld / DexWM：latent action 世界模型家族。
- DreamGen（NVIDIA）：用世界模型"想象"合成机器人轨迹。
- RL-100（2025）：真机 RL 达 8 任务 1000 episode 全过、单任务 250 连胜；**榨汁机器人在商场服务 7 小时零失败**——但天花板：均 per-task。
- Z-1（2026）：GRPO 系统后训练 flow-based VLA，无额外私域 demo 超 SOTA。

## 三、核心概念（5 个）

1. **VLA（视觉-语言-动作模型）**：端到端网络，输入相机图像+本体感觉+自然语言，输出连续动作序列。传统感知-规划-控制流水线被单一模型替换。"下一个 token 是扭矩"。
2. **双系统/三系统架构**：System 2 VLM 大脑（Hz 级语义推理）→ System 1 动作专家（200Hz flow-matching/diffusion 连续控制）→ System 0 身体先验（1kHz 平衡/接触，神经"小脑"）。频率分层即架构分层。
3. **Latent Actions（隐动作）**：从无标注视频的帧对中自监督提取的动作表示——人类视频没有机器人动作标签，就先学一个"隐藏动作标签"，再当动作条件用。绕开数据墙的关键技术。
4. **世界模型当评测器/训练场**：学 s_{t+1}~p(·|s_t,a_t) 的视频模型，既能在里面"做梦"造数据（DreamGen），又能当裁判给策略打分（DreamDojo r=0.995 与真实结果相关）。
5. **多模态上下文条件化**：π0.7 的核心招——同一权重靠上下文（子任务、子目标图、元数据、控制模式）切换"档位"，specialist 能力蒸馏回 generalist，推理期语言可转向。

## 四、关键洞察（5 条）

1. **VLA 在以约 5 倍速重演 LLM 剧本，且每一幕都似曾相识**：预训练数据墙→合成数据（Omniverse=机器人版 GPT 合成语料）→后训练 RL（RECAP/RL-100=机器人版 RLHF 之后的 verifiable RL）→记忆与可控性（MEM/π0.7=agent 记忆系统的物理版）。给 LLM 工程师的机会：你们已经看过这部剧的下一集。
2. **"数据墙"的解法不是更多遥操作，而是把人类视频变成免费燃料**：EgoScale 给出 R²=0.9983 的人类视频-机器人性能 scaling law，LAPA 预训练省 30-40x 算力，手是通用 embodiment。互联网没有"动作的维基百科"，但 YouTube 是"展示动作的维基百科"。
3. **评测危机与 agent 领域的 reward hacking / 基准饱和是同一种病**：LIBERO 95%+ 的榜单名次在零样本开放世界几乎无信息量（Diffusion Policy 无 VLM 也能刷到）；开源模型"赢"闭源 4 代前的权重、却输掉全部真实差距。任何领域：**当基准被饱和，榜单就停止测量它声称测量的东西**。
4. **频率分层正在产生"System 0"——一个没有认知的脊柱层**：Figure 用 10M 参数 + 1kHz 替代 10.9 万行 C++，说明具身栈的底座不是更大的 VLM，而是把"反射"从软件工程迁移到学习。类比生物：脊髓反射不需要大脑参与。
5. **机器人在补 LLM 已交过学费的课：记忆与整理**：MEM 让任务从 2 分钟到 10+ 分钟；π0.7 用元数据区分 demo/失败/次优 rollout 统一吸收（=记忆领域"不物理删除、给后悔药"的镜像）；RL-100 证明部署经验是最后 10% 可靠性的来源。**"Agent 失眠症"的机器人版已经开演。**

## 五、可落地 Next Actions

1. **本周就能摸到**：HuggingFace LeRobot + SO-101（~$100 级机械臂）+ SmolVLA 450M：采 50 条 demo、单卡 4 小时微调、$499 Jetson Orin NX 部署——个人体验 VLA 全闭环的最低成本路径。
2. **给 agent 工程师的接口思维**：把 VLA 当 agent 的"手"——ER 1.5 式分层（大脑调工具、动作专家执行）与 agent 的 tool-call 循环同构；关注 Gemini Robotics API 化的接口形态。
3. **跟进开源追赶闭源的窗口**：EO-1（全开源：权重+代码+数据）与 openpi 的差距是 4 代；用 LIBERO-Plus（而非 LIBERO 原版）做选型评测，扰动鲁棒性才是真信号。
4. **世界模型当评测器的思路迁移**：DreamDojo r=0.995 的做法——"在梦里模拟评测代替昂贵真机实验"——可平移到 agent 领域：用世界模型/环境模型预筛 agent 策略，省真机/线上流量。
5. **写作闭环**：本笔记转化为博文《机器人开始长记性了：VLA 正在重演 LLM 的剧本》发布至博客。

## 六、引用来源（主要）

- pi.website（π 家族论文与博客：π0.5/0.6/0.7、MEM、RL Token、Robot Olympics）
- arxiv 2503.14734（GR00T N1）、arxiv 2602.06949（DreamDojo）、arxiv 2508.21112（EO-1）、arxiv 2503.06669（AgiBot World）
- deepmind.google（Gemini Robotics 1.5 / 2 博客）、figure.ai（Helix 01/02）
- mbreuss.github.io（State of VLA Research at ICLR 2026）、CVPR 2026 LIBERO-Plus、Evaluation Bottleneck Survey（preprints 202606.0425）
- developer.nvidia.com（World-Action Models 博客）、dreamdojo-world.github.io、openelab.io / huggingface.co（SmolVLA 实操）、claru.ai（遥操作经济学）
