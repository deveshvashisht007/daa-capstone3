"""Phase 4 - runtime benchmarking and chart generation.

Measures how every major algorithmic component scales and writes:
  * docs/runtime_results.csv     - raw numbers
  * charts/runtime_comparison.png - sorting / knapsack / Dijkstra / TSP scaling
  * charts/phase_breakdown.png    - integrated planner step times per dataset
"""

from __future__ import annotations

import csv
import os
import random
import statistics
import time
from typing import Dict, List, Sequence

from .graph import Graph, dijkstra, nearest_neighbour, two_opt
from .knapsack import knapsack_bruteforce, knapsack_dp
from .models import DeliveryPoint, Parcel
from .planner import CourierPlanner, load_parcels, load_points
from .sorting import SORT_ALGORITHMS


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------
def time_ms(fn, repeats: int = 3) -> float:
    """Return the best-of-`repeats` runtime in milliseconds."""
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return min(samples)


def _random_parcels(n: int, seed: int = 42) -> List[Parcel]:
    rng = random.Random(seed)
    return [
        Parcel(
            parcel_id=f"P{i:04d}",
            destination=rng.choice(["A", "B", "C", "D", "E", "F"]),
            weight_kg=round(rng.uniform(0.3, 6.0), 1),
            priority=rng.randint(1, 5),
            deadline_min=rng.randint(30, 600),
        )
        for i in range(n)
    ]


def _random_graph(n: int, seed: int = 42) -> Graph:
    rng = random.Random(seed)
    points = [DeliveryPoint("Depot", 0.0, 0.0)]
    for i in range(1, n):
        points.append(DeliveryPoint(f"N{i}", rng.uniform(0, 30), rng.uniform(0, 30)))
    return Graph.from_points(points)


# ---------------------------------------------------------------------------
# Individual benchmarks
# ---------------------------------------------------------------------------
def benchmark_sorting(sizes: Sequence[int] = (50, 100, 200, 400, 800, 1600)) -> Dict[str, Dict[int, float]]:
    results: Dict[str, Dict[int, float]] = {name: {} for name in SORT_ALGORITHMS}
    for n in sizes:
        parcels = _random_parcels(n)
        key = lambda p: p.sort_key
        for name, algorithm in SORT_ALGORITHMS.items():
            # Insertion sort is O(n^2); stop it at 800 so the run stays quick.
            if name == "Insertion Sort" and n > 800:
                continue
            results[name][n] = time_ms(lambda a=algorithm: a(parcels, key=key))
    return results


def benchmark_knapsack(sizes: Sequence[int] = (4, 8, 12, 16, 18), capacity: float = 20.0) -> Dict[str, Dict[int, float]]:
    results: Dict[str, Dict[int, float]] = {"DP (O(nW))": {}, "Brute force (O(2^n))": {}}
    for n in sizes:
        parcels = _random_parcels(n, seed=n)
        results["DP (O(nW))"][n] = time_ms(lambda p=parcels: knapsack_dp(p, capacity))
        results["Brute force (O(2^n))"][n] = time_ms(
            lambda p=parcels: knapsack_bruteforce(p, capacity), repeats=1
        )
    return results


def benchmark_dijkstra(sizes: Sequence[int] = (10, 20, 40, 80, 160, 320)) -> Dict[str, Dict[int, float]]:
    results: Dict[str, Dict[int, float]] = {"Dijkstra (one source)": {}}
    for n in sizes:
        graph = _random_graph(n)
        results["Dijkstra (one source)"][n] = time_ms(lambda g=graph: dijkstra(g, "Depot"))
    return results


def benchmark_tsp(sizes: Sequence[int] = (5, 8, 12, 16, 20, 25, 30)) -> Dict[str, Dict[int, float]]:
    results: Dict[str, Dict[int, float]] = {"NN + 2-opt": {}}
    for n in sizes:
        graph = _random_graph(n + 1)
        nodes = graph.nodes()
        matrix = {u: dijkstra(graph, u)[0] for u in nodes}

        def run(m=matrix, start="Depot"):
            route, _ = nearest_neighbour(m, start)
            two_opt(route, m)

        results["NN + 2-opt"][n] = time_ms(run)
    return results


# ---------------------------------------------------------------------------
# Integrated planner benchmark (small / medium / large datasets)
# ---------------------------------------------------------------------------
def benchmark_planner(data_dir: str = "data") -> List[dict]:
    rows: List[dict] = []
    points = load_points(os.path.join(data_dir, "delivery_points.csv"))
    graph = Graph.from_points(points)
    planner = CourierPlanner(graph, depot="Depot")

    for label, filename, capacity in (
        ("small (10 parcels)", "parcels_small.csv", 20.0),
        ("medium (60 parcels)", "parcels_medium.csv", 40.0),
        ("large (400 parcels)", "parcels_large.csv", 80.0),
    ):
        path = os.path.join(data_dir, filename)
        if not os.path.exists(path):
            continue
        parcels = load_parcels(path)
        t0 = time.perf_counter()
        result = planner.plan(parcels, capacity_kg=capacity)
        total = (time.perf_counter() - t0) * 1000
        rows.append(
            {
                "dataset": label,
                "parcels": len(parcels),
                "selected": len(result.packing.selected),
                "stops": len(result.route.order) - 1,
                "sort_ms": result.timings_ms["sort"],
                "knapsack_ms": result.timings_ms["knapsack"],
                "route_ms": result.timings_ms["route"],
                "total_ms": total,
                "route_km": result.route.total_km,
                "value": result.packing.total_value,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Reporting + charts
# ---------------------------------------------------------------------------
def save_csv(sorting, knapsack, dijkstra_res, tsp, planner_rows, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["component", "variant", "n", "runtime_ms"])
        for component, table in (
            ("sorting", sorting),
            ("knapsack", knapsack),
            ("dijkstra", dijkstra_res),
            ("tsp", tsp),
        ):
            for variant, series in table.items():
                for n, ms in series.items():
                    writer.writerow([component, variant, n, f"{ms:.4f}"])
        writer.writerow([])
        writer.writerow(["dataset", "parcels", "selected", "stops", "sort_ms", "knapsack_ms", "route_ms", "total_ms", "route_km", "value"])
        for row in planner_rows:
            writer.writerow(
                [
                    row["dataset"], row["parcels"], row["selected"], row["stops"],
                    f"{row['sort_ms']:.3f}", f"{row['knapsack_ms']:.3f}",
                    f"{row['route_ms']:.3f}", f"{row['total_ms']:.3f}",
                    f"{row['route_km']:.2f}", row["value"],
                ]
            )


def _plot_scaling(ax, title, xlabel, ylabel, table, log_y=True):
    for variant, series in table.items():
        xs = sorted(series)
        ys = [series[x] for x in xs]
        ax.plot(xs, ys, marker="o", label=variant)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if log_y:
        ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)


def make_charts(sorting, knapsack, dijkstra_res, tsp, planner_rows, chart_dir: str = "charts") -> List[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(chart_dir, exist_ok=True)
    written: List[str] = []

    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
    _plot_scaling(axes[0, 0], "Sorting: runtime vs number of parcels", "parcels (n)", "time (ms)", sorting)
    _plot_scaling(axes[0, 1], "Knapsack: DP vs brute force", "parcels (n)", "time (ms)", knapsack)
    _plot_scaling(axes[1, 0], "Dijkstra: runtime vs graph size", "nodes (V)", "time (ms)", dijkstra_res)
    _plot_scaling(axes[1, 1], "TSP approximation: runtime vs stops", "stops", "time (ms)", tsp)
    fig.suptitle("Mini-Courier Planner - Phase 4 runtime comparison", fontweight="bold")
    fig.tight_layout()
    path = os.path.join(chart_dir, "runtime_comparison.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    written.append(path)

    if planner_rows:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        labels = [r["dataset"] for r in planner_rows]
        steps = [("sort_ms", "sort"), ("knapsack_ms", "knapsack"), ("route_ms", "route")]
        width = 0.26
        positions = range(len(labels))
        for offset, (step, name) in zip((-width, 0.0, width), steps):
            values = [max(r[step], 1e-4) for r in planner_rows]
            bars = ax.bar([p + offset for p in positions], values, width, label=name)
            for bar, value in zip(bars, values):
                ax.annotate(
                    f"{value:.2f}",
                    (bar.get_x() + bar.get_width() / 2, value),
                    textcoords="offset points",
                    xytext=(0, 3),
                    ha="center",
                    fontsize=7,
                )
        ax.set_yscale("log")
        ax.set_xticks(list(positions))
        ax.set_xticklabels(labels)
        ax.set_ylabel("time (ms, log scale)")
        ax.set_title("Integrated planner: runtime of major steps")
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        path = os.path.join(chart_dir, "phase_breakdown.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        written.append(path)
    return written


def run_all(data_dir: str = "data", out_dir: str = "docs", chart_dir: str = "charts") -> dict:
    print("Benchmarking sorting algorithms ...")
    sorting = benchmark_sorting()
    print("Benchmarking knapsack DP vs brute force ...")
    knapsack = benchmark_knapsack()
    print("Benchmarking Dijkstra ...")
    dijkstra_res = benchmark_dijkstra()
    print("Benchmarking TSP approximation ...")
    tsp = benchmark_tsp()
    print("Benchmarking integrated planner ...")
    planner_rows = benchmark_planner(data_dir)

    csv_path = os.path.join(out_dir, "runtime_results.csv")
    save_csv(sorting, knapsack, dijkstra_res, tsp, planner_rows, csv_path)
    charts = make_charts(sorting, knapsack, dijkstra_res, tsp, planner_rows, chart_dir)
    print(f"Raw results -> {csv_path}")
    for chart in charts:
        print(f"Chart       -> {chart}")
    return {
        "sorting": sorting,
        "knapsack": knapsack,
        "dijkstra": dijkstra_res,
        "tsp": tsp,
        "planner": planner_rows,
    }
