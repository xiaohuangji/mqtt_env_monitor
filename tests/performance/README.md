# 性能实验脚本

为《网络负载与成本建模》提供待校准系数的实测值。关联 Issue：性能实验（抓包 + 压测）。

## 脚本一览

| 脚本 | 跑在哪 | 作用 | 产出系数 |
| --- | --- | --- | --- |
| `bench_ramp.py` | 服务器 | emqtt_bench 连接数爬坡，psutil 采样 Broker 内存/CPU，`ss` 统计真实连接数 | m_conn（每连接内存）、m_base、amqtt 失效点 |
| `bench_throughput.py` | 服务器 | 固定速率消息吞吐（pub/sub），采样 CPU | k_core（每核每秒消息数） |
| `latency_probe.py` | 本地 | 订阅并对照 payload 发送时间戳与接收时间（同机时钟），统计延迟分位数/到达率/重复/乱序 | 延迟与到达率实测 |
| `run_server_suite.sh` | 服务器 | 按序执行三组服务器侧实验 | 一键复现 |

## Day 2 服务器侧执行步骤

```bash
# 1. 上传脚本（本地执行，IP 以当日为准）
scp -r tests scripts root@<server-ip>:~/mqtt_env_monitor/

# 2. 服务器上执行
ssh root@<server-ip>
systemctl start emqx
cd ~/mqtt_env_monitor/tests/performance
bash run_server_suite.sh        # 约 25~35 分钟

# 3. 取回结果（本地执行）
scp -r root@<server-ip>:~/mqtt_env_monitor/tests/performance/results ./tests/performance/
```

## 本地侧实验

- 抓包矩阵：见 `docs/project_outputs/测试证据/抓包实验操作手册.md`。
- 跨公网延迟（节点与探针同机，时钟一致）：

```bash
# 终端 1：探针
D:\anaconda\python.exe tests\performance\latency_probe.py --broker-host <server-ip> --duration 120 --output captures\latency_wan.csv
# 终端 2：节点（指向云端 EMQX）
D:\anaconda\python.exe src\simulated_nodes\sim_node.py --host <server-ip> --node-id node01 --interval 2 --count 30 --qos 1
```

## 注意事项

- 容量爬坡走服务器 loopback，公网带宽不会污染数据；跨公网只做小规模延迟实验。
- amqtt 对照组用 `scripts/mqtt_broker.py --max-connections 200000` 起在 1884 端口，让它败在性能而不是配置上限。
- 采样的是 Broker 进程树（EMQX 找 `beam.smp`，amqtt 找 `mqtt_broker`），压测工具自身的资源不计入。
