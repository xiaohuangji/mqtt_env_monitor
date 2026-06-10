# PC 模拟节点运行验证

## 1. 编写目的

本文档记录 PC 模拟环境监测节点模块 `src/simulated_nodes/sim_node.py` 的运行验证过程，对应 Issue #16。验证内容包括：

1. 双节点同时持续上传多类环境数据，订阅端能否完整接收并区分各节点消息。
2. Broker 重启场景下，节点能否自动重连并继续发布数据。

本次验证只覆盖 PC 模拟节点模块本身，不实现 Web 监控端，不接入 ESP32 硬件节点，也不做正式的 QoS 对比测试。

## 2. 验证环境

| 项目 | 内容 |
| --- | --- |
| 操作系统 | Windows |
| Python | Python 3.11.7 |
| Python 依赖 | `paho-mqtt 2.1.0`、`amqtt 0.11.3` |
| Broker | `scripts/mqtt_broker.py`，监听 `127.0.0.1:1883` |
| 订阅端 | `scripts/mqtt_sub_test.py`，订阅 `env_monitor/+/+` |
| MQTT 版本 | MQTT 3.1.1 |
| 验证时间 | 2026-06-10 15:09 ~ 2026-06-10 15:11 |

## 3. 模块说明

`src/simulated_nodes/sim_node.py` 是可持续运行的模拟环境监测节点程序，按照《MQTT主题与消息格式设计》规定的 Topic 和 JSON 格式周期性发布数据。命令行参数如下：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--node-id` | `node01` | 节点编号 |
| `--types` | `temperature,humidity,light,noise` | 发布的数据类型组合，逗号分隔 |
| `--interval` | `5.0` | 上传周期，单位秒 |
| `--host` | `127.0.0.1` | Broker 地址 |
| `--port` | `1883` | Broker 端口 |
| `--qos` | `0` | MQTT QoS 等级，可选 0、1、2 |
| `--count` | `0` | 发布轮数，0 表示持续运行直到 Ctrl+C |
| `--client-id` | `sim_{node_id}` | MQTT 客户端标识 |

主要特性：

- 按 `env_monitor/{node_id}/{data_type}` 发布 JSON 消息，字段包含 `node_id`、`data_type`、`value`、`unit`、`timestamp`、`seq`。
- `seq` 在节点内连续递增，`timestamp` 使用带 `+08:00` 时区的 ISO 8601 格式。
- 模拟数据采用“基准值 + 均值回归 + 小幅随机波动”方式生成，数值平滑变化并限制在合理范围内：温度 15~35 C、湿度 20~90 %RH、光照 0~1000 lux、噪声 30~90 dB。
- 使用 `connect_async` 加后台网络线程，Broker 不可达时自动重试，Broker 重启后自动重连（重连间隔 1~5 秒）。
- 每条消息输出发送日志，结束时输出 `attempted / succeeded / queued / failed` 统计，便于与订阅端接收记录对照统计到达率。

## 4. 验证一：双节点并发上传

### 4.1 验证步骤

1. 启动本地 Broker：

   ```powershell
   python scripts\mqtt_broker.py
   ```

2. 启动订阅端：

   ```powershell
   python scripts\mqtt_sub_test.py --timeout 30
   ```

3. 同时启动两个模拟节点。`node01` 模拟全部四类数据，`node02` 只模拟温度和光照，用于验证数据类型可配置：

   ```powershell
   python src\simulated_nodes\sim_node.py --node-id node01 --interval 2 --count 8
   python src\simulated_nodes\sim_node.py --node-id node02 --types temperature,light --interval 2 --count 8
   ```

### 4.2 验证结果

节点端发送日志（节选）：

```text
[2026-06-10T15:09:45+08:00] node node01 started: types=temperature,humidity,light,noise interval=2.0s qos=0 broker=127.0.0.1:1883
[2026-06-10T15:09:45+08:00] publish ok topic=env_monitor/node01/temperature qos=0 payload={"node_id":"node01","data_type":"temperature","value":26.31,"unit":"C","timestamp":"2026-06-10T15:09:45+08:00","seq":1}
...
[2026-06-10T15:10:01+08:00] node node01 stopped: attempted=32 succeeded=32 queued=0 failed=0

[2026-06-10T15:09:45+08:00] node node02 started: types=temperature,light interval=2.0s qos=0 broker=127.0.0.1:1883
[2026-06-10T15:09:45+08:00] publish ok topic=env_monitor/node02/temperature qos=0 payload={"node_id":"node02","data_type":"temperature","value":26.96,"unit":"C","timestamp":"2026-06-10T15:09:45+08:00","seq":1}
...
[2026-06-10T15:10:01+08:00] node node02 stopped: attempted=16 succeeded=16 queued=0 failed=0
```

发送与接收统计：

| 节点 | 数据类型 | 发送消息数 | 订阅端接收数 | 到达率 |
| --- | --- | --- | --- | --- |
| `node01` | temperature、humidity、light、noise | 32（8 轮 × 4 类） | 32 | 100% |
| `node02` | temperature、light | 16（8 轮 × 2 类） | 16 | 100% |
| 合计 | - | 48 | 48 | 100% |

订阅端通过 `env_monitor/+/+` 接收到全部 48 条消息，能按 Topic 区分两个节点和不同数据类型，JSON 字段完整，`seq` 连续无缺失。验证结论：

- 两个节点可同时持续上传，互不干扰。
- 数据类型组合可按节点配置，节点编号不绑定固定数据类型，符合项目统一设计。
- 消息格式与《MQTT主题与消息格式设计》一致。

## 5. 验证二：Broker 重启断线重连

### 5.1 验证步骤

1. 启动 Broker 和订阅端（同验证一）。
2. 以 QoS 1 启动持续运行的模拟节点：

   ```powershell
   python src\simulated_nodes\sim_node.py --node-id node01 --interval 2 --qos 1
   ```

3. 节点正常发布约 8 秒后，强制结束 Broker 进程。
4. 等待约 6 秒后重新启动 Broker。
5. 观察节点日志中的断开、重连和补发情况，并核对订阅端接收的 `seq` 是否缺失。

### 5.2 验证结果

节点端关键事件日志：

```text
[2026-06-10T15:10:16+08:00] node node01 started: types=temperature,humidity,light,noise interval=2.0s qos=1 broker=127.0.0.1:1883
[2026-06-10T15:10:16+08:00] connected to 127.0.0.1:1883 as sim_node01
[2026-06-10T15:10:24+08:00] disconnected from broker (reason=Unspecified error), auto reconnect enabled
[2026-06-10T15:10:26+08:00] publish queued (offline) topic=env_monitor/node01/temperature seq=21
...
[2026-06-10T15:10:30+08:00] publish queued (offline) topic=env_monitor/node01/noise seq=32
[2026-06-10T15:10:31+08:00] connected to 127.0.0.1:1883 as sim_node01
```

时间线：

| 时间 | 事件 |
| --- | --- |
| 15:10:16 | 节点启动并连接成功，开始以 QoS 1 发布 |
| 15:10:24 | Broker 进程被强制结束，节点检测到断开并进入自动重连 |
| 15:10:26 ~ 15:10:30 | 断线期间 `seq` 21~32 共 12 条消息在客户端离线排队 |
| 15:10:30 前后 | Broker 重新启动 |
| 15:10:31 | 节点自动重连成功，距检测到断开约 7 秒 |

订阅端接收统计：共接收 60 条消息，`seq` 范围 1~60，无缺失。断线期间排队的 12 条 QoS 1 消息在重连后由客户端自动补发，订阅端全部收到。订阅端自身在 Broker 重启后也自动重连并重新订阅成功。

验证结论：

- 节点检测断开、自动重连、重连后继续发布的流程正常，本次重连耗时约 7 秒，满足《需求分析与设计指标》中断线重连恢复时间不超过 10 秒的初步指标。
- QoS 1 时，paho-mqtt 客户端会将离线期间的消息排队并在重连后补发，本次断线场景下消息到达率仍为 100%。

## 6. 发现与说明

1. QoS 1 下离线消息会被客户端排队补发；QoS 0 下离线消息将直接丢弃。节点日志将两种情况分别记录为 `publish queued (offline)` 和 `publish failed`，便于后续 QoS 0/1/2 对比测试时统计差异。
2. 节点启动时会先等待与 Broker 的首次连接建立（最多 10 秒）再开始发布，避免启动瞬间产生无效发布记录；若 Broker 不可达，节点仍会启动并在后台持续重试连接。
3. 本次验证的发送日志与订阅端接收记录均可通过 `seq` 一一对照，该方法后续可直接用于消息到达率和平均延迟的正式测试。

## 7. 小结

本次验证表明 `src/simulated_nodes/sim_node.py` 满足 Issue #16 的验收标准：节点编号、数据类型组合、上传周期、Broker 地址、端口和 QoS 均可通过命令行配置；双节点并发上传时订阅端可完整接收并区分消息；Broker 重启后节点可在 10 秒内自动重连并继续发布。该模块可作为后续 Web 监控端开发、QoS 对比测试、延迟与到达率测试的稳定数据源。
