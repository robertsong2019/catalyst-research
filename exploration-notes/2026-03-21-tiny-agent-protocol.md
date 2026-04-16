# Tiny Agent Protocol (TAP) - Creative Exploration

**探索时间:** 2026年3月21日 19:00 - 21:00  
**探索方向:** AI Agent + Embedded Systems - 轻量级代理协议  
**探索者:** 🤖

---

## 一、创意起源

### 1.1 问题空间

当前 AI Agent 框架的问题：
- **重量级** - OpenClaw, LangChain, CrewAI 都需要完整运行时
- **资源密集** - 动辄数 GB 内存，持续网络连接
- **不适合边缘** - 无法在 IoT 设备、微控制器上运行

### 1.2 灵感来源

- **MQTT** - 轻量级消息协议，专为受限环境设计
- **CoAP** - 受限应用协议，用于物联网
- **ESP-NOW** - 乐鑫的低功耗无线协议
- **LoRa** - 长距离低功耗通信

### 1.3 核心创意

**Tiny Agent Protocol (TAP)** - 为边缘设备设计的极简代理协议：

```
┌─────────────────────────────────────────────┐
│           Cloud Orchestrator                │
│         (OpenClaw / Full Agent)             │
└────────────┬────────────────────────────────┘
             │ TAP Protocol
             │ (JSON-RPC-like over MQTT/CoAP)
     ┌───────┴───────┐
     │               │
┌────▼────┐     ┌────▼────┐
│ESP32    │     │RPi Pico │
│TAP Agent│     │TAP Agent│
│< 100KB  │     │< 100KB  │
└─────────┘     └─────────┘
```

---

## 二、协议设计

### 2.1 设计原则

1. **Minimal Footprint** - 核心协议 < 10KB 代码
2. **Stateless by Default** - 无需持久化状态
3. **Pub/Sub Native** - 基于 MQTT/CoAP 模式
4. **Graceful Degradation** - 网络中断时降级运行
5. **Battery Aware** - 低功耗设计

### 2.2 核心原语

```typescript
// TAP Message Format (最小化)
interface TAPMessage {
  v: 1;              // 协议版本
  id: string;        // 消息 ID (8 chars)
  t: number;         // 时间戳 (Unix ms)
  a: TAPAction;      // 动作类型
  p?: any;           // 负载 (可选)
}

type TAPAction = 
  | 'ping'     // 心跳
  | 'sense'    // 感知环境
  | 'act'      // 执行动作
  | 'query'    // 查询状态
  | 'emit'     // 发送事件
  | 'sleep'    // 进入休眠
;
```

### 2.3 能力声明

```typescript
// 设备能力声明 (启动时发送)
interface TAPCapability {
  agent: string;           // 代理 ID
  sensors: string[];       // 可用传感器
  actuators: string[];     // 可用执行器
  memory: number;          // 可用内存 (KB)
  battery?: number;        // 电池电量 (%)
  interval: number;        // 心跳间隔 (秒)
}
```

### 2.4 消息流示例

```
Device                          Orchestrator
  │                                  │
  │ ──── TAP_CAP (capabilities) ────>│
  │                                  │
  │ <─── TAP_OK (acknowledge) ───────│
  │                                  │
  │ ──── TAP_SENSE (temp: 25C) ─────>│
  │                                  │
  │ <─── TAP_ACT (led: on) ─────────│
  │                                  │
  │ ──── TAP_EMIT (action_done) ────>│
  │                                  │
```

---

## 三、参考实现设计

### 3.1 架构

```
tap/
├── spec/                    # 协议规范
│   ├── TAP-SPEC.md         # 完整规范文档
│   └── TAP-EXAMPLES.md     # 示例消息
│
├── core/                    # 核心库 (语言无关)
│   ├── tap-schema.json     # JSON Schema 验证
│   └── tap-test-vectors/   # 测试向量
│
├── sdk-c/                   # C SDK (ESP32/RPi Pico)
│   ├── include/tap.h       # 公共 API
│   ├── src/tap.c           # 核心实现
│   └── examples/           # 示例代码
│
├── sdk-js/                  # JavaScript SDK (Node.js)
│   ├── src/
│   │   ├── client.ts       # TAP 客户端
│   │   ├── orchestrator.ts # 编排器
│   │   └── transport.ts    # 传输层 (MQTT)
│   └── test/
│
└── orchestrator/            # 云端编排器
    ├── src/
    │   ├── registry.ts     # 设备注册
    │   ├── scheduler.ts    # 任务调度
    │   └── bridge.ts       # OpenClaw 桥接
    └── adapters/
        ├── mqtt.ts         # MQTT 适配器
        └── coap.ts         # CoAP 适配器
```

### 3.2 C SDK API (嵌入式)

```c
// 超简 API - 仅 5 个函数
typedef struct {
  const char* agent_id;
  const char** sensors;
  int sensor_count;
  const char** actuators;
  int actuator_count;
} TAPConfig;

// 初始化 TAP 客户端
int tap_init(const TAPConfig* config);

// 发送感知数据
int tap_sense(const char* sensor, const char* value);

// 接收动作指令 (非阻塞)
int tap_poll_action(char* action, size_t len);

// 发送事件
int tap_emit(const char* event_type, const char* data);

// 清理
void tap_cleanup(void);
```

### 3.3 JavaScript SDK API (云端)

```typescript
// TAP Orchestrator (云端)
class TAPOrchestrator {
  // 注册设备
  register(capability: TAPCapability): Promise<void>;
  
  // 发送指令到设备
  act(agentId: string, action: string, params?: any): Promise<void>;
  
  // 订阅设备事件
  on(event: 'sense' | 'emit', handler: (msg: TAPMessage) => void): void;
  
  // 查询设备状态
  query(agentId: string): Promise<DeviceState>;
}

// TAP Client (边缘设备 - Node.js)
class TAPClient {
  constructor(config: TAPConfig, transport: Transport);
  
  // 发送感知数据
  async sense(sensor: string, value: any): Promise<void>;
  
  // 监听动作指令
  onAction(handler: (action: string, params: any) => Promise<void>): void;
  
  // 发送事件
  async emit(event: string, data?: any): Promise<void>;
}
```

---

## 四、创新点

### 4.1 渐进式智能

```
Level 0: Pure Reflex (无条件反射)
  - 温度 > 30C → 开风扇
  - 无云端连接，本地决策

Level 1: Cloud-Assisted (云端辅助)
  - 感知数据 → 云端分析 → 接收指令
  - 需要 TAP 协议通信

Level 2: Predictive (预测性)
  - 云端学习模式 → 下发预测模型
  - 设备本地预测执行

Level 3: Collaborative (协作性)
  - 多设备通过云端协调
  - 形成 swarm intelligence
```

### 4.2 电量感知调度

```typescript
interface PowerProfile {
  level: 'critical' | 'low' | 'normal' | 'high';
  interval: number;  // 心跳间隔 (秒)
  features: string[]; // 启用的功能
}

// 根据电量自动调整行为
const PROFILES: Record<string, PowerProfile> = {
  critical: { level: 'critical', interval: 3600, features: ['ping'] },
  low:      { level: 'low',      interval: 600,  features: ['ping', 'sense'] },
  normal:   { level: 'normal',   interval: 60,   features: ['ping', 'sense', 'act'] },
  high:     { level: 'high',     interval: 30,   features: ['ping', 'sense', 'act', 'emit'] }
};
```

### 4.3 离线降级

```typescript
// 当网络中断时的降级行为
const FALLBACK_RULES = {
  'temperature': {
    condition: (v) => v > 30,
    action: 'fan_on',
    priority: 'high'
  },
  'humidity': {
    condition: (v) => v > 80,
    action: 'alert',
    priority: 'medium'
  },
  'motion': {
    condition: (v) => v === true,
    action: 'light_on',
    priority: 'low'
  }
};
```

---

## 五、与 OpenClaw 集成

### 5.1 TAP Bridge Skill

```markdown
# TAP Bridge Skill

## Description
Connect OpenClaw to TAP-enabled edge devices.

## Tools
- `tap_list_devices` - 列出所有已注册设备
- `tap_sense` - 从设备读取传感器数据
- `tap_act` - 向设备发送动作指令
- `tap_query` - 查询设备状态

## Usage
"Check temperature sensor in living room and turn on fan if > 25C"
```

### 5.2 工作流示例

```yaml
# OpenClaw TAP Workflow
name: Smart Home Climate Control
trigger: cron(*/5 * * * *)  # 每 5 分钟

steps:
  - tap_list_devices:
      filter: { sensors: [temperature] }
      save: temp_sensors
      
  - for_each: $temp_sensors
    do:
      - tap_sense:
          device: ${item.id}
          sensor: temperature
          save: current_temp
          
      - condition: ${current_temp > 25}
        then:
          - tap_act:
              device: ${item.id}
              action: fan_on
              
      - condition: ${current_temp < 20}
        then:
          - tap_act:
              device: ${item.id}
              action: heater_on
```

---

## 六、实现计划

### Phase 1: 规范与测试 (今晚)
- [x] 协议规范文档
- [ ] JSON Schema 验证
- [ ] 测试向量
- [ ] 示例消息

### Phase 2: SDK 实现 (后续)
- [ ] JavaScript SDK (Node.js)
- [ ] C SDK (ESP32)
- [ ] Python SDK (测试用)

### Phase 3: 编排器 (后续)
- [ ] MQTT 传输层
- [ ] 设备注册表
- [ ] OpenClaw 桥接

### Phase 4: 硬件验证 (后续)
- [ ] ESP32 示例项目
- [ ] RPi Pico 示例项目
- [ ] 真实硬件测试

---

## 七、潜在应用

### 7.1 智能家居
- 温度/湿度传感器
- 灯光控制
- 安防监控
- 能源管理

### 7.2 农业物联网
- 土壤湿度监测
- 自动灌溉
- 温室控制
- 作物健康分析

### 7.3 工业监控
- 设备状态监测
- 预测性维护
- 环境监控
- 安全警报

### 7.4 环境监测
- 空气质量
- 水质监测
- 噪音水平
- 辐射检测

---

## 八、与现有方案对比

| 特性 | TAP | MQTT | CoAP | HTTP |
|------|-----|------|------|------|
| Agent 语义 | ✅ | ❌ | ❌ | ❌ |
| 最小内存 | <10KB | ~50KB | ~30KB | ~100KB |
| 离线降级 | ✅ | ❌ | ❌ | ❌ |
| 电量感知 | ✅ | ❌ | ❌ | ❌ |
| 云编排 | ✅ | ❌ | ❌ | ❌ |

---

## 九、总结

### 9.1 核心价值

**TAP 协议填补了一个空白**：
- 比 MQTT 更智能 (Agent 语义)
- 比 HTTP 更轻量 (嵌入式友好)
- 比自定义协议更标准 (规范 + 多语言 SDK)

### 9.2 创新性

1. **Agent-Native** - 专为 AI Agent 设计，而非通用消息
2. **Edge-First** - 从嵌入式视角出发，而非云端优先
3. **Graceful Degradation** - 网络中断时仍能工作
4. **Battery-Aware** - 自动调整行为以省电

### 9.3 下一步

1. 完成规范文档
2. 实现 JavaScript SDK 原型
3. 创建模拟设备测试
4. 编写 OpenClaw 集成 Skill
5. 硬件验证 (如果有 ESP32)

---

**探索状态:** 🚧 In Progress  
**下一步:** 创建 GitHub 仓库，实现规范和 SDK 原型

_让 AI Agent 运行在每一个微控制器上 🤖🔌_
