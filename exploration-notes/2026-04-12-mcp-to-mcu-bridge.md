# MCP-to-MCU Bridge: AI Agent × Embedded Systems

**日期:** 2026-04-12
**方向:** AI Agent 编程 + AI 嵌入式 + 快速原型

## 灵感来源

1. **IoT-SkillsBench** (Duke University, arxiv 2603.19583) — 为嵌入式 IoT 开发设计 Skilled AI Agents，支持 ESP32-S3、nRF52840、ATmega2560
2. **fastmcp** (GitHub 24k+ stars) — 快速构建 MCP 服务器的 Python 框架
3. **PocketFlow** — 100 行极简 LLM 框架，构建 agent workflow

## 核心创意: MCP-MCU Bridge

一个 MCP 服务器，让 AI Agent 能通过自然语言控制微控制器：

```
AI Agent → MCP Protocol → MCP-MCU Server → Serial/UART → MCU (ESP32/RPi Pico)
```

### 架构设计

```
┌─────────────┐     MCP      ┌──────────────┐    UART/Serial    ┌─────────┐
│  AI Agent   │ ◄──────────► │  MCP-MCU     │ ◄──────────────►  │  ESP32  │
│ (Claude/GPT)│   tools/call │  Server      │   JSON protocol   │  Pico   │
└─────────────┘              │  (Python)    │                    │  etc.   │
                             └──────────────┘                    └─────────┘
```

### MCP Tools 设计

```python
# MCP Server 暴露的工具
tools = {
    "mcu_pin_mode": "设置引脚模式 (input/output/pwm)",
    "mcu_digital_write": "数字写入 HIGH/LOW",
    "mcu_digital_read": "数字读取",
    "mcu_analog_read": "模拟读取 (ADC)",
    "mcu_pwm_write": "PWM 输出",
    "mcu_i2c_scan": "扫描 I2C 设备",
    "mcu_i2c_read": "读取 I2C 设备数据",
    "mcu_spi_transfer": "SPI 数据传输",
    "mcu_sensor_read": "读取传感器 (DHT22/BME280/MPU6050)",
    "mcu_display": "在 OLED/LCD 显示文字/图形",
    "mcu_deploy": "部署 MicroPython/CircuitPython 脚本",
}
```

### MCU 端固件 (最小协议)

```json
// 串口 JSON 协议 — 极简设计
// Request:  {"c":"dw","p":2,"v":1}  → digitalWrite(2, HIGH)
// Response: {"ok":true}
// Request:  {"c":"ar","p":36}       → analogRead(36)
// Response: {"ok":true,"v":2048}
```

### 用例示例

**"让 LED 呼吸" → Agent 自动生成:**
```python
# Agent 通过 MCP 调用
for i in range(256):
    mcu_pwm_write(pin=2, duty=i)
    time.sleep(0.01)
for i in range(255, -1, -1):
    mcu_pwm_write(pin=2, duty=i)
    time.sleep(0.01)
```

**"读取温湿度" → Agent 自动调用:**
```python
data = mcu_sensor_read(sensor="DHT22", pin=4)
# → {"temperature": 23.5, "humidity": 65.2}
```

## 技术栈

| 组件 | 选择 | 原因 |
|------|------|------|
| MCP Server | fastmcp (Python) | 生态成熟，24k+ stars |
| MCU 固件 | MicroPython | 易部署，JSON 原生支持 |
| 通信 | UART/Serial | 简单可靠 |
| 协议 | JSON over Serial | 可读、可调试 |
| 目标硬件 | ESP32-S3 / RPi Pico W | WiFi + BLE，社区活跃 |

## 与现有项目的关系

- **IoT-SkillsBench**: 学术框架，评估 Agent 在嵌入式任务上的表现
- **MCP-MCU Bridge**: 实用工具，让任何 AI Agent 能直接控制硬件
- **差异**: IoT-SkillsBench 是 benchmark，我们是 bridge/SDK

## 扩展方向

1. **WebSerial 支持** — 浏览器直接连接 MCU，无需本地 Python
2. **OTA 部署** — Agent 通过 WiFi 远程更新 MCU 脚本
3. **可视化 Dashboard** — 实时显示引脚状态、传感器数据
4. **多 MCU 管理** — 一个 MCP Server 控制多个 MCU
5. **安全沙箱** — 限制 Agent 可执行的操作，防止硬件损坏

## 实现优先级

Phase 1 (MVP):
- [ ] ESP32 MicroPython 固件 (JSON serial protocol)
- [ ] fastmcp server (基础 pin control)
- [ ] 串口通信层

Phase 2:
- [ ] 传感器抽象层 (DHT22, BME280, MPU6050)
- [ ] I2C/SPI 支持
- [ ] OLED 显示支持

Phase 3:
- [ ] WebSerial bridge
- [ ] OTA 部署
- [ ] 多设备管理

## 反思

这个项目的核心价值在于**降低 AI 控制硬件的门槛**。传统嵌入式开发需要:
- 看数据手册
- 写 C/C++ 代码
- 烧录调试

而通过 MCP Bridge:
- 用自然语言描述需求
- Agent 自动生成硬件操作序列
- 实时反馈，快速迭代

这正是 AI + Embedded + Rapid Prototyping 的交叉点。

---
*Generated during creative evening session - 2026-04-12*
