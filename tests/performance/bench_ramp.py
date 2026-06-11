"""Connection-ramp capacity test driver (runs on the test server, Linux).

For each step N it launches ``emqtt_bench conn -c N``, waits for the ramp to
finish, holds the load while sampling the broker process tree (RSS / CPU via
psutil) and the established-connection count on the broker port (via ``ss``),
then tears the bench down and writes one CSV row. A step fails when the bench
cannot reach the target count or the broker process dies; the ramp stops there,
which is exactly the "failure point" data we want for the amqtt baseline.

Example (EMQX):
    python3 bench_ramp.py --label emqx --port 1883 --proc-name beam.smp \
        --steps 1000,5000,10000,20000,50000 --output results/ramp_emqx.csv
Example (amqtt baseline on port 1884):
    python3 bench_ramp.py --label amqtt --port 1884 --proc-name mqtt_broker \
        --steps 100,500,1000,2000,5000 --output results/ramp_amqtt.csv
"""

from __future__ import annotations

import argparse
import csv
import shlex
import subprocess
import time
from pathlib import Path

import psutil


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MQTT broker connection-ramp test.")
    parser.add_argument("--bench", default="/opt/emqtt-bench/bin/emqtt_bench",
                        help="Path to emqtt_bench.")
    parser.add_argument("--host", default="127.0.0.1", help="Broker host.")
    parser.add_argument("--port", type=int, default=1883, help="Broker port.")
    parser.add_argument("--label", default="emqx", help="Broker label written to the CSV.")
    parser.add_argument("--proc-name", default="emqx",
                        help="Substring to find broker processes (emqx / mqtt_broker). "
                             "Do NOT use beam.smp: emqtt_bench is also an Erlang VM.")
    parser.add_argument("--steps", default="1000,5000,10000,20000,50000",
                        help="Comma-separated target connection counts.")
    parser.add_argument("--conn-interval-ms", type=int, default=1,
                        help="emqtt_bench -i value (1 ms ~= 1000 conns/s).")
    parser.add_argument("--proto-version", type=int, default=5, choices=(3, 4, 5),
                        help="MQTT protocol version for bench clients "
                             "(4 = 3.1.1, required for amqtt).")
    parser.add_argument("--hold", type=float, default=30.0,
                        help="Seconds to hold and sample at each step.")
    parser.add_argument("--reach-fraction", type=float, default=0.98,
                        help="Step counts as reached when ss sees >= fraction * target.")
    parser.add_argument("--output", default="ramp_results.csv", help="CSV output path.")
    return parser.parse_args()


# Processes that must never be counted as "the broker": the bench tool is an
# Erlang VM too, and orchestration commands mention broker names in their args.
EXCLUDE_PARTS = ("emqtt_bench", "emqtt-bench", "bench_ramp", "bench_throughput",
                 "run_server_suite", "ssh", "scp", "grep")


def broker_processes(name_part: str) -> list[psutil.Process]:
    procs = []
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            text = " ".join(proc.info["cmdline"] or [proc.info["name"] or ""])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if (name_part in text and proc.pid != psutil.Process().pid
                and not any(part in text for part in EXCLUDE_PARTS)):
            procs.append(proc)
    return procs


def established_count(port: int) -> int:
    out = subprocess.run(
        ["bash", "-c", f"ss -H -tn state established '( sport = :{port} )' | wc -l"],
        capture_output=True, text=True, timeout=20,
    )
    try:
        return int(out.stdout.strip())
    except ValueError:
        return -1


def sample_tree(procs: list[psutil.Process]) -> tuple[float, float]:
    """Return (rss_mb, cpu_percent) summed over processes and their children."""
    rss = 0
    cpu = 0.0
    for proc in procs:
        try:
            members = [proc] + proc.children(recursive=True)
            for member in members:
                rss += member.memory_info().rss
                cpu += member.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rss / 1024 / 1024, cpu


def run_step(args: argparse.Namespace, target: int, writer: csv.writer, handle) -> bool:
    procs = broker_processes(args.proc_name)
    if not procs:
        print(f"[step {target}] broker process '{args.proc_name}' not found, aborting")
        writer.writerow([args.label, target, 0, "", "", "", "", "broker_missing"])
        return False
    baseline_conns = established_count(args.port)
    sample_tree(procs)  # prime cpu_percent counters

    bench_log = Path(args.output).with_suffix(f".bench_{target}.log")
    cmd = (f"{args.bench} conn -h {args.host} -p {args.port} -c {target} "
           f"-i {args.conn_interval_ms} -V {args.proto_version}")
    print(f"[step {target}] {cmd}")
    with open(bench_log, "w") as log_handle:
        bench = subprocess.Popen(shlex.split(cmd), stdout=log_handle, stderr=subprocess.STDOUT)

        ramp_deadline = time.time() + target * args.conn_interval_ms / 1000 + 30
        reached = 0
        while time.time() < ramp_deadline:
            time.sleep(2)
            reached = established_count(args.port) - baseline_conns
            if reached >= int(target * args.reach_fraction):
                break
            if bench.poll() is not None:
                break
            if not broker_processes(args.proc_name):
                break

        status = "ok" if reached >= int(target * args.reach_fraction) else "below_target"
        if not broker_processes(args.proc_name):
            status = "broker_died"

        rss_samples: list[float] = []
        cpu_samples: list[float] = []
        hold_end = time.time() + args.hold
        while time.time() < hold_end and status != "broker_died":
            time.sleep(1)
            rss, cpu = sample_tree(procs)
            rss_samples.append(rss)
            cpu_samples.append(cpu)
            if not broker_processes(args.proc_name):
                status = "broker_died"
                break

        final_conns = established_count(args.port) - baseline_conns
        bench.terminate()
        try:
            bench.wait(timeout=30)
        except subprocess.TimeoutExpired:
            bench.kill()

    def avg(values: list[float]) -> str:
        return f"{sum(values) / len(values):.1f}" if values else ""

    def peak(values: list[float]) -> str:
        return f"{max(values):.1f}" if values else ""

    writer.writerow([args.label, target, max(reached, final_conns),
                     avg(rss_samples), peak(rss_samples),
                     avg(cpu_samples), peak(cpu_samples), status])
    handle.flush()
    print(f"[step {target}] reached={max(reached, final_conns)} status={status} "
          f"rss_avg={avg(rss_samples)}MB cpu_avg={avg(cpu_samples)}%")

    time.sleep(5)  # let the broker release connections before the next step
    return status == "ok"


def main() -> None:
    args = parse_args()
    steps = [int(item) for item in args.steps.split(",") if item.strip()]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["broker", "target_conns", "reached_conns",
                         "rss_mb_avg", "rss_mb_peak", "cpu_pct_avg", "cpu_pct_peak", "status"])
        for target in steps:
            if not run_step(args, target, writer, handle):
                print(f"[ramp] stopping at step {target}")
                break
    print(f"[ramp] results written to {output}")


if __name__ == "__main__":
    main()
