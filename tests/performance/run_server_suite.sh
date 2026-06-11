#!/usr/bin/env bash
# Day-2 capacity suite, run ON the test server as root.
# Prerequisites: EMQX running (systemctl start emqx), repo files uploaded to
# ~/mqtt_env_monitor, emqtt_bench at /opt/emqtt-bench, psutil + amqtt installed.
set -e
cd "$(dirname "$0")"

ulimit -n 1000000
RESULTS=results
mkdir -p "$RESULTS"

echo "=== 1/3 EMQX connection ramp (1k -> 50k) ==="
python3 bench_ramp.py --label emqx --port 1883 --proc-name emqx \
    --steps 1000,5000,10000,20000,50000 --hold 30 \
    --output "$RESULTS/ramp_emqx.csv"

echo "=== 2/3 amqtt baseline ramp (port 1884, expect early failure) ==="
python3 ../../scripts/mqtt_broker.py --host 0.0.0.0 --port 1884 \
    --max-connections 200000 > "$RESULTS/amqtt_broker.log" 2>&1 &
AMQTT_PID=$!
sleep 3
python3 bench_ramp.py --label amqtt --port 1884 --proc-name mqtt_broker \
    --steps 100,500,1000,2000,5000,10000 --hold 20 \
    --output "$RESULTS/ramp_amqtt.csv" || true
kill $AMQTT_PID 2>/dev/null || true

echo "=== 3/3 EMQX throughput (QoS1, json payload size) ==="
python3 bench_throughput.py --label emqx --port 1883 --proc-name emqx \
    --rates 1000,5000,10000,20000,50000 --payload-size 118 --hold 30 \
    --output "$RESULTS/throughput_emqx.csv"

echo "=== suite done ==="
ls -lh "$RESULTS"
