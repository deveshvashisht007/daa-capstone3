"""Integration layer: sort -> select/pack -> route (Phases 2 and 3)."""

from __future__ import annotations

import csv
import time
from typing import Dict, List, Sequence

from .graph import Graph, dijkstra, nearest_neighbour, shortest_path, two_opt
from .knapsack import knapsack_dp, pack_boxes
from .models import DeliveryPoint, PackingPlan, Parcel, PlanResult, RoutePlan
from .sorting import sort_parcels


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_parcels(path: str) -> List[Parcel]:
    parcels: List[Parcel] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            parcels.append(
                Parcel(
                    parcel_id=row["parcel_id"].strip(),
                    destination=row["destination"].strip(),
                    weight_kg=float(row["weight_kg"]),
                    priority=int(row["priority"]),
                    deadline_min=int(row["deadline_min"]),
                    customer_tier=row.get("customer_tier", "standard").strip(),
                )
            )
    return parcels


def load_points(path: str) -> List[DeliveryPoint]:
    points: List[DeliveryPoint] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            points.append(
                DeliveryPoint(row["name"].strip(), float(row["x"]), float(row["y"]))
            )
    return points


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------
class CourierPlanner:
    """Ties every algorithm together into one delivery plan."""

    def __init__(self, graph: Graph, depot: str = "Depot") -> None:
        self.graph = graph
        self.depot = depot

    def plan(
        self,
        parcels: Sequence[Parcel],
        capacity_kg: float,
        box_capacity_kg: float = 5.0,
    ) -> PlanResult:
        result = PlanResult(
            depot=self.depot, capacity_kg=capacity_kg, box_capacity_kg=box_capacity_kg
        )

        # ---- Phase 2a: prioritise parcels (merge sort, EDF) ---------------
        t0 = time.perf_counter()
        result.sorted_parcels = sort_parcels(parcels)
        result.timings_ms["sort"] = (time.perf_counter() - t0) * 1000

        # ---- Phase 2b: optimal selection (0/1 knapsack DP) ----------------
        t0 = time.perf_counter()
        packing: PackingPlan = knapsack_dp(result.sorted_parcels, capacity_kg)
        packing.boxes = pack_boxes(packing.selected, box_capacity_kg)
        result.packing = packing
        result.timings_ms["knapsack"] = (time.perf_counter() - t0) * 1000

        # ---- Phase 3: shortest paths + TSP approximation ------------------
        t0 = time.perf_counter()
        result.route = self._build_route(packing.selected)
        result.timings_ms["route"] = (time.perf_counter() - t0) * 1000
        return result

    # -- Phase 3 internals --------------------------------------------------
    def _build_route(self, selected: Sequence[Parcel]) -> RoutePlan:
        # One stop per distinct destination, in the order the parcels were
        # prioritised (earliest deadline first) for deterministic tie-breaking.
        destinations: List[str] = []
        seen = set()
        for parcel in selected:
            if parcel.destination not in seen:
                seen.add(parcel.destination)
                destinations.append(parcel.destination)

        if not destinations:
            return RoutePlan(order=[self.depot], total_km=0.0)

        nodes = [self.depot] + destinations

        # Pairwise road distances come from Dijkstra on the full graph, so the
        # tour can use any intermediate road node, not just delivery stops.
        matrix: Dict[str, Dict[str, float]] = {
            u: dijkstra(self.graph, u)[0] for u in nodes
        }

        nn_route, nn_len = nearest_neighbour(matrix, self.depot)
        route, length = two_opt(nn_route, matrix)

        legs = [
            (route[i], route[i + 1], matrix[route[i]][route[i + 1]])
            for i in range(len(route) - 1)
        ]
        improvement = 0.0 if nn_len == 0 else (nn_len - length) / nn_len * 100
        depot_distances = {node: matrix[self.depot][node] for node in destinations}
        depot_paths = {
            node: shortest_path(self.graph, self.depot, node)[1] for node in destinations
        }
        return RoutePlan(
            order=route,
            legs=legs,
            total_km=length,
            nn_km=nn_len,
            improvement_pct=improvement,
            depot_distances=depot_distances,
            depot_paths=depot_paths,
        )


# ---------------------------------------------------------------------------
# Human-readable output (used for screenshots / output traces)
# ---------------------------------------------------------------------------
def format_plan(result: PlanResult, show_rows: int = 20) -> str:
    lines: List[str] = []
    add = lines.append
    bar = "=" * 78

    add(bar)
    add(" MINI-COURIER PLANNER - DELIVERY PLAN")
    add(bar)
    add(f" Depot              : {result.depot}")
    add(f" Van capacity       : {result.capacity_kg:.1f} kg")
    add(f" Parcels received   : {len(result.sorted_parcels)}")
    add(f" Parcels selected   : {len(result.packing.selected)}")
    add(f" Total value        : {result.packing.total_value}")
    add(f" Total weight       : {result.packing.total_weight:.2f} kg")
    add("")

    add("-" * 78)
    add(" PHASE 2a - PRIORITISED PARCELS (merge sort, earliest deadline first)")
    add("-" * 78)
    add(f" {'ID':<7} {'Destination':<12} {'Weight':>9}  {'Pri':<3} {'Deadline':>8}  {'Tier':<8} Value")
    for parcel in result.sorted_parcels[:show_rows]:
        add(" " + str(parcel))
    if len(result.sorted_parcels) > show_rows:
        add(f" ... {len(result.sorted_parcels) - show_rows} more parcels")
    add("")

    add("-" * 78)
    add(" PHASE 2b - KNAPSACK SELECTION (0/1 DP, maximise priority value)")
    add("-" * 78)
    for parcel in result.packing.selected:
        add("  [TAKE] " + str(parcel))
    for parcel in result.packing.skipped[:5]:
        add("  [SKIP] " + str(parcel))
    if len(result.packing.skipped) > 5:
        add(f"  ... {len(result.packing.skipped) - 5} more parcels skipped")
    add("")
    add(f" Box packing plan (first-fit decreasing, box limit {result.box_capacity_kg:.1f} kg):")
    for i, box in enumerate(result.packing.boxes, 1):
        load = sum(p.weight_kg for p in box)
        ids = ", ".join(p.parcel_id for p in box)
        note = "  (oversized parcel)" if load > result.box_capacity_kg + 1e-9 else ""
        add(f"   Box {i}: {load:5.2f} kg -> {ids}{note}")
    add("")

    add("-" * 78)
    add(" PHASE 3 - DELIVERY ROUTE (Dijkstra distances + nearest neighbour + 2-opt)")
    add("-" * 78)
    add("  Dijkstra shortest paths from the depot:")
    add(f"  {'Stop':<14} {'Distance':>10}   Path")
    for node in result.route.order[1:-1]:
        path = result.route.depot_paths.get(node, [node])
        add(f"  {node:<14} {result.route.depot_distances.get(node, 0.0):>8.2f} km   " + " -> ".join(path))
    add("")
    add("  Route: " + " -> ".join(result.route.order))
    add("")
    add(f"  {'Leg':<28} {'Distance (km)':>13}")
    for u, v, d in result.route.legs:
        add(f"  {u + ' -> ' + v:<28} {d:>13.2f}")
    add(f"  {'TOTAL':<28} {result.route.total_km:>13.2f}")
    add("")
    add(f"  Nearest-neighbour tour : {result.route.nn_km:.2f} km")
    add(f"  After 2-opt            : {result.route.total_km:.2f} km")
    add(f"  Improvement            : {result.route.improvement_pct:.1f}%")
    add("")

    add("-" * 78)
    add(" RUNTIME OF MAJOR STEPS")
    add("-" * 78)
    for step, ms in result.timings_ms.items():
        add(f"  {step:<12} {ms:>9.3f} ms")
    add(f"  {'TOTAL':<12} {sum(result.timings_ms.values()):>9.3f} ms")
    add(bar)
    return "\n".join(lines)
