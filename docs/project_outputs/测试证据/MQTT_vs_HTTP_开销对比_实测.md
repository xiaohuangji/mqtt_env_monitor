# MQTT 与 HTTP 上传开销对比实测

> 实验脚本：`scripts/compare_mqtt_http.py`　｜　样本数 N = 200 / 格式

## 方法

同一条环境监测数据，分别用 **MQTT**（QoS 1 `PUBLISH` + `PUBACK`，原始套接字逐字节计）与 **HTTP**（`POST` 请求 + `200` 响应，请求头对齐 python-requests、服务端为合规最小响应）发送，统计单次上传的**应用层字节**（发送 + 接收）。应用层协议字节数与对端在本地或公网无关，故本地即可精确、可复现地测量协议开销。

## 结果（应用层字节，含报文头）

| payload 格式 | payload (B) | MQTT 单次 (B) | HTTP 单次 (B) | MQTT 节省 | 协议头开销 MQTT / HTTP |
| --- | --- | --- | --- | --- | --- |
| json | 122 | 163 | 463 | 65 % | ≈ 40 / 340 B |
| json-min | 65 | 105 | 405 | 74 % | ≈ 40 / 340 B |
| msgpack | 49 | 89 | 392 | 77 % | ≈ 40 / 340 B |

- 协议头开销几乎恒定：**MQTT 每条约 40 B，HTTP 每条约 340 B（约 8 倍）**。
- payload 越小、上传越频繁，HTTP 的固定大头占比越高，MQTT 越省。
- 一次性建链：MQTT `CONNECT`+`CONNACK` 约 28 B（长连接复用，仅 1 次）；HTTP 不保持长连接时每次还需 TCP 三次握手。
- 延迟不在此对比（本地环回不具参考意义）；MQTT 跨公网延迟另见《公网延迟实测》（平均 44.7 ms）。

## 复现

```bash
python scripts/compare_mqtt_http.py --count 200 --format json
python scripts/compare_mqtt_http.py --count 200 --format json-min
python scripts/compare_mqtt_http.py --count 200 --format msgpack
# 需本地有 MQTT broker 在 1883；脚本内置临时 HTTP 服务
```
