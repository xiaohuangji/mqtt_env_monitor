"""Simulated environment monitoring node that continuously publishes MQTT data.

Each node simulates one or more environment data types and publishes JSON
messages to ``env_monitor/{node_id}/{data_type}`` at a fixed interval.
Values follow a mean-reverting random walk so the data drifts smoothly
within a realistic range instead of jumping randomly.
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt


CN_TZ = timezone(timedelta(hours=8))

# Per data type: unit, base value, mean-reversion rate, noise scale, value range, decimals.
SIM_PROFILES = {
    "temperature": {"unit": "C", "base": 26.5, "revert": 0.05, "sigma": 0.15, "min": 15.0, "max": 35.0, "ndigits": 2},
    "humidity": {"unit": "%RH", "base": 58.0, "revert": 0.05, "sigma": 0.8, "min": 20.0, "max": 90.0, "ndigits": 1},
    "light": {"unit": "lux", "base": 420.0, "revert": 0.05, "sigma": 25.0, "min": 0.0, "max": 1000.0, "ndigits": 1},
    "noise": {"unit": "dB", "base": 48.0, "revert": 0.10, "sigma": 2.5, "min": 30.0, "max": 90.0, "ndigits": 1},
}


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simulated environment monitoring node.")
    parser.add_argument("--node-id", default="node01", help="Node id, e.g. node01.")
    parser.add_argument(
        "--types",
        default=",".join(SIM_PROFILES),
        help="Comma-separated data types to publish, e.g. temperature,humidity.",
    )
    parser.add_argument("--interval", type=float, default=5.0, help="Publish interval in seconds.")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker host.")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port.")
    parser.add_argument("--qos", type=int, default=0, choices=(0, 1, 2), help="MQTT QoS.")
    parser.add_argument("--count", type=int, default=0, help="Stop after this many publish rounds (0 = run forever).")
    parser.add_argument("--client-id", default="", help="MQTT client id (default: sim_{node_id}).")
    return parser.parse_args()


class DataSimulator:
    """Generate smooth values with a mean-reverting random walk."""

    def __init__(self, data_type: str) -> None:
        profile = SIM_PROFILES[data_type]
        self.base = profile["base"]
        self.revert = profile["revert"]
        self.sigma = profile["sigma"]
        self.minimum = profile["min"]
        self.maximum = profile["max"]
        self.ndigits = profile["ndigits"]
        # Start near the base with a random offset so different nodes differ.
        self.value = self.base + random.uniform(-3 * self.sigma, 3 * self.sigma)

    def next_value(self) -> float:
        self.value += self.revert * (self.base - self.value) + random.gauss(0, self.sigma)
        self.value = min(max(self.value, self.minimum), self.maximum)
        return round(self.value, self.ndigits)


def now_iso() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def is_failure(reason_code: object) -> bool:
    if hasattr(reason_code, "is_failure"):
        return bool(reason_code.is_failure)
    return reason_code != 0


def build_payload(node_id: str, data_type: str, value: float, seq: int) -> str:
    payload = {
        "node_id": node_id,
        "data_type": data_type,
        "value": value,
        "unit": SIM_PROFILES[data_type]["unit"],
        "timestamp": now_iso(),
        "seq": seq,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def run_node(args: argparse.Namespace) -> None:
    data_types = parse_csv(args.types)
    unknown = [data_type for data_type in data_types if data_type not in SIM_PROFILES]
    if unknown:
        raise SystemExit(f"Unsupported data type(s): {', '.join(unknown)}")
    if not data_types:
        raise SystemExit("No data type specified.")
    if args.interval <= 0:
        raise SystemExit("Interval must be positive.")

    client_id = args.client_id or f"sim_{args.node_id}"
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311,
    )

    connected = threading.Event()

    def on_connect(client: mqtt.Client, userdata: object, flags: object, reason_code: object, properties: object) -> None:
        if is_failure(reason_code):
            print(f"[{now_iso()}] connect failed: {reason_code}")
        else:
            print(f"[{now_iso()}] connected to {args.host}:{args.port} as {client_id}")
            connected.set()

    def on_disconnect(client: mqtt.Client, userdata: object, flags: object, reason_code: object, properties: object) -> None:
        connected.clear()
        print(f"[{now_iso()}] disconnected from broker (reason={reason_code}), auto reconnect enabled")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=5)

    print(
        f"[{now_iso()}] node {args.node_id} started: types={','.join(data_types)} "
        f"interval={args.interval}s qos={args.qos} broker={args.host}:{args.port}"
    )

    # connect_async + loop_start keeps retrying until the broker is reachable,
    # and automatically reconnects after the broker restarts.
    client.connect_async(args.host, args.port, keepalive=30)
    client.loop_start()

    if not connected.wait(timeout=10):
        print(f"[{now_iso()}] broker not reachable yet, publishing starts anyway (auto retry in background)")

    simulators = {data_type: DataSimulator(data_type) for data_type in data_types}
    seq = 0
    attempted = 0
    succeeded = 0
    queued = 0
    failed = 0

    try:
        rounds = 0
        while args.count <= 0 or rounds < args.count:
            for data_type in data_types:
                seq += 1
                attempted += 1
                value = simulators[data_type].next_value()
                topic = f"env_monitor/{args.node_id}/{data_type}"
                message = build_payload(args.node_id, data_type, value, seq)
                result = client.publish(topic, message, qos=args.qos)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    succeeded += 1
                    print(f"[{now_iso()}] publish ok topic={topic} qos={args.qos} payload={message}")
                elif result.rc == mqtt.MQTT_ERR_NO_CONN and args.qos > 0:
                    # paho queues QoS 1/2 messages while offline and resends them after reconnect.
                    queued += 1
                    print(f"[{now_iso()}] publish queued (offline) topic={topic} seq={seq}")
                else:
                    failed += 1
                    print(f"[{now_iso()}] publish failed rc={result.rc} topic={topic} seq={seq}")
            rounds += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n[{now_iso()}] node {args.node_id} stopping...")
    finally:
        client.loop_stop()
        client.disconnect()
        print(
            f"[{now_iso()}] node {args.node_id} stopped: "
            f"attempted={attempted} succeeded={succeeded} queued={queued} failed={failed}"
        )


def main() -> None:
    run_node(parse_args())


if __name__ == "__main__":
    main()
