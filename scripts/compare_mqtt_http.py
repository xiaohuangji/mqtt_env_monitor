"""MQTT 与 HTTP 上传开销对比实验。

同一条环境监测数据，分别用 MQTT（QoS 1 PUBLISH）与 HTTP（POST）上传，
逐字节测量单次上传的应用层协议字节（发送/接收）、报文头开销、一次性建链开销
与本地往返延迟。

说明：应用层协议字节与网络位置无关——同一条 PUBLISH / POST 发往本地或公网，
线上字节完全相同，故本实验在本地即可精确、可复现地测量协议开销；延迟一项因
受真实网络 RTT 主导，仅作本地参考（公网延迟另有实测）。

用法：
    python scripts/compare_mqtt_http.py --count 200
    python scripts/compare_mqtt_http.py --host 127.0.0.1 --mqtt-port 1883 --format json
"""

from __future__ import annotations

import argparse
import json
import socket
import statistics
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

TOPIC = "env_monitor/node01/temperature"


def make_payload(fmt: str) -> bytes:
    """一条与本系统一致的环境读数。"""
    if fmt == "json":
        d = {"node_id": "node01", "data_type": "temperature", "value": 26.5,
             "unit": "C", "timestamp": "2026-06-17T20:00:00.000+08:00", "seq": 1}
        return json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # json-min / msgpack：短键、epoch 毫秒、单位由监控端反查
    d = {"n": "node01", "d": "temperature", "v": 26.5, "t": 1781827200000, "s": 1}
    if fmt == "msgpack":
        import msgpack
        return msgpack.packb(d)
    return json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def recv_n(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("connection closed by peer")
        data += chunk
    return data


# ========================= HTTP =========================

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = b"ok"
        self.send_response(200)           # 自动附带 Server、Date 头（贴近真实 HTTP 服务）
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # 静音
        pass


def start_http_server(port: int) -> HTTPServer:
    srv = HTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def build_http_request(host: str, port: int, body: bytes, keep_alive: bool,
                       content_type: str = "application/json") -> bytes:
    """构造与标准客户端（python-requests）一致的请求头。"""
    conn = "keep-alive" if keep_alive else "close"
    head = (
        f"POST /up HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"User-Agent: python-requests/2.31.0\r\n"
        f"Accept-Encoding: gzip, deflate\r\n"
        f"Accept: */*\r\n"
        f"Connection: {conn}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode("ascii")
    return head + body


def read_http_response(sock: socket.socket) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    head, _, rest = data.partition(b"\r\n\r\n")
    content_length = 0
    for line in head.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1])
    body = rest
    while len(body) < content_length:
        chunk = sock.recv(4096)
        if not chunk:
            break
        body += chunk
    return head + b"\r\n\r\n" + body[:content_length]


def run_http(host: str, port: int, body: bytes, count: int, keep_alive: bool,
             content_type: str = "application/json"):
    out_total = in_total = 0
    latencies = []
    sample_req = sample_resp = b""
    sock = None
    try:
        for _ in range(count):
            if sock is None:
                sock = socket.create_connection((host, port))
            req = build_http_request(host, port, body, keep_alive, content_type)
            t0 = time.perf_counter()
            sock.sendall(req)
            resp = read_http_response(sock)
            latencies.append((time.perf_counter() - t0) * 1000)
            out_total += len(req)
            in_total += len(resp)
            if not sample_req:
                sample_req, sample_resp = req, resp
            if not keep_alive:
                sock.close()
                sock = None
    finally:
        if sock:
            sock.close()
    return {
        "out": out_total / count, "in": in_total / count,
        "total": (out_total + in_total) / count,
        "latency_ms": statistics.mean(latencies),
        "sample_req": sample_req, "sample_resp": sample_resp,
    }


# ========================= MQTT 3.1.1（QoS 1，原始套接字，逐字节可控） =========================

def _remaining_length(n: int) -> bytes:
    out = b""
    while True:
        byte = n % 128
        n //= 128
        if n > 0:
            byte |= 0x80
        out += bytes([byte])
        if n == 0:
            return out


def mqtt_connect(client_id: str, keepalive: int = 30) -> bytes:
    var_header = b"\x00\x04MQTT" + b"\x04" + b"\x02" + struct.pack(">H", keepalive)  # level 4, clean session
    payload = struct.pack(">H", len(client_id)) + client_id.encode("ascii")
    rem = var_header + payload
    return b"\x10" + _remaining_length(len(rem)) + rem


def mqtt_publish_qos1(topic: str, payload: bytes, packet_id: int) -> bytes:
    var_header = struct.pack(">H", len(topic)) + topic.encode("ascii") + struct.pack(">H", packet_id)
    rem = var_header + payload
    return b"\x32" + _remaining_length(len(rem)) + rem        # 0x32 = PUBLISH, QoS 1


def run_mqtt(host: str, port: int, body: bytes, count: int):
    sock = socket.create_connection((host, port))
    connect_pkt = mqtt_connect("cmp_node01")
    sock.sendall(connect_pkt)
    connack = recv_n(sock, 4)                                  # CONNACK 固定 4 字节
    if connack[0] != 0x20 or connack[3] != 0x00:
        sock.close()
        raise ConnectionError(f"MQTT CONNECT 被拒：{connack!r}")
    connect_out, connect_in = len(connect_pkt), len(connack)

    out_total = in_total = 0
    latencies = []
    sample_pub = b""
    try:
        for i in range(count):
            pub = mqtt_publish_qos1(TOPIC, body, (i % 65535) + 1)
            t0 = time.perf_counter()
            sock.sendall(pub)
            puback = recv_n(sock, 4)                            # PUBACK 固定 4 字节
            latencies.append((time.perf_counter() - t0) * 1000)
            out_total += len(pub)
            in_total += len(puback)
            if not sample_pub:
                sample_pub = pub
    finally:
        sock.close()
    return {
        "out": out_total / count, "in": in_total / count,
        "total": (out_total + in_total) / count,
        "latency_ms": statistics.mean(latencies),
        "connect_once": connect_out + connect_in,
        "sample_pub": sample_pub,
    }


# ========================= 主流程 =========================

def main() -> None:
    ap = argparse.ArgumentParser(description="MQTT 与 HTTP 上传开销对比实验")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    ap.add_argument("--http-port", type=int, default=18080, help="内置 HTTP 服务端口")
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--format", default="json", choices=("json", "json-min", "msgpack"))
    args = ap.parse_args()

    body = make_payload(args.format)
    ctype = "application/msgpack" if args.format == "msgpack" else "application/json"
    print(f"实验参数：payload={args.format}（{len(body)} B）  样本数 N={args.count}  topic={TOPIC}")
    print("=" * 78)

    start_http_server(args.http_port)
    time.sleep(0.3)
    http_ka = run_http(args.host, args.http_port, body, args.count, keep_alive=True, content_type=ctype)
    http_new = run_http(args.host, args.http_port, body, args.count, keep_alive=False, content_type=ctype)

    try:
        mqtt = run_mqtt(args.host, args.mqtt_port, body, args.count)
    except (OSError, ConnectionError) as exc:
        print(f"\n[!] 连接 MQTT broker {args.host}:{args.mqtt_port} 失败：{exc}")
        print("    请先确保本地有 MQTT broker 在 1883（EMQX/mosquitto）。仅打印 HTTP 结果。")
        mqtt = None

    def row(name, d):
        print(f"{name:<26}{d['out']:>8.1f}{d['in']:>9.1f}{d['total']:>10.1f}{d['latency_ms']:>11.3f}")

    print(f"\n{'方式':<24}{'发送 B':>10}{'接收 B':>9}{'合计 B':>10}{'本地RTT ms':>11}")
    print("-" * 78)
    if mqtt:
        row("MQTT QoS1 PUBLISH", mqtt)
    row("HTTP POST (keep-alive)", http_ka)
    row("HTTP POST (每次新建连接)", http_new)
    print("-" * 78)

    if mqtt:
        save = (1 - mqtt["total"] / http_ka["total"]) * 100
        mqtt_overhead = mqtt["total"] - len(body)
        http_overhead = http_ka["total"] - len(body)
        print(f"\n负载 payload 本身 = {len(body)} B（两者相同）")
        print(f"协议开销（合计 - payload）：MQTT {mqtt_overhead:.1f} B  vs  HTTP {http_overhead:.1f} B"
              f"  → MQTT 单次开销约为 HTTP 的 {mqtt_overhead / http_overhead * 100:.0f}%")
        print(f"单次上传合计字节：MQTT {mqtt['total']:.1f} B  vs  HTTP {http_ka['total']:.1f} B"
              f"  → MQTT 省 {save:.0f}%")
        print(f"一次性建链：MQTT CONNECT+CONNACK = {mqtt['connect_once']} B（长连接复用，仅 1 次）；"
              f"HTTP 每次新建连接还要额外 TCP 三次握手")
        print("\n样例 MQTT PUBLISH 字节：", mqtt["sample_pub"])
    print("\n样例 HTTP 请求：")
    print(http_ka["sample_req"].decode("latin-1"))
    print("样例 HTTP 响应：")
    print(http_ka["sample_resp"].decode("latin-1"))


if __name__ == "__main__":
    main()
