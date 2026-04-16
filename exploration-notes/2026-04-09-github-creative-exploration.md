# GitHub 创意项目探索笔记
## 日期：2026-04-09

## 一、探索发现

### 1. AI Agent 编程趋势

**热门项目：**
- `caramaschiHG/awesome-ai-agents-2026` - 258 stars，340+资源，20个类别
  - 包含编码Agent、多智能体编排、浏览器/桌面Agent
  - 覆盖协议标准、可观测性、评估工具

**核心方向：**
- 编码Agent（Claude Code, Cursor Codex, OpenCode）
- 多智能体协调（Work Crew, Supervisor, Pipeline, Council模式）
- 轻量级/极简Agent框架
- Agent模板和快速构建工具

### 2. AI 嵌入式与边缘计算

**硬件创新：**
- Nordic Semiconductor: 专用NPU用于语音识别，速度快10倍，能耗降低10倍
- Texas Instruments: TinyEngine NPU集成到整个MCU产品线
- FPGA优化AI: 使用MXINT8和4-bit格式，甚至三元和二进制格式

**技术挑战：**
- 高效推理（批处理、内存管理、GPU饱和、分片）
- 本地LLM部署（精度vs带宽权衡）
- 低延迟、低功耗需求

**应用场景：**
- 工业预测性维护（MAX78000 AI微控制器）
- 边缘AI平台（Qualcomm IQ9 + NVIDIA技术）
- 实时故障诊断

### 3. AI 快速原型开发工具

**主流工具：**
- Claude Code: 推理能力强，适合复杂任务
- Cursor: 工作流优化，多模型编排
- GitHub Copilot: IDE集成，代码补全
- GPT-5.3 Codex: 重构能力出色

**新兴模式：**
- CLI工具与Agent集成（Valyu CLI, Agentmail CLI）
- 低代码Agent构建器
- Prompt-to-App平台

## 二、创意方向选择

### 选定方向：**边缘AI Agent微框架**

**理由：**
1. AI Agent发展迅速，但主要在云端
2. 嵌入式AI硬件能力提升（NPU、专用加速器）
3. 边缘计算趋势：隐私保护、低延迟、离线能力
4. 缺少轻量级Agent框架

**核心概念：**
设计一个超轻量级的AI Agent框架，专为资源受限的嵌入式设备设计（如ESP32、RPi Pico、STM32），支持：
- 基础Agent通信（MCP协议子集）
- 本地模型推理（量化模型）
- 云端协同（必要时调用大模型）
- 传感器融合和决策
- 极低内存占用（<512KB）

**技术栈：**
- C/C++（嵌入式友好）
- MicroPython/JavaScript（可选高级接口）
- TFLite Micro或ONNX Runtime
- 串口/网络通信层

## 三、计划实现的功能模块

### MVP（最小可行产品）
1. Agent核心调度器
2. 工具调用机制（简化版）
3. 本地内存管理（环形缓冲区）
4. 基础通信协议（JSON over Serial）

### V2 功能
1. 量化模型推理接口
2. 云端协同模式（WiFi/蜂窝）
3. 传感器数据预处理管道
4. OTA更新支持

## 四、参考资源

**开源项目：**
- CLI-Anything: Making ALL Software Agent-Native
- TensorFlow Lite Micro
- MicroPython for embedded AI

**学习资料：**
- Stanford CS336 (Lecture 5-11): LLM Inference
- FPGA Conference 2026: Embedded AI talks
- Embedded World 2026 field reports

## 五、下一步行动

1. 创建实验性仓库：`edge-agent-micro`
2. 实现核心调度器原型
3. 测试在ESP32上的性能
4. 编写文档和示例

---

**备注：** 这是一个探索性项目，重点在于验证边缘Agent的可行性和发现技术挑战。
