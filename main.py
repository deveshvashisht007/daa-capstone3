"""Command-line entry point for the Mini-Courier Planner.

Examples
--------
python main.py demo --data data/parcels_small.csv --capacity 20
python main.py dp-table --data data/parcels_small.csv --capacity 12
python main.py benchmark
python main.py verify
"""

from __future__ import annotations

import argparse
import os
import sys

from courier.graph import Graph
from courier.knapsack import dp_table_snapshot
from courier.performance import run_all
from courier.planner import CourierPlanner, format_plan, load_parcels, load_points
from courier.sorting import sort_parcels
from courier.verify import run_checks

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_POINTS = os.path.join(BASE_DIR, "data", "delivery_points.csv")


def _write(text: str, out: str | None) -> None:
    print(text)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"\n[saved] {out}")


def cmd_demo(args: argparse.Namespace) -> None:
    points = load_points(args.points)
    graph = Graph.from_points(points)
    parcels = load_parcels(args.data)
    planner = CourierPlanner(graph, depot=args.depot)
    result = planner.plan(parcels, capacity_kg=args.capacity, box_capacity_kg=args.box)
    _write(format_plan(result, show_rows=args.rows), args.out)


def cmd_dp_table(args: argparse.Namespace) -> None:
    parcels = sort_parcels(load_parcels(args.data))[: args.items]
    table, capacities = dp_table_snapshot(parcels, args.capacity, step_kg=1)
    width = 6
    lines = []
    lines.append("=" * (26 + width * len(capacities)))
    lines.append(f" 0/1 KNAPSACK DP TABLE  (capacity 0..{capacities[-1]} kg, columns sampled every 1 kg)")
    lines.append("=" * (26 + width * len(capacities)))
    header = f"{'items considered':<18}{'w(kg)':>7}{'v':>5} |" + "".join(
        f"{c:>{width}}" for c in capacities
    )
    lines.append(header)
    lines.append("-" * len(header))
    lines.append(f"{'(none)':<18}{'-':>7}{'-':>5} |" + "".join(f"{v:>{width}}" for v in table[0]))
    for i, parcel in enumerate(parcels, start=1):
        lines.append(
            f"{parcel.parcel_id:<18}{parcel.weight_kg:>7.1f}{parcel.priority_score:>5} |"
            + "".join(f"{v:>{width}}" for v in table[i])
        )
    lines.append("")
    lines.append(f"Optimal value at capacity {capacities[-1]} kg = {table[-1][-1]}")
    lines.append("Reading: row i = first i parcels, column c = capacity c kg.")
    lines.append("Each cell is max(value of previous row, value of parcel i + cell at c-w_i).")
    _write("\n".join(lines), args.out)


def cmd_benchmark(args: argparse.Namespace) -> None:
    run_all(data_dir=args.data_dir, out_dir=args.out_dir, chart_dir=args.chart_dir)


def cmd_verify(args: argparse.Namespace) -> None:
    checks = run_checks()
    lines = ["=" * 78, " CORRECTNESS VERIFICATION", "=" * 78]
    passed = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        passed += ok
        lines.append(f" [{status}] {name:<52} {detail}")
    lines.append("-" * 78)
    lines.append(f" {passed}/{len(checks)} checks passed")
    lines.append("=" * 78)
    _write("\n".join(lines), args.out)
    if passed != len(checks):
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mini-Courier Planner - DAA Capstone (sorting + knapsack + Dijkstra + TSP)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="build and print a complete delivery plan")
    demo.add_argument("--data", default=os.path.join(BASE_DIR, "data", "parcels_small.csv"))
    demo.add_argument("--points", default=DEFAULT_POINTS)
    demo.add_argument("--capacity", type=float, default=20.0, help="van capacity in kg")
    demo.add_argument("--box", type=float, default=5.0, help="physical box capacity in kg")
    demo.add_argument("--depot", default="Depot")
    demo.add_argument("--rows", type=int, default=20, help="parcels to show in the sorted list")
    demo.add_argument("--out", default=None, help="also save the output trace to this file")
    demo.set_defaults(func=cmd_demo)

    table = sub.add_parser("dp-table", help="print the knapsack DP table (evidence)")
    table.add_argument("--data", default=os.path.join(BASE_DIR, "data", "parcels_small.csv"))
    table.add_argument("--capacity", type=float, default=12.0)
    table.add_argument("--items", type=int, default=10)
    table.add_argument("--out", default=None)
    table.set_defaults(func=cmd_dp_table)

    bench = sub.add_parser("benchmark", help="run Phase 4 performance tests and draw charts")
    bench.add_argument("--data-dir", default=os.path.join(BASE_DIR, "data"))
    bench.add_argument("--out-dir", default=os.path.join(BASE_DIR, "docs"))
    bench.add_argument("--chart-dir", default=os.path.join(BASE_DIR, "charts"))
    bench.set_defaults(func=cmd_benchmark)

    verify = sub.add_parser("verify", help="run algorithmic correctness checks")
    verify.add_argument("--out", default=None)
    verify.set_defaults(func=cmd_verify)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
