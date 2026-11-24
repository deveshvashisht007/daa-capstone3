"""Correctness checks used by `python main.py verify` and the unit tests."""

from __future__ import annotations

import random
from typing import List, Tuple

from .graph import Graph, dijkstra, nearest_neighbour, shortest_path, tour_length, two_opt
from .knapsack import knapsack_bruteforce, knapsack_dp, knapsack_value_only
from .models import DeliveryPoint, Parcel
from .sorting import (
    heap_sort,
    insertion_sort,
    merge_sort,
    quick_sort,
    sort_parcels,
    timsort,
)


def _random_parcels(n: int, seed: int = 7) -> List[Parcel]:
    rng = random.Random(seed)
    return [
        Parcel(
            parcel_id=f"P{i:03d}",
            destination=rng.choice(["A", "B", "C", "D", "E"]),
            weight_kg=round(rng.uniform(0.5, 5.0), 1),
            priority=rng.randint(1, 5),
            deadline_min=rng.randint(30, 600),
        )
        for i in range(n)
    ]


def run_checks() -> List[Tuple[str, bool, str]]:
    """Return a list of (check name, passed, detail)."""
    checks: List[Tuple[str, bool, str]] = []

    # 1. every sort agrees with Python's sorted() -------------------------
    data = _random_parcels(120, seed=11)
    expected = [p.parcel_id for p in sorted(data, key=lambda p: p.sort_key)]
    for name, fn in (
        ("Insertion Sort", insertion_sort),
        ("Merge Sort", merge_sort),
        ("Quick Sort", quick_sort),
        ("Heap Sort", heap_sort),
        ("Timsort", timsort),
    ):
        got = [p.parcel_id for p in fn(data, key=lambda p: p.sort_key)]
        checks.append((f"{name} matches sorted()", got == expected, f"n={len(data)}"))

    # 2. merge sort is stable ---------------------------------------------
    tied = [
        Parcel("X1", "A", 1.0, 3, 100),
        Parcel("X2", "A", 1.0, 3, 100),
        Parcel("X3", "A", 1.0, 3, 100),
    ]
    stable = [p.parcel_id for p in sort_parcels(tied)] == ["X1", "X2", "X3"]
    checks.append(("Merge sort keeps input order for equal keys", stable, "stability"))

    # 3. DP knapsack equals brute force -----------------------------------
    for n, cap in ((10, 12.0), (14, 18.0), (16, 9.5)):
        parcels = _random_parcels(n, seed=n)
        dp_value = knapsack_dp(parcels, cap).total_value
        ref = knapsack_bruteforce(parcels, cap)
        checks.append(
            (f"Knapsack DP == brute force (n={n}, cap={cap} kg)", dp_value == ref, f"{dp_value} vs {ref}")
        )

    # 4. space-optimised DP agrees with full table ------------------------
    parcels = _random_parcels(30, seed=3)
    full = knapsack_dp(parcels, 15.0)
    compact = knapsack_value_only(parcels, 15.0)
    checks.append(("1-D DP value == 2-D DP value", full.total_value == compact, f"{compact}"))
    checks.append(
        (
            "Selected weight respects capacity",
            full.total_weight <= 15.0 + 1e-9,
            f"{full.total_weight:.2f} <= 15.0 kg",
        )
    )

    # 5. Dijkstra matches a hand-computed path ----------------------------
    g = Graph()
    for u, v, w in [
        ("Depot", "A", 4), ("Depot", "B", 1), ("B", "A", 2),
        ("A", "C", 5), ("B", "C", 8), ("C", "D", 2), ("A", "D", 11),
    ]:
        g.add_edge(u, v, w)
    d, path = shortest_path(g, "Depot", "D")
    checks.append(("Dijkstra finds Depot->D = 10 via B,A,C", abs(d - 10) < 1e-9, f"{path} = {d}"))

    # 6. TSP tour is valid and 2-opt never makes it longer ----------------
    points = [
        DeliveryPoint("Depot", 0, 0), DeliveryPoint("A", 3, 1),
        DeliveryPoint("B", 5, 4), DeliveryPoint("C", 1, 5), DeliveryPoint("D", 6, 6),
    ]
    g2 = Graph.from_points(points)
    matrix = {u: dijkstra(g2, u)[0] for u in g2.nodes()}
    route, nn_len = nearest_neighbour(matrix, "Depot")
    improved, new_len = two_opt(route, matrix)
    checks.append(
        (
            "TSP tour visits every stop exactly once",
            len(route) == len(points) + 1 and route[0] == route[-1] == "Depot",
            " -> ".join(route),
        )
    )
    checks.append(("2-opt length <= NN length", new_len <= nn_len + 1e-9, f"{nn_len:.2f} -> {new_len:.2f} km"))
    checks.append(("Tour length recomputation is consistent", abs(tour_length(improved, matrix) - new_len) < 1e-6, "delta"))
    return checks
