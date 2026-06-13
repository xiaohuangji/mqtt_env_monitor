"""Web monitor that subscribes to environment topics and serves a live dashboard.

The backend subscribes to ``env_monitor/+/+`` with paho-mqtt, keeps the latest
entry per (node_id, data_type), logs every received message with its receive
time, and pushes updates to browsers through Server-Sent Events (SSE).

Payloads may be json, json-min or msgpack (see
docs/project_outputs/课程设计报告/网络负载与成本建模.md for the field mapping);
``--mqtt-version`` selects MQTT 5.0 (default) or 3.1.1.
"""

from __future__ import annotations

import argparse
import json
import queue
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify, render_template

# Sizing-calculator coefficients, calibrated by the capture/load experiments
# (see docs/project_outputs/课程设计报告/网络负载与成本建模.md §10).
CALC_CONFIG_PATH = Path(__file__).resolve().parent / "calc_config.json"


CN_TZ = timezone(timedelta(hours=8))

# Display names for known data types; unknown types fall back to the raw key.
DATA_TYPE_CN = {
    "temperature": "温度",
    "humidity": "湿度",
    "light": "光照",
    "noise": "噪声",
    "pressure": "气压",
    "co2": "二氧化碳浓度",
    "pm25": "PM2.5",
    "mq2_gas": "可燃气体",
    "soil_moisture": "土壤湿度",
}

# Default units when compact payloads omit the unit field.
UNIT_BY_TYPE = {
    "temperature": "C",
    "humidity": "%RH",
    "light": "lux",
    "noise": "dB",
    "pressure": "hPa",
    "co2": "ppm",
    "pm25": "ug/m3",
    "mq2_gas": "raw",      # MQ-2 原始 ADC 值(0-4095),阈值标定后可换算 ppm
    "soil_moisture": "%",  # FC-28 换算为百分比
}

# json-min / msgpack short keys -> full field names.
SHORT_KEYS = {"n": "node_id", "d": "data_type", "v": "value", "u": "unit", "t": "timestamp", "s": "seq"}

try:
    import msgpack
except ImportError:  # binary payloads are then counted as invalid
    msgpack = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the web monitor for env_monitor topics.")
    parser.add_argument("--broker-host", default="127.0.0.1", help="MQTT broker host.")
    parser.add_argument("--broker-port", type=int, default=1883, help="MQTT broker port.")
    parser.add_argument("--topic", default="env_monitor/+/+", help="MQTT topic filter to subscribe.")
    parser.add_argument("--qos", type=int, default=0, choices=(0, 1, 2), help="Subscribe QoS.")
    parser.add_argument("--web-host", default="127.0.0.1", help="Web server bind host.")
    parser.add_argument("--web-port", type=int, default=8080, help="Web server bind port.")
    parser.add_argument("--offline-after", type=float, default=15.0,
                        help="Mark an entry stale after this many seconds without data.")
    parser.add_argument("--log-file", default="", help="Optional file to append receive logs.")
    parser.add_argument("--client-id", default="web_monitor", help="MQTT client id.")
    parser.add_argument("--mqtt-version", default="5", choices=("5", "311"),
                        help="MQTT protocol version.")
    return parser.parse_args()


def now_dt() -> datetime:
    return datetime.now(CN_TZ)


def is_failure(reason_code: object) -> bool:
    if hasattr(reason_code, "is_failure"):
        return bool(reason_code.is_failure)
    return reason_code != 0


def decode_payload(raw: bytes) -> tuple[dict, str]:
    """Decode json / json-min / msgpack payload bytes; raises ValueError."""
    if raw[:1] == b"{":
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"bad json: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
        return payload, ("json" if "node_id" in payload else "json-min")
    if msgpack is None:
        raise ValueError("binary payload but msgpack package not installed")
    try:
        payload = msgpack.unpackb(raw)
    except Exception as exc:  # msgpack raises several exception types
        raise ValueError(f"bad msgpack: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")
    return payload, "msgpack"


def normalize_payload(payload: dict) -> dict:
    """Expand short keys and epoch-ms timestamps from compact formats."""
    out = {SHORT_KEYS.get(key, key): value for key, value in payload.items()}
    ts = out.get("timestamp")
    if isinstance(ts, (int, float)):
        seconds = ts / 1000 if ts > 1e11 else ts
        out["timestamp"] = datetime.fromtimestamp(seconds, CN_TZ).isoformat(timespec="milliseconds")
    if not out.get("unit"):
        out["unit"] = UNIT_BY_TYPE.get(str(out.get("data_type", "")), "")
    return out


class MonitorState:
    """Latest entries plus SSE subscriber queues, shared across threads."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.Lock()
        self.latest: dict[tuple[str, str], dict[str, object]] = {}
        self.subscribers: list[queue.Queue] = []
        self.received_total = 0
        self.invalid_total = 0
        self.format_counts: dict[str, int] = {}
        self.log_handle = open(args.log_file, "a", encoding="utf-8") if args.log_file else None

    def log(self, line: str) -> None:
        print(line)
        if self.log_handle:
            self.log_handle.write(line + "\n")
            self.log_handle.flush()

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            entries = sorted(
                self.latest.values(),
                key=lambda e: (str(e["node_id"]), str(e["data_type"])),
            )
            return {
                "server_now": now_dt().timestamp(),
                "offline_after": self.args.offline_after,
                "broker": f"{self.args.broker_host}:{self.args.broker_port}",
                "topic": self.args.topic,
                "received_total": self.received_total,
                "invalid_total": self.invalid_total,
                "format_counts": dict(self.format_counts),
                "type_names": DATA_TYPE_CN,
                "entries": entries,
            }

    def register(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self.lock:
            self.subscribers.append(q)
        return q

    def unregister(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def handle_message(self, message: mqtt.MQTTMessage) -> None:
        received = now_dt()
        try:
            payload, fmt = decode_payload(message.payload)
        except ValueError as exc:
            with self.lock:
                self.invalid_total += 1
            self.log(
                f"[warn] invalid payload ignored ({exc}): "
                f"topic={message.topic} raw={message.payload[:80]!r}"
            )
            return

        payload = normalize_payload(payload)
        payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.log(
            f"[recv {received.isoformat(timespec='milliseconds')}] "
            f"topic={message.topic} qos={message.qos} format={fmt} payload={payload_text}"
        )

        # Fall back to topic levels when fields are missing, so malformed
        # but routable messages still show up for debugging.
        topic_parts = message.topic.split("/")
        node_id = str(payload.get("node_id") or (topic_parts[1] if len(topic_parts) > 1 else "unknown"))
        data_type = str(payload.get("data_type") or (topic_parts[2] if len(topic_parts) > 2 else "unknown"))

        entry = {
            "node_id": node_id,
            "data_type": data_type,
            "value": payload.get("value"),
            "unit": payload.get("unit", ""),
            "timestamp": payload.get("timestamp", ""),
            "seq": payload.get("seq"),
            "topic": message.topic,
            "qos": message.qos,
            "format": fmt,
            "received_at": received.isoformat(timespec="milliseconds"),
            "received_epoch": received.timestamp(),
        }

        with self.lock:
            self.latest[(node_id, data_type)] = entry
            self.received_total += 1
            self.format_counts[fmt] = self.format_counts.get(fmt, 0) + 1
            update = {"entry": entry, "received_total": self.received_total}
            for q in self.subscribers:
                q.put(update)


def build_mqtt_client(state: MonitorState) -> mqtt.Client:
    args = state.args
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=args.client_id,
        protocol=mqtt.MQTTv5 if args.mqtt_version == "5" else mqtt.MQTTv311,
    )

    def on_connect(client: mqtt.Client, userdata: object, flags: object, reason_code: object, properties: object) -> None:
        if is_failure(reason_code):
            state.log(f"[mqtt] connect failed: {reason_code}")
            return
        state.log(f"[mqtt] connected to {args.broker_host}:{args.broker_port}, subscribing {args.topic} qos={args.qos}")
        client.subscribe(args.topic, qos=args.qos)

    def on_disconnect(client: mqtt.Client, userdata: object, flags: object, reason_code: object, properties: object) -> None:
        state.log(f"[mqtt] disconnected from broker (reason={reason_code}), auto reconnect enabled")

    def on_message(client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        state.handle_message(message)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.connect_async(args.broker_host, args.broker_port, keepalive=30)
    return client


def build_app(state: MonitorState) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/data")
    def api_data() -> Response:
        return jsonify(state.snapshot())

    @app.get("/calculator")
    def calculator() -> str:
        return render_template("calculator.html")

    @app.get("/api/calc_config")
    def api_calc_config() -> Response:
        return jsonify(json.loads(CALC_CONFIG_PATH.read_text(encoding="utf-8")))

    @app.get("/stream")
    def stream() -> Response:
        def generate():
            q = state.register()
            try:
                yield "event: snapshot\ndata: " + json.dumps(state.snapshot(), ensure_ascii=False) + "\n\n"
                while True:
                    try:
                        update = q.get(timeout=15)
                        yield "event: update\ndata: " + json.dumps(update, ensure_ascii=False) + "\n\n"
                    except queue.Empty:
                        yield ": keepalive\n\n"
            finally:
                state.unregister(q)

        return Response(generate(), mimetype="text/event-stream")

    return app


def main() -> None:
    args = parse_args()
    state = MonitorState(args)

    client = build_mqtt_client(state)
    client.loop_start()

    app = build_app(state)
    state.log(f"[web] monitor page at http://{args.web_host}:{args.web_port}/")
    try:
        app.run(host=args.web_host, port=args.web_port, threaded=True)
    finally:
        client.loop_stop()
        client.disconnect()
        if state.log_handle:
            state.log_handle.close()


if __name__ == "__main__":
    main()
