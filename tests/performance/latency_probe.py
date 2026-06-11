"""Latency / arrival-rate probe: subscribe and compare send vs receive time.

Run the probe and the simulated nodes on the SAME machine so both sides share
one clock; the measured delay then covers node -> broker -> probe, which for a
cloud broker includes the real WAN round trip.

Payloads may be json, json-min or msgpack (same field mapping as the monitor).
Outputs a per-message CSV plus a summary with delay percentiles, duplicate
count, out-of-order count and a seq-gap based loss estimate.

Example (cloud EMQX):
    python latency_probe.py --broker-host <server-ip> --duration 60 \
        --output captures/latency_wan.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt

try:
    import msgpack
except ImportError:
    msgpack = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure MQTT delivery latency and arrival.")
    parser.add_argument("--broker-host", default="127.0.0.1")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--topic", default="env_monitor/+/+")
    parser.add_argument("--qos", type=int, default=1, choices=(0, 1, 2))
    parser.add_argument("--duration", type=float, default=60.0,
                        help="Seconds to listen before printing the summary.")
    parser.add_argument("--mqtt-version", default="5", choices=("5", "311"))
    parser.add_argument("--output", default="", help="Optional per-message CSV path.")
    parser.add_argument("--client-id", default="latency_probe")
    return parser.parse_args()


def send_epoch_from_payload(payload: dict) -> float | None:
    ts = payload.get("timestamp", payload.get("t"))
    if isinstance(ts, (int, float)):
        return ts / 1000 if ts > 1e11 else float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts).timestamp()
        except ValueError:
            return None
    return None


def decode(raw: bytes) -> dict | None:
    if raw[:1] == b"{":
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    elif msgpack is not None:
        try:
            payload = msgpack.unpackb(raw)
        except Exception:
            return None
    else:
        return None
    return payload if isinstance(payload, dict) else None


class Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.rows: list[tuple] = []          # (recv_iso, topic, key, seq, delay_ms)
        self.delays: list[float] = []
        self.invalid = 0
        self.no_timestamp = 0
        self.duplicates = 0
        self.out_of_order = 0
        self.last_seq: dict[tuple, int] = {}
        self.seen: dict[tuple, set[int]] = {}

    def add(self, topic: str, payload: dict, recv_epoch: float) -> None:
        node = str(payload.get("node_id", payload.get("n", "?")))
        dtype = str(payload.get("data_type", payload.get("d", "?")))
        seq = payload.get("seq", payload.get("s"))
        # seq increases per NODE across all its data types, so gap/duplicate
        # tracking must be keyed by node, not by (node, type).
        key = (node,)
        send_epoch = send_epoch_from_payload(payload)
        delay_ms = (recv_epoch - send_epoch) * 1000 if send_epoch else None
        with self.lock:
            if isinstance(seq, int):
                seen = self.seen.setdefault(key, set())
                if seq in seen:
                    self.duplicates += 1
                seen.add(seq)
                if seq < self.last_seq.get(key, 0):
                    self.out_of_order += 1
                self.last_seq[key] = max(self.last_seq.get(key, 0), seq)
            if delay_ms is None:
                self.no_timestamp += 1
            else:
                self.delays.append(delay_ms)
            self.rows.append((
                datetime.fromtimestamp(recv_epoch).isoformat(timespec="milliseconds"),
                topic, f"{node}/{dtype}", seq,
                f"{delay_ms:.1f}" if delay_ms is not None else "",
            ))

    def summary(self) -> str:
        with self.lock:
            received = len(self.rows)
            expected = sum(max(seqs) - min(seqs) + 1 for seqs in self.seen.values() if seqs)
            unique = sum(len(seqs) for seqs in self.seen.values())
            lost = expected - unique if expected else 0
            lines = [
                f"received={received} invalid={self.invalid} no_timestamp={self.no_timestamp}",
                f"seq-span expected={expected} unique={unique} lost={lost} "
                f"arrival={100.0 * unique / expected:.2f}%" if expected else "no seq data",
                f"duplicates={self.duplicates} out_of_order={self.out_of_order}",
            ]
            if self.delays:
                ordered = sorted(self.delays)

                def pct(p: float) -> float:
                    return ordered[min(len(ordered) - 1, int(p * len(ordered)))]

                lines.append(
                    f"delay_ms avg={sum(ordered) / len(ordered):.1f} p50={pct(0.50):.1f} "
                    f"p95={pct(0.95):.1f} max={ordered[-1]:.1f}"
                )
            return "\n".join(lines)


def main() -> None:
    args = parse_args()
    stats = Stats()
    use_v5 = args.mqtt_version == "5"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.client_id,
                         protocol=mqtt.MQTTv5 if use_v5 else mqtt.MQTTv311)

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        print(f"[probe] connected, subscribing {args.topic} qos={args.qos}")
        client.subscribe(args.topic, qos=args.qos)

    def on_message(client, userdata, message) -> None:
        recv_epoch = time.time()
        payload = decode(message.payload)
        if payload is None:
            with stats.lock:
                stats.invalid += 1
            return
        stats.add(message.topic, payload, recv_epoch)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker_host, args.broker_port, keepalive=30)
    client.loop_start()

    print(f"[probe] listening for {args.duration:.0f}s ...")
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        pass
    client.loop_stop()
    client.disconnect()

    print("=== latency probe summary ===")
    print(stats.summary())
    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["recv_time", "topic", "node/type", "seq", "delay_ms"])
            writer.writerows(stats.rows)
        print(f"[probe] per-message rows written to {args.output}")


if __name__ == "__main__":
    main()
