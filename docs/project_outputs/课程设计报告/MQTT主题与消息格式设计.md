# MQTT 主题与消息格式设计

## 1. 编写目的

本项目采用 MQTT 协议实现多节点环境监测数据上传。为了避免 PC 模拟节点、ESP32 硬件节点、MQTT Broker 和 Web 监控端之间出现主题命名不一致、字段含义不清、数据解析困难等问题，需要在实现具体功能之前统一 MQTT 主题结构和消息数据格式。

本文件用于规定本项目的 MQTT Topic 命名规则、节点编号规则、数据类型命名规则、JSON 消息字段和示例数据。后续软件模拟节点、硬件节点、Web 监控端和测试方案均应参考本文件。

## 2. 命名规范

本项目区分“给人看的内容”和“给程序处理的内容”：

- 文档标题、报告说明、页面展示文本可以使用中文。
- MQTT Topic、JSON 字段名、数据类型枚举值、代码变量名和配置项统一使用英文。
- 英文命名使用小写字母、数字和下划线，避免空格、中文和特殊符号。

采用英文命名的原因：

1. 降低编码兼容问题，避免不同系统、终端、抓包工具中出现中文乱码。
2. 便于 MQTTX、Wireshark、日志和命令行工具查看与过滤。
3. 便于后续使用 Python、JavaScript、C/C++ 等不同语言开发。
4. 符合常见物联网项目中 Topic 和 JSON 字段的命名习惯。

## 3. 设计原则

MQTT 主题与消息格式设计遵循以下原则：

1. 层次清晰：Topic 应能体现系统名称、节点编号和数据类型。
2. 易于订阅：监控端既能订阅全部数据，也能按节点或数据类型订阅。
3. 易于扩展：后续增加节点或数据类型时，不需要改变已有主题结构。
4. 字段统一：软件模拟节点和 ESP32 硬件节点使用相同 JSON 字段。
5. 便于测试：消息中包含时间戳和序号，方便统计延迟、到达率和重复消息。

## 4. MQTT 主题命名规则

本项目 MQTT 主题采用 3 层结构：

```text
env_monitor/{node_id}/{data_type}
```

字段含义：

| 层级 | 示例 | 含义 |
| --- | --- | --- |
| `env_monitor` | `env_monitor` | 系统标识，表示环境监测系统 |
| `{node_id}` | `node01` | 节点编号，用于区分不同采集节点 |
| `{data_type}` | `temperature` | 数据类型，用于区分温度、湿度、光照、噪声等数据 |

示例：

```text
env_monitor/node01/temperature
env_monitor/node01/humidity
env_monitor/node02/light
env_monitor/node02/noise
```

监控端可使用通配符订阅：

| 订阅主题 | 含义 |
| --- | --- |
| `env_monitor/+/+` | 订阅所有节点的所有环境数据 |
| `env_monitor/node01/+` | 订阅 `node01` 的所有环境数据 |
| `env_monitor/+/temperature` | 订阅所有节点的温度数据 |

## 5. 节点编号规则

节点编号统一使用 `node` 加两位数字：

```text
node01
node02
node03
```

规则说明：

- `node` 表示环境监测节点。
- 数字部分从 `01` 开始递增。
- 编号长度保持一致，便于排序、展示和日志分析。
- PC 模拟节点和 ESP32 硬件节点共用同一编号规则。

第一阶段建议使用：

| 节点编号 | 节点类型 | 说明 |
| --- | --- | --- |
| `node01` | PC 模拟节点 | 可模拟温度、湿度、光照、噪声等多类环境数据 |
| `node02` | PC 模拟节点 | 可模拟温度、湿度、光照、噪声等多类环境数据 |

后续接入 ESP32 时，可以继续使用 `node03`、`node04`，也可以根据实际硬件替换对应节点的实现方式，但不改变 Topic 结构。

节点编号只表示节点身份，不表示该节点固定负责某一种或某几种数据类型。实际发布哪些 `data_type` 由节点配置或传感器接入情况决定。例如 PC 模拟节点可以同时模拟四类环境数据，ESP32 硬件节点则根据实际传感器能力采集一种或多种真实数据。

## 6. 数据类型命名规则

数据类型统一使用英文小写单词：

| 数据类型 | 中文显示名称 | 单位 | 说明 |
| --- | --- | --- | --- |
| `temperature` | 温度 | `C` | 表示环境温度 |
| `humidity` | 湿度 | `%RH` | 表示空气相对湿度 |
| `light` | 光照 | `lux` | 表示环境光照强度 |
| `noise` | 噪声 | `dB` | 表示环境噪声强度 |

后续新增数据类型时，继续使用英文小写命名。例如：

| 数据类型 | 中文显示名称 | 说明 |
| --- | --- | --- |
| `pressure` | 气压 | 表示环境气压 |
| `co2` | 二氧化碳浓度 | 表示空气中二氧化碳浓度 |
| `pm25` | PM2.5 | 表示细颗粒物浓度 |

## 7. JSON 消息格式

节点发布的 MQTT 消息载荷采用 JSON 格式。基础格式如下：

```json
{
  "node_id": "node01",
  "data_type": "temperature",
  "value": 26.5,
  "unit": "C",
  "timestamp": "2026-06-08T22:30:00+08:00",
  "seq": 1
}
```

字段说明：

| 字段 | 类型 | 是否必需 | 示例 | 含义 |
| --- | --- | --- | --- | --- |
| `node_id` | string | 是 | `node01` | 发布数据的节点编号 |
| `data_type` | string | 是 | `temperature` | 数据类型，应与 Topic 最后一层一致 |
| `value` | number | 是 | `26.5` | 环境数据值 |
| `unit` | string | 是 | `C` | 数据单位 |
| `timestamp` | string | 是 | `2026-06-08T22:30:00+08:00` | 数据上传时间，使用 ISO 8601 格式 |
| `seq` | number | 是 | `1` | 消息序号，用于统计丢失、重复和乱序情况 |

字段约束：

- `node_id` 必须与 Topic 中的 `{node_id}` 保持一致。
- `data_type` 必须与 Topic 中的 `{data_type}` 保持一致。
- `value` 使用数字类型，便于监控端绘图和统计。
- `timestamp` 应包含时区信息，便于计算传输延迟。
- `seq` 在同一节点内递增，用于后续统计消息到达率和异常情况。

## 8. 中文显示映射

协议和代码中使用英文命名，页面展示和报告说明中可映射为中文。

| 英文标识 | 中文显示名称 |
| --- | --- |
| `node_id` | 节点编号 |
| `data_type` | 数据类型 |
| `value` | 数据值 |
| `unit` | 单位 |
| `timestamp` | 上传时间 |
| `seq` | 消息序号 |
| `temperature` | 温度 |
| `humidity` | 湿度 |
| `light` | 光照 |
| `noise` | 噪声 |

Web 监控端可在界面显示中文名称，但内部解析仍使用英文字段。例如收到 `data_type` 为 `temperature` 的消息时，页面显示为“温度”。

## 9. 主题与消息示例

以下示例仅用于说明不同节点、不同数据类型的 Topic 和 Payload 写法，不表示 `node01`、`node02` 固定负责某些数据类型。

### 9.1 `node01` 发布温度数据

Topic：

```text
env_monitor/node01/temperature
```

Payload：

```json
{
  "node_id": "node01",
  "data_type": "temperature",
  "value": 26.5,
  "unit": "C",
  "timestamp": "2026-06-08T22:30:00+08:00",
  "seq": 1
}
```

### 9.2 `node01` 发布湿度数据

Topic：

```text
env_monitor/node01/humidity
```

Payload：

```json
{
  "node_id": "node01",
  "data_type": "humidity",
  "value": 58.2,
  "unit": "%RH",
  "timestamp": "2026-06-08T22:30:05+08:00",
  "seq": 2
}
```

### 9.3 `node02` 发布光照数据

Topic：

```text
env_monitor/node02/light
```

Payload：

```json
{
  "node_id": "node02",
  "data_type": "light",
  "value": 420,
  "unit": "lux",
  "timestamp": "2026-06-08T22:30:10+08:00",
  "seq": 1
}
```

### 9.4 `node02` 发布噪声数据

Topic：

```text
env_monitor/node02/noise
```

Payload：

```json
{
  "node_id": "node02",
  "data_type": "noise",
  "value": 48.6,
  "unit": "dB",
  "timestamp": "2026-06-08T22:30:15+08:00",
  "seq": 2
}
```

## 10. 扩展性说明

### 10.1 增加更多节点

如果后续增加更多环境监测节点，只需要新增节点编号，不需要改变 Topic 结构。

示例：

```text
env_monitor/node03/temperature
env_monitor/node04/humidity
```

监控端订阅 `env_monitor/+/+` 时，可自动接收新增节点的数据。

### 10.2 增加更多数据类型

如果后续增加气压、PM2.5、二氧化碳浓度等数据，只需要新增 `{data_type}` 枚举值。

示例：

```text
env_monitor/node01/pressure
env_monitor/node02/pm25
```

监控端应通过数据类型映射表显示中文名称。如果遇到未配置中文名称的数据类型，可以先显示英文标识。

### 10.3 兼容软件节点和硬件节点

PC 模拟节点和 ESP32 硬件节点发布的数据使用同一 Topic 结构和 JSON 格式。监控端无需关心数据来自模拟节点还是真实硬件节点，只需要根据 `node_id` 和 `data_type` 解析消息。

### 10.4 为测试保留统计字段

`timestamp` 和 `seq` 是后续测试的重要字段：

- `timestamp` 可用于计算平均传输延迟。
- `seq` 可用于统计消息丢失、重复和乱序。

因此即使第一版监控端只展示基本数据，也应保留这两个字段。

## 11. 与后续模块的关系

本设计文档将作为后续模块的接口依据：

| 后续模块 | 与本文件的关系 |
| --- | --- |
| PC 模拟节点 | 按本文件规定的 Topic 和 JSON 格式发布模拟数据 |
| ESP32 硬件节点 | 按本文件规定的 Topic 和 JSON 格式发布真实传感器数据 |
| MQTT Broker | 转发符合本文件主题结构的消息 |
| Web 监控端 | 订阅 `env_monitor/+/+` 并解析 JSON 字段进行展示 |
| 测试方案 | 使用 `timestamp` 和 `seq` 统计延迟、到达率和异常情况 |

普通环境数据的 QoS 等级暂不在本文件中固定。后续可根据测试任务分别使用 QoS 0、QoS 1、QoS 2 对比消息传输效果。

## 12. 小结

本阶段确定了 MQTT 主题结构、节点编号规则、数据类型命名规则、JSON 消息格式和中文显示映射关系。后续 PC 模拟节点、ESP32 硬件节点和 Web 监控端应统一遵循本文件设计，从而保证不同模块之间的数据接口一致，便于后续测试、扩展和报告整理。
