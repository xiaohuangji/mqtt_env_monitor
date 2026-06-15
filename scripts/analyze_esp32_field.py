"""ESP32 室外长时间测试数据分析（Issue #42）。

读取监控端 --log-file 输出的接收日志，按数据类型画出全天变化曲线，
并统计到达率、数据中断和异常值。用法：

    python scripts/analyze_esp32_field.py --log logs/esp32_0615.log --node esp32hyh0615

输出：
    - logs/esp32_0615_curves.png   五类传感器全天曲线
    - 终端打印每类数据的统计（消息数、seq 连续性、到达率、最大中断、异常值）
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

# 监控端日志行：[recv <时间>] topic=... qos=.. format=.. payload={...}
LINE_RE = re.compile(r"\[recv ([\d\-T:.+]+)\].*?payload=(\{.*\})\s*$")

CN = {"temperature": "温度", "humidity": "湿度", "light": "光照",
      "smoke": "可燃气体", "mq2_gas": "可燃气体", "soil_moisture": "土壤湿度", "noise": "噪声"}
ORDER = ["temperature", "humidity", "light", "smoke", "soil_moisture"]


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def main() -> None:
    ap = argparse.ArgumentParser(description="分析 ESP32 室外测试接收日志")
    ap.add_argument("--log", required=True, help="监控端 --log-file 生成的日志路径")
    ap.add_argument("--node", default="", help="只统计该 node_id（留空则全部）")
    ap.add_argument("--out", default="", help="曲线图输出路径（默认与日志同名 _curves.png）")
    ap.add_argument("--gap", type=float, default=120.0, help="判定为中断的最小间隔秒数")
    args = ap.parse_args()

    # series[data_type] = list of (recv_dt, value, seq)
    series: dict[str, list[tuple[datetime, float, int]]] = defaultdict(list)
    bad = 0
    for line in open(args.log, encoding="utf-8", errors="replace"):
        m = LINE_RE.search(line)
        if not m:
            continue
        recv_dt = parse_iso(m.group(1))
        try:
            p = json.loads(m.group(2))
        except json.JSONDecodeError:
            bad += 1
            continue
        node = str(p.get("node_id") or p.get("n") or "")
        if args.node and node != args.node:
            continue
        dtype = str(p.get("data_type") or p.get("d") or "")
        val = p.get("value", p.get("v"))
        seq = p.get("seq", p.get("s"))
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        series[dtype].append((recv_dt, val, int(seq) if isinstance(seq, int) else -1))

    if not series:
        print("未解析到任何数据，请检查日志路径和格式。")
        return

    # ---- 统计 ----
    # 注意：seq 是节点全局递增（5 个 data_type 共用一个计数器），所以到达率按
    # “节点整体”算，单类型表格只统计消息数、最大中断和异常值。
    print("=" * 64)
    print(f"{'数据类型':<12}{'消息数':>10}{'最大中断(s)':>14}{'异常值':>10}")
    print("-" * 64)
    for dtype in [d for d in ORDER if d in series] + [d for d in series if d not in ORDER]:
        rows = sorted(series[dtype], key=lambda r: r[0])
        n = len(rows)
        gaps = [(rows[i][0] - rows[i - 1][0]).total_seconds() for i in range(1, n)]
        max_gap = f"{max(gaps):.0f}" if gaps else "-"
        anomalies = sum(1 for _, v, _ in rows if v <= -1 or (dtype == "soil_moisture" and (v < 0 or v > 100)))
        print(f"{CN.get(dtype, dtype):<12}{n:>10}{max_gap:>14}{anomalies:>10}")
    print("=" * 64)
    all_seqs = [r[2] for rows in series.values() for r in rows if r[2] >= 0]
    if all_seqs:
        span = max(all_seqs) - min(all_seqs) + 1
        uniq = len(set(all_seqs))
        print(f"节点整体到达率：{100.0 * uniq / span:.1f}%　（seq {min(all_seqs)}~{max(all_seqs)}，应收 {span} / 实收 {uniq}）")
    if bad:
        print(f"（另有 {bad} 行 payload 解析失败）")

    # 中断时段（任一类型间隔超过阈值）
    all_times = sorted(t for rows in series.values() for t, _, _ in rows)
    breaks = [(all_times[i - 1], all_times[i], (all_times[i] - all_times[i - 1]).total_seconds())
              for i in range(1, len(all_times)) if (all_times[i] - all_times[i - 1]).total_seconds() > args.gap]
    if breaks:
        print(f"\n检测到 {len(breaks)} 处数据中断（间隔 > {args.gap:.0f}s）：")
        for a, b, g in breaks[:10]:
            print(f"  {a.strftime('%H:%M:%S')} → {b.strftime('%H:%M:%S')}  中断 {g:.0f}s")
        if len(breaks) > 10:
            print(f"  ... 其余 {len(breaks) - 10} 处略")
    else:
        print(f"\n全程无超过 {args.gap:.0f}s 的数据中断。")

    # ---- 画曲线 ----
    plot_types = [d for d in ORDER if d in series]
    fig, axes = plt.subplots(len(plot_types), 1, figsize=(11, 2.4 * len(plot_types)), sharex=True)
    if len(plot_types) == 1:
        axes = [axes]
    span_txt = ""
    if all_times:
        span_txt = f"（{all_times[0].strftime('%m-%d %H:%M')} ~ {all_times[-1].strftime('%H:%M')}）"
    fig.suptitle(f"ESP32 室外长时间测试 全天数据曲线 {span_txt}", fontsize=13)
    for ax, dtype in zip(axes, plot_types):
        rows = [r for r in sorted(series[dtype], key=lambda r: r[0]) if r[1] > -1]
        xs = [r[0] for r in rows]
        ys = [r[1] for r in rows]
        ax.plot(xs, ys, linewidth=1.0, color="#0b5fa5")
        ax.set_ylabel(CN.get(dtype, dtype))
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("时间")
    fig.autofmt_xdate()
    out = args.out or (args.log.rsplit(".", 1)[0] + "_curves.png")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(out, dpi=150)
    print(f"\n曲线图已保存：{out}")


if __name__ == "__main__":
    main()
