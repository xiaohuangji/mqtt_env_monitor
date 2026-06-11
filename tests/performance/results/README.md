# 性能实验结果目录说明

本目录存放 2026-06-11 性能实验的**原始数据**。如果你只想看结论，请按这个顺序读：

1. **汇总分析**：`docs/project_outputs/测试证据/性能实验数据表.md`（全部实验的表格化结果与结论）
2. **图表**：`docs/project_outputs/测试证据/实验图_*.png`（见下表）
3. 需要溯源某个数字时，再回到本目录查原始 CSV / 日志

## 图表索引（均在 docs/project_outputs/测试证据/）

| 图 | 内容 | 来源数据 |
| --- | --- | --- |
| 实验图_连接容量对比.png | EMQX vs amqtt 内存/CPU 随连接数（1k→50k） | ramp_emqx.csv、ramp_amqtt_v4.csv |
| 实验图_吞吐对比.png | 两 Broker CPU 随消息速率，amqtt 5000 条/秒单核饱和 | throughput_emqx.csv、throughput_amqtt_v4.csv |
| 实验图_协议开销对比.png | 7 种协议组合的单条消息字节（抓包矩阵） | captures/wireshark/*.pcap 解析 |
| 实验图_公网延迟分布.png | 120 条消息端到端延迟直方图 | latency_wan.csv |
| 场景6实景压测30分钟曲线.png | 2 万连接 30 分钟：连接/速率/CPU/内存四联图 | soak_samples.csv、soak_sub.log |

## 顶层文件说明

| 文件 | 实验 | 说明 |
| --- | --- | --- |
| `ramp_emqx.csv` | EMQX 连接数爬坡 | 每行一个梯度（1k/5k/10k/20k/50k）：达成连接数、内存均值/峰值、CPU 均值/峰值、状态 |
| `ramp_amqtt_v4.csv` | amqtt 连接数爬坡（对照组，MQTT 3.1.1 客户端） | 列同上 |
| `throughput_emqx.csv` | EMQX 消息吞吐 | 每行一个速率档（1k→50k 条/秒）：发布连接数、QoS、CPU 占用 |
| `throughput_amqtt_v4.csv` | amqtt 消息吞吐（对照组） | 200→5000 条/秒，5000 处单核饱和 |
| `soak_samples.csv` | 场景⑥实景压测 30 分钟 | 每 5 秒一行：连接数、EMQX 内存、CPU |
| `soak_pub.log` / `soak_sub.log` | 同上 | emqtt_bench 逐秒发布/接收速率（sub 端总接收 24,613,940 条） |
| `latency_wan.csv` | 跨公网延迟 | 每条消息一行：接收时间、主题、seq、延迟 ms |
| `reconnect_node.log` | 断线重连复测 | 节点日志：21:13:17.599 断开 → 21:13:22.835 恢复（5.2 s），6 条排队 0 丢失 |

## 子目录

- `logs/`：emqtt_bench 的逐步原始输出（`ramp_*.bench_N.log` 为各梯度建连日志，`throughput_*.pub/sub_N.log` 为各速率档的逐秒速率行）以及编排日志。
- `invalid_v5_attempt/`：**无效数据，仅作过程留痕**。首轮 amqtt 对照实验中 emqtt_bench 默认以 MQTT 5.0 连接 amqtt（仅支持 3.1.1），amqtt 不拒绝也不应答 CONNACK，连接在 TCP 层静默挂起——当时 `ss` 统计的"连接数"是 TCP 层假象，吞吐为零。该现象本身作为工程发现记录在《性能实验数据表》§4.1；有效数据见 `*_v4.csv`。

## 复现方法

测试脚本与使用说明见上级目录 `tests/performance/README.md`；抓包步骤见 `docs/project_outputs/测试证据/抓包实验操作手册.md`。
