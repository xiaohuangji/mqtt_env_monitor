"""QoS x packet-loss experiment (runs on the test server, Linux, needs root).

Uses our own sim_node (publishes seq-numbered messages) + latency_probe
(counts unique seq received) so arrival rate is measured precisely per
sequence number -- emqtt_bench carries no seq and cannot do this.

`tc netem` injects loss on the loopback interface, so both the
sim_node->broker uplink and the broker->probe downlink traverse the lossy
link (each message crosses it twice). For each (loss, QoS) cell, sim_node and
probe both use the same QoS, giving an end-to-end user-visible arrival rate.

Core lesson: QoS 0 arrival drops with loss; QoS 1/2 recover toward 100% by
retransmission, at the cost of latency.

Topic Alias is disabled (--no-topic-alias) so a lost alias-registration
packet cannot corrupt later QoS 0 messages -- we isolate the QoS variable.

Run from tests/performance on the server (needs sim_node uploaded):
    sudo python3 qos_loss_test.py --losses 0,5,15 --qos-list 0,1,2 \
        --count 100 --nodes 3 --output results/qos_loss.csv
"""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SIM = REPO / "src" / "simulated_nodes" / "sim_node.py"
PROBE = Path(__file__).resolve().parent / "latency_probe.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QoS x packet-loss arrival/latency test (seq-accurate).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--iface", default="lo")
    parser.add_argument("--losses", default="0,5,15", help="Single-trip loss percentages.")
    parser.add_argument("--qos-list", default="0,1,2")
    parser.add_argument("--count", type=int, default=100, help="Messages per node.")
    parser.add_argument("--nodes", type=int, default=3)
    parser.add_argument("--interval", type=float, default=0.1, help="Publish interval per node (s).")
    parser.add_argument("--settle", type=float, default=10.0, help="Extra seconds after publish for in-flight/retransmit.")
    parser.add_argument("--output", default="qos_loss.csv")
    return parser.parse_args()


def set_loss(iface: str, pct: float) -> None:
    subprocess.run(shlex.split(f"tc qdisc del dev {iface} root"),
                   stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    if pct > 0:
        subprocess.run(shlex.split(f"tc qdisc add dev {iface} root netem loss {pct}%"), check=True)


def clear_loss(iface: str) -> None:
    subprocess.run(shlex.split(f"tc qdisc del dev {iface} root"),
                   stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


def run_cell(args, loss, qos, out: Path):
    cell_csv = out.with_suffix(f".cell_l{int(loss)}_q{qos}.csv")
    send_secs = args.count * args.interval
    probe_dur = send_secs + args.settle + 5
    # Probe subscribes first; same QoS as publishers for end-to-end semantics.
    probe_cmd = [sys.executable, str(PROBE), "--broker-host", args.host, "--broker-port", str(args.port),
                 "--qos", str(qos), "--duration", str(probe_dur), "--mqtt-version", "311",
                 "--output", str(cell_csv)]
    probe = subprocess.Popen(probe_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    nodes = []
    for i in range(args.nodes):
        node_cmd = [sys.executable, str(SIM), "--host", args.host, "--port", str(args.port),
                    "--node-id", f"q{i+1:02d}", "--types", "temperature", "--interval", str(args.interval),
                    "--count", str(args.count), "--qos", str(qos), "--mqtt-version", "311"]
        nodes.append(subprocess.Popen(node_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for n in nodes:
        n.wait()
    time.sleep(args.settle)
    probe.wait(timeout=probe_dur + 20)

    # Count unique (node, seq) the probe actually received.
    received = set()
    delays = []
    if cell_csv.exists():
        for row in csv.DictReader(open(cell_csv, encoding="utf-8")):
            received.add((row["node/type"], row["seq"]))
            if row["delay_ms"]:
                delays.append(float(row["delay_ms"]))
    expected = args.count * args.nodes
    arrival = 100.0 * len(received) / expected if expected else 0
    delays.sort()
    avg = sum(delays) / len(delays) if delays else 0
    p95 = delays[min(len(delays) - 1, int(0.95 * len(delays)))] if delays else 0
    return expected, len(received), arrival, avg, p95


def main() -> None:
    args = parse_args()
    if not SIM.exists():
        sys.exit(f"sim_node not found at {SIM}")
    losses = [float(x) for x in args.losses.split(",") if x.strip()]
    qos_list = [int(x) for x in args.qos_list.split(",") if x.strip()]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(out, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["loss_pct", "qos", "sent", "received_unique",
                             "arrival_pct", "delay_ms_avg", "delay_ms_p95"])
            for loss in losses:
                set_loss(args.iface, loss)
                print(f"=== loss {loss}% on {args.iface} ===")
                for qos in qos_list:
                    sent, recv, arrival, avg, p95 = run_cell(args, loss, qos, out)
                    writer.writerow([loss, qos, sent, recv, f"{arrival:.2f}", f"{avg:.1f}", f"{p95:.1f}"])
                    handle.flush()
                    print(f"  qos{qos}: sent={sent} recv={recv} arrival={arrival:.2f}% "
                          f"delay_avg={avg:.1f}ms p95={p95:.1f}ms")
    finally:
        clear_loss(args.iface)
        print("[netem] cleared")
    print(f"[qos_loss] written to {out}")


if __name__ == "__main__":
    main()
