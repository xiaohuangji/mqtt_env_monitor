"""Publish MQTT test messages that follow the project topic and JSON format."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable

import paho.mqtt.client as mqtt


DATA_UNITS = {
    "temperature": "C",
    "humidity": "%RH",
    "light": "lux",
    "noise": "dB",
}

BASE_VALUES = {
    "temperature": 26.5,
    "humidity": 58.0,
    "light": 420.0,
    "noise": 48.0,
}

DEFAULT_NODES = ("node01", "node02")
DEFAULT_TYPES = ("temperature", "humidity", "light", "noise")
CN_TZ = timezone(timedelta(hours=8))


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish MQTT test messages.")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker host.")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port.")
    parser.add_argument("--qos", type=int, default=0, choices=(0, 1, 2), help="MQTT QoS.")
    parser.add_argument("--nodes", default=",".join(DEFAULT_NODES), help="Comma-separated node ids.")
    parser.add_argument("--types", default=",".join(DEFAULT_TYPES), help="Comma-separated data types.")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat count for each node/type set.")
    parser.add_argument("--interval", type=float, default=0.2, help="Interval between messages in seconds.")
    parser.add_argument("--client-id", default="mqtt_pub_test", help="MQTT client id.")
    return parser.parse_args()


def build_payload(node_id: str, data_type: str, seq: int, repeat_index: int) -> dict[str, object]:
    node_offset = int(node_id[-2:]) - 1 if node_id[-2:].isdigit() else 0
    value = BASE_VALUES[data_type] + node_offset + repeat_index * 0.1

    if data_type in {"humidity", "light", "noise"}:
        value = round(value, 1)
    else:
        value = round(value, 2)

    return {
        "node_id": node_id,
        "data_type": data_type,
        "value": value,
        "unit": DATA_UNITS[data_type],
        "timestamp": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "seq": seq,
    }


def validate_data_types(data_types: Iterable[str]) -> None:
    unknown = [data_type for data_type in data_types if data_type not in DATA_UNITS]
    if unknown:
        raise SystemExit(f"Unsupported data type(s): {', '.join(unknown)}")


def publish_messages(args: argparse.Namespace) -> int:
    nodes = parse_csv(args.nodes)
    data_types = parse_csv(args.types)
    validate_data_types(data_types)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        protocol=mqtt.MQTTv311,
    )
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()

    seq_by_node = {node_id: 0 for node_id in nodes}
    sent = 0

    try:
        for repeat_index in range(args.repeat):
            for node_id in nodes:
                for data_type in data_types:
                    seq_by_node[node_id] += 1
                    payload = build_payload(node_id, data_type, seq_by_node[node_id], repeat_index)
                    topic = f"env_monitor/{node_id}/{data_type}"
                    message = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    result = client.publish(topic, message, qos=args.qos)
                    result.wait_for_publish(timeout=5)
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        raise RuntimeError(f"Publish failed for {topic}: rc={result.rc}")
                    sent += 1
                    print(f"published topic={topic} payload={message}")
                    time.sleep(args.interval)
    finally:
        client.loop_stop()
        client.disconnect()

    print(f"sent {sent} message(s)")
    return sent


def main() -> None:
    args = parse_args()
    publish_messages(args)


if __name__ == "__main__":
    main()
