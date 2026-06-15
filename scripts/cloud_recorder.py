"""云端 MQTT 消息记录器（Issue #42 ESP32 室外长时间测试用）。

在云服务器上后台运行，订阅 ESP32 上传的数据并写入日志文件，**本地电脑无需开机**。
日志格式与监控端 --log-file 完全一致，测试结束后下载下来即可用
scripts/analyze_esp32_field.py 直接分析。

采用持久会话（clean_session=False + 固定 client_id + QoS 1）：即使记录器进程
偶尔重启，Broker 也会把断线期间的消息补发过来，保证 15 小时数据不缺。

云服务器上后台启动示例：
    nohup python3 cloud_recorder.py --log ~/esp32_0615.log > ~/recorder.out 2>&1 &
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt

CN_TZ = timezone(timedelta(hours=8))


def main() -> None:
    ap = argparse.ArgumentParser(description="云端 ESP32 数据记录器")
    ap.add_argument("--host", default="127.0.0.1", help="EMQX 地址（云上本机用 127.0.0.1）")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", default="env_monitor/+/+", help="订阅主题（默认记录全部节点）")
    ap.add_argument("--qos", type=int, default=1)
    ap.add_argument("--log", required=True, help="日志输出文件")
    ap.add_argument("--client-id", default="esp32_field_recorder")
    args = ap.parse_args()

    fh = open(args.log, "a", encoding="utf-8")

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"[recorder] connected ({reason_code}), subscribing {args.topic} qos={args.qos}", flush=True)
        client.subscribe(args.topic, qos=args.qos)

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        print(f"[recorder] disconnected ({reason_code}), auto-reconnecting...", flush=True)

    def on_message(client, userdata, msg):
        now = datetime.now(CN_TZ).isoformat(timespec="milliseconds")
        raw = msg.payload.decode("utf-8", errors="replace")
        line = f"[recv {now}] topic={msg.topic} qos={msg.qos} payload={raw}"
        print(line, flush=True)
        fh.write(line + "\n")
        fh.flush()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        protocol=mqtt.MQTTv311,
        clean_session=False,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect(args.host, args.port, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
