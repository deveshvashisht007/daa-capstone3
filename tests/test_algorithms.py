"""Unit tests for the Mini-Courier Planner.

Run with:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from courier.graph import Graph, dijkstra, nearest_neighbour, shortest_path, two_opt
from courier.knapsack import knapsack_bruteforce, knapsack_dp, knapsack_value_only, pack_boxes
from courier.models import DeliveryPoint, Parcel
from courier.planner import CourierPlanner, load_parcels, load_points
from courier.sorting import merge_sort, sort_parcels
from courier.verify import run_checks


class TestVerifiedAlgorithms(unittest.TestCase):
    def test_all_cross_checks(self) -> None:
        for name, ok, detail in run_checks():
            with self.subTest(check=name):
                self.assertTrue(ok, f"{name} failed: {detail}")


class TestEdgeCases(unittest.TestCase):
    def test_empty_parcel_list(self) -> None:
        plan = knapsack_dp([], 10.0)
        self.assertEqual(plan.total_value, 0)
        self.assertEqual(plan.selected, [])

    def test_zero_capacity(self) -> None:
        parcels = [Parcel("A", "X", 1.0, 5, 10)]
        self.assertEqual(knapsack_dp(parcels, 0.0).selected, [])

    def test_parcel_heavier_than_capacity_is_skipped(self) -> None:
        parcels = [Parcel("A", "X", 9.0, 5, 10), Parcel("B", "Y", 1.0, 1, 10)]
        plan = knapsack_dp(parcels, 5.0)
        self.assertEqual([p.parcel_id for p in plan.selected], ["B"])

    def test_boxes_never_exceed_capacity_for_normal_parcels(self) -> None:
        parcels = [Parcel(f"P{i}", "X", 1.0, 3, 60) for i in range(10)]
        boxes = pack_boxes(parcels, box_capacity_kg=4.0)
        self.assertEqual(len(boxes), 3)  # 4 + 4 + 2
        for box in boxes:
            self.assertLessEqual(sum(p.weight_kg for p in box), 4.0 + 1e-9)

    def test_disconnected_graph_returns_infinity(self) -> None:
        g = Graph()
        g.add_edge("A", "B", 1.0)
        g.add_node("Z")
        distance, path = shortest_path(g, "A", "Z")
        self.assertEqual(distance, float("inf"))
        self.assertEqual(path, [])

    def test_single_stop_tour(self) -> None:
        g = Graph()
        g.add_edge("Depot", "A", 2.0)
        matrix = {u: dijkstra(g, u)[0] for u in g.nodes()}
        route, length = nearest_neighbour(matrix, "Depot")
        self.assertEqual(route, ["Depot", "A", "Depot"])
        self.assertAlmostEqual(length, 4.0)
        improved, improved_len = two_opt(route, matrix)
        self.assertAlmostEqual(improved_len, 4.0)

    def test_sort_is_stable_for_identical_keys(self) -> None:
        parcels = [Parcel(f"P{i}", "X", 1.0, 3, 100) for i in range(20)]
        self.assertEqual([p.parcel_id for p in sort_parcels(parcels)],
                         [f"P{i}" for i in range(20)])


class TestIntegratedPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.root = root
        points = load_points(os.path.join(root, "data", "delivery_points.csv"))
        cls.graph = Graph.from_points(points)
        cls.parcels = load_parcels(os.path.join(root, "data", "parcels_small.csv"))

    def test_plan_respects_capacity_and_route(self) -> None:
        planner = CourierPlanner(self.graph)
        result = planner.plan(self.parcels, capacity_kg=20.0, box_capacity_kg=5.0)

        self.assertLessEqual(result.packing.total_weight, 20.0 + 1e-9)
        self.assertEqual(result.route.order[0], "Depot")
        self.assertEqual(result.route.order[-1], "Depot")

        stops = set(result.route.order[1:-1])
        for parcel in result.packing.selected:
            self.assertIn(parcel.destination, stops)

        self.assertLessEqual(result.route.total_km, result.route.nn_km + 1e-9)

    def test_plan_uses_all_parcels_when_capacity_is_large(self) -> None:
        planner = CourierPlanner(self.graph)
        result = planner.plan(self.parcels, capacity_kg=10_000.0)
        self.assertEqual(len(result.packing.selected), len(self.parcels))
        self.assertEqual(result.packing.skipped, [])

    def test_dp_value_matches_space_optimised_variant(self) -> None:
        planner = CourierPlanner(self.graph)
        result = planner.plan(self.parcels, capacity_kg=20.0)
        self.assertEqual(
            result.packing.total_value,
            knapsack_value_only(result.sorted_parcels, 20.0),
        )
        self.assertEqual(
            result.packing.total_value,
            knapsack_bruteforce(result.sorted_parcels, 20.0),
        )


if __name__ == "__main__":
    unittest.main()
