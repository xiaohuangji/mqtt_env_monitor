"""Loaded connection-ramp test (runs on the test server, Linux).

Unlike bench_ramp.py (idle connections), each step here holds N connections
that actively publish, plus a fan-in subscriber set, so the sampled memory
includes message-flow cost (in-flight copies, QoS1 inflight queue, per-sub
send buffers). Holds long enough for RSS to reach a plateau before sampling.

Pairs with bench_ramp.py on the same connection axis: idle slope = per-conn
baseline (m_conn), loaded slope - idle slope = message-flow add-on for the
chosen load profile (per-conn rate / sub count / QoS / payload).

Example (load profile: 1 msg / 15 s per conn, 68 B, QoS1, 10 subscribers):
    python3 bench_loadramp.py --port 1883 --proc-name emqx \
        --steps 5000,10000,20000,35000,50000 \
        --pub-interval-ms 15000 --payload 68 --qos 1 --subs 10 \
        --hold 360 --plateau 240 --output results/loadramp_emqx.csv
"""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
import time
from pathlib import Path

import psutil

from bench_ramp import broker_processes, established_count, sample_tree


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loaded MQTT connection-ramp test.")
    parser.add_argument("--bench", default="/opt/emqtt-bench/bin/emqtt_bench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--label", default="emqx")
    parser.add_argument("--proc-name", default="emqx")
    parser.add_argument("--steps", default="5000,10000,20000,35000,50000")
    parser.add_argument("--pub-interval-ms", type=int, default=15000,
                        help="Per-connection publish interval (15000 = 1 msg / 15 s).")
    parser.add_argument("--payload", type=int, default=68, help="Payload bytes (json-min profile).")
    parser.add_argument("--qos", type=int, default=1, choices=(0, 1, 2))
    parser.add_argument("--subs", type=int, default=10, help="Fan-in subscriber count.")
    parser.add_argument("--conn-interval-ms", type=int, default=1, help="emqtt_bench -i ramp rate.")
    parser.add_argument("--hold", type=float, default=360, help="Total seconds to hold each step.")
    parser.add_argument("--plateau", type=float, default=240,
                        help="Start sampling only after this many seconds (let RSS settle).")
    parser.add_argument("--reach-fraction", type=float, default=0.97)
    parser.add_argument("--output", default="loadramp_results.csv")
    return parser.parse_args()


def run_step(args, target, writer, handle) -> bool:
    procs = broker_processes(args.proc_name)
    if not procs:
        writer.writerow([args.label, target, args.subs, args.qos, 0, "", "", "", "", "broker_missing"])
        return False
    base_conns = established_count(args.port)
    sample_tree(procs)

    out = Path(args.output)
    sub_log = out.with_suffix(f".sub_{target}.log")
    pub_log = out.with_suffix(f".pub_{target}.log")
    # Fan-in subscribers first so they are ready to receive once publishers ramp.
    sub_cmd = (f"{args.bench} sub -h {args.host} -p {args.port} "
               f"-c {args.subs} -t 'load/#' -q {args.qos}")
    pub_cmd = (f"{args.bench} pub -h {args.host} -p {args.port} -c {target} "
               f"-i {args.conn_interval_ms} -I {args.pub_interval_ms} "
               f"-t 'load/%i' -s {args.payload} -q {args.qos}")
    print(f"[step {target}] subs={args.subs} pub_interval={args.pub_interval_ms}ms payload={args.payload}")

    with open(sub_log, "w") as sh, open(pub_log, "w") as ph:
        sub = subprocess.Popen(shlex.split(sub_cmd), stdout=sh, stderr=subprocess.STDOUT)
        time.sleep(3)
        pub = subprocess.Popen(shlex.split(pub_cmd), stdout=ph, stderr=subprocess.STDOUT)

        ramp_deadline = time.time() + target * args.conn_interval_ms / 1000 + 40
        reached = 0
        while time.time() < ramp_deadline:
            time.sleep(2)
            reached = established_count(args.port) - base_conns - args.subs
            if reached >= int(target * args.reach_fraction):
                break
            if not broker_processes(args.proc_name):
                break

        status = "ok" if reached >= int(target * args.reach_fraction) else "below_target"
        if not broker_processes(args.proc_name):
            status = "broker_died"

        # Hold; only sample after the plateau delay so message buffers stabilize.
        rss_s, cpu_s = [], []
        start = time.time()
        while time.time() - start < args.hold and status not in ("broker_died",):
            time.sleep(3)
            if time.time() - start < args.plateau:
                continue
            rss, cpu = sample_tree(procs)
            rss_s.append(rss)
            cpu_s.append(cpu)
            if not broker_processes(args.proc_name):
                status = "broker_died"
                break

        final = established_count(args.port) - base_conns - args.subs
        for p in (pub, sub):
            p.terminate()
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()

    def avg(xs):
        return f"{sum(xs) / len(xs):.1f}" if xs else ""

    def peak(xs):
        return f"{max(xs):.1f}" if xs else ""

    writer.writerow([args.label, target, args.subs, args.qos, max(reached, final),
                     avg(rss_s), peak(rss_s), avg(cpu_s), peak(cpu_s), status])
    handle.flush()
    print(f"[step {target}] reached={max(reached, final)} status={status} "
          f"rss_avg={avg(rss_s)} rss_peak={peak(rss_s)} cpu_avg={avg(cpu_s)}")
    time.sleep(8)
    return status == "ok"


def main() -> None:
    args = parse_args()
    steps = [int(s) for s in args.steps.split(",") if s.strip()]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["broker", "target_conns", "subs", "qos", "reached_conns",
                         "rss_mb_avg", "rss_mb_peak", "cpu_pct_avg", "cpu_pct_peak", "status"])
        for target in steps:
            if not run_step(args, target, writer, handle):
                print(f"[loadramp] stopping at step {target}")
                break
    print(f"[loadramp] results written to {out}")


if __name__ == "__main__":
    main()
