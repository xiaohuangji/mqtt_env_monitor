"""Message-throughput test driver (runs on the test server, Linux).

For each offered rate it launches an ``emqtt_bench sub`` fan-in subscriber and
an ``emqtt_bench pub`` generator (rate = conns * 1000 / interval_ms), samples
the broker process tree, and writes one CSV row. The per-core throughput
coefficient k_core for the sizing model is fitted from cpu_pct vs rate.

Example:
    python3 bench_throughput.py --port 1883 --proc-name beam.smp \
        --rates 1000,5000,10000,20000 --payload-size 118 \
        --output results/throughput_emqx.csv
"""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
import time
from pathlib import Path

import psutil

from bench_ramp import broker_processes, sample_tree


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MQTT broker throughput test.")
    parser.add_argument("--bench", default="/opt/emqtt-bench/bin/emqtt_bench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--label", default="emqx")
    parser.add_argument("--proc-name", default="emqx")
    parser.add_argument("--rates", default="1000,5000,10000,20000",
                        help="Comma-separated offered message rates (msg/s).")
    parser.add_argument("--msg-per-conn", type=int, default=10,
                        help="Messages per second per publisher connection.")
    parser.add_argument("--payload-size", type=int, default=118,
                        help="Payload bytes (defaults to the json profile size).")
    parser.add_argument("--qos", type=int, default=1, choices=(0, 1, 2))
    parser.add_argument("--hold", type=float, default=30.0)
    parser.add_argument("--output", default="throughput_results.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rates = [int(item) for item in args.rates.split(",") if item.strip()]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["broker", "offered_rate", "pub_conns", "qos", "payload_bytes",
                         "rss_mb_avg", "cpu_pct_avg", "cpu_pct_peak", "status"])

        for rate in rates:
            procs = broker_processes(args.proc_name)
            if not procs:
                print(f"[rate {rate}] broker process not found, aborting")
                break
            sample_tree(procs)  # prime cpu counters

            conns = max(1, rate // args.msg_per_conn)
            interval_ms = max(1, int(1000 / args.msg_per_conn))
            sub_cmd = (f"{args.bench} sub -h {args.host} -p {args.port} "
                       f"-c 1 -t 'bench/#' -q {args.qos}")
            pub_cmd = (f"{args.bench} pub -h {args.host} -p {args.port} "
                       f"-c {conns} -I {interval_ms} -t 'bench/%i' "
                       f"-s {args.payload_size} -q {args.qos} -i 1")
            print(f"[rate {rate}] conns={conns} interval={interval_ms}ms")

            sub_log = output.with_suffix(f".sub_{rate}.log")
            pub_log = output.with_suffix(f".pub_{rate}.log")
            with open(sub_log, "w") as sub_handle, open(pub_log, "w") as pub_handle:
                sub = subprocess.Popen(shlex.split(sub_cmd), stdout=sub_handle,
                                       stderr=subprocess.STDOUT)
                time.sleep(3)
                pub = subprocess.Popen(shlex.split(pub_cmd), stdout=pub_handle,
                                       stderr=subprocess.STDOUT)

                # Wait for all publisher connections, then sample the steady state.
                time.sleep(conns * 0.001 + 10)
                rss_samples: list[float] = []
                cpu_samples: list[float] = []
                status = "ok"
                hold_end = time.time() + args.hold
                while time.time() < hold_end:
                    time.sleep(1)
                    rss, cpu = sample_tree(procs)
                    rss_samples.append(rss)
                    cpu_samples.append(cpu)
                    if pub.poll() is not None:
                        status = "pub_exited"
                        break
                    if not broker_processes(args.proc_name):
                        status = "broker_died"
                        break

                for proc in (pub, sub):
                    proc.terminate()
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        proc.kill()

            def avg(values: list[float]) -> str:
                return f"{sum(values) / len(values):.1f}" if values else ""

            writer.writerow([args.label, rate, conns, args.qos, args.payload_size,
                             avg(rss_samples), avg(cpu_samples),
                             f"{max(cpu_samples):.1f}" if cpu_samples else "", status])
            handle.flush()
            print(f"[rate {rate}] cpu_avg={avg(cpu_samples)}% status={status}")
            if status != "ok":
                break
            time.sleep(5)

    print(f"[throughput] results written to {output}")


if __name__ == "__main__":
    main()
