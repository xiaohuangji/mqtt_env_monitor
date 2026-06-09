# MQTT 发布订阅验证

## 1. 编写目的

本文档记录本地 MQTT Broker 搭建、MQTTX 发布订阅验证和 Python 最小发布订阅脚本验证过程，用于确认项目已设计的 MQTT Topic 和 JSON 消息格式可以在实际 MQTT 通信中正常传输。

本次验证只覆盖 MQTT 通信链路的最小闭环，不实现完整 PC 模拟节点、Web 监控端或 ESP32 硬件节点。

## 2. 验证环境

| 项目 | 内容 |
| --- | --- |
| 操作系统 | Windows |
| Python | Python 3.11.7 |
| Python 依赖 | `paho-mqtt 2.1.0`、`amqtt 0.11.3` |
| MQTTX CLI | `mqttx-cli 1.12.1` |
| Broker 地址 | `127.0.0.1` |
| Broker 端口 | `1883` |
| MQTT 版本 | MQTT 3.1.1 |
| 验证时间 | 2026-06-09 23:18 ~ 2026-06-09 23:23 |

## 3. 新增脚本说明

| 脚本 | 作用 |
| --- | --- |
| `scripts/mqtt_broker.py` | 启动一个本地轻量 MQTT Broker，默认监听 `127.0.0.1:1883` |
| `scripts/mqtt_pub_test.py` | 发布符合项目 Topic 和 JSON 格式的测试消息 |
| `scripts/mqtt_sub_test.py` | 订阅 `env_monitor/+/+` 并打印收到的 Topic 与 JSON 内容 |

依赖记录在根目录 `requirements.txt` 中。

## 4. Topic 与 JSON 格式

本次验证使用项目已确定的 Topic 结构：

```text
env_monitor/{node_id}/{data_type}
```

订阅端使用通配 Topic：

```text
env_monitor/+/+
```

测试消息 JSON 基础字段包括：

```text
node_id, data_type, value, unit, timestamp, seq
```

示例消息：

```json
{
  "node_id": "node01",
  "data_type": "temperature",
  "value": 26.5,
  "unit": "C",
  "timestamp": "2026-06-09T23:23:00+08:00",
  "seq": 1
}
```

## 5. Python 脚本验证步骤

### 5.1 安装依赖

```powershell
pip install -r requirements.txt
```

### 5.2 启动本地 Broker

```powershell
python scripts\mqtt_broker.py
```

默认启动后监听：

```text
127.0.0.1:1883
```

### 5.3 启动订阅脚本

在另一个终端运行：

```powershell
python scripts\mqtt_sub_test.py --count 8 --timeout 15
```

其中：

- `--count 8` 表示收到 8 条消息后自动退出。
- `--timeout 15` 表示最多等待 15 秒。

### 5.4 启动发布脚本

在第三个终端运行：

```powershell
python scripts\mqtt_pub_test.py --interval 0.05
```

默认发布 `node01`、`node02` 两个节点的四类环境数据，共 8 条消息。

## 6. Python 脚本验证结果

发布脚本成功发布 8 条消息：

| 节点 | 数据类型 | Topic |
| --- | --- | --- |
| `node01` | `temperature` | `env_monitor/node01/temperature` |
| `node01` | `humidity` | `env_monitor/node01/humidity` |
| `node01` | `light` | `env_monitor/node01/light` |
| `node01` | `noise` | `env_monitor/node01/noise` |
| `node02` | `temperature` | `env_monitor/node02/temperature` |
| `node02` | `humidity` | `env_monitor/node02/humidity` |
| `node02` | `light` | `env_monitor/node02/light` |
| `node02` | `noise` | `env_monitor/node02/noise` |

订阅脚本成功订阅 `env_monitor/+/+`，并接收到全部 8 条消息。接收结果中包含 Topic、QoS 和 JSON Payload，说明：

- Broker 可以正常启动并接收客户端连接。
- 发布端可以按项目规定 Topic 发布消息。
- 订阅端可以通过 `env_monitor/+/+` 接收两个节点、多种数据类型的消息。
- Payload 包含 `node_id`、`data_type`、`value`、`unit`、`timestamp`、`seq` 字段。

## 7. MQTTX CLI 验证步骤

本次使用 MQTTX CLI 进行命令行验证。首先确认版本：

```powershell
npx -y mqttx-cli --version
```

输出版本：

```text
1.12.1
```

启动本地 Broker 后，使用 MQTTX CLI 订阅：

```powershell
npx -y mqttx-cli sub -h 127.0.0.1 -p 1883 -t env_monitor/+/+ -V 3.1.1 --output-mode clean
```

使用 MQTTX CLI 发布：

```powershell
npx -y mqttx-cli pub -h 127.0.0.1 -p 1883 -t env_monitor/node01/temperature --file-read payload.json -V 3.1.1
```

注意：在 PowerShell 中直接把 JSON 写到 `-m` 参数中时，双引号容易被命令行处理掉；使用 `--file-read` 从 JSON 文件读取 Payload 更稳定。JSON 文件建议使用 UTF-8 无 BOM 编码，避免 Payload 前出现 BOM 字符。

## 8. MQTTX CLI 验证结果

MQTTX CLI 发布端显示：

```text
Read file successfully
Connected
Message published
```

MQTTX CLI 订阅端收到消息：

```json
{
  "topic": "env_monitor/node01/temperature",
  "payload": "{\"node_id\":\"node01\",\"data_type\":\"temperature\",\"value\":26.5,\"unit\":\"C\",\"timestamp\":\"2026-06-09T23:23:00+08:00\",\"seq\":1}"
}
```

该结果说明 MQTTX CLI 可以连接本地 Broker，并完成发布订阅验证。

## 9. 小结

本次验证完成了本地 MQTT Broker、MQTTX CLI 和 Python 最小发布订阅脚本的基础测试。测试结果表明，项目当前设计的 Topic：

```text
env_monitor/{node_id}/{data_type}
```

以及 JSON 基础字段：

```text
node_id, data_type, value, unit, timestamp, seq
```

能够在实际 MQTT 发布订阅过程中正常传输。该验证结果可作为后续 PC 模拟节点、Web 监控端和 ESP32 节点接入的基础。
