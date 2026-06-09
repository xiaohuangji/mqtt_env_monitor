"""Subscribe to project MQTT topics and print received JSON messages."""

from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt


CN_TZ = timezone(timedelta(hours=8))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Subscribe to MQTT test messages.")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker host.")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port.")
    parser.add_argument("--topic", default="env_monitor/+/+", help="MQTT topic filter.")
    parser.add_argument("--qos", type=int, default=0, choices=(0, 1, 2), help="MQTT QoS.")
    parser.add_argument("--count", type=int, default=0, help="Stop after receiving this many messages.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Stop after this many seconds.")
    parser.add_argument("--client-id", default="mqtt_sub_test", help="MQTT client id.")
    return parser.parse_args()


def is_failure(reason_code: object) -> bool:
    if hasattr(reason_code, "is_failure"):
        return bool(reason_code.is_failure)
    return reason_code != 0


def main() -> None:
    args = parse_args()
    connected = threading.Event()
    finished = threading.Event()
    state = {"received": 0}

    def on_connect(client: mqtt.Client, userdata: object, flags: object, reason_code: object, properties: object) -> None:
        if is_failure(reason_code):
            print(f"connect failed: {reason_code}")
            finished.set()
            return
        print(f"connected to {args.host}:{args.port}, subscribing {args.topic}")
        client.subscribe(args.topic, qos=args.qos)
        connected.set()

    def on_message(client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        state["received"] += 1
        received_at = datetime.now(CN_TZ).isoformat(timespec="seconds")
        payload_text = message.payload.decode("utf-8", errors="replace")

        print(f"[{received_at}] topic={message.topic} qos={message.qos}")
        try:
            payload = json.loads(payload_text)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(payload_text)

        if args.count and state["received"] >= args.count:
            finished.set()
            client.disconnect()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    if not connected.wait(timeout=5):
        client.loop_stop()
        raise SystemExit("subscriber did not connect within 5 seconds")

    deadline = time.monotonic() + args.timeout
    while not finished.wait(timeout=0.2):
        if args.timeout > 0 and time.monotonic() >= deadline:
            print("subscriber timeout reached")
            client.disconnect()
            break

    client.loop_stop()
    print(f"received {state['received']} message(s)")
    if state["received"] == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
