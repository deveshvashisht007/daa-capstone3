"""Graph construction, Dijkstra shortest paths and TSP approximation (Phase 3).

The delivery network is modelled as a weighted undirected graph.  Edge weights
are road distances in kilometres (straight-line distance x a small road
factor).  Dijkstra answers "how far is each customer from the depot?", while
the nearest-neighbour heuristic + 2-opt builds one efficient delivery tour.
"""

from __future__ import annotations

import heapq
import math
from typing import Dict, Iterable, List, Sequence, Tuple

from .models import DeliveryPoint

INF = float("inf")


class Graph:
    """Adjacency-list weighted graph (undirected by default)."""

    def __init__(self) -> None:
        self.adj: Dict[str, List[Tuple[str, float]]] = {}

    # -- construction -------------------------------------------------------
    def add_node(self, name: str) -> None:
        self.adj.setdefault(name, [])

    def add_edge(self, u: str, v: str, weight: float, directed: bool = False) -> None:
        self.add_node(u)
        self.add_node(v)
        self.adj[u].append((v, weight))
        if not directed:
            self.adj[v].append((u, weight))

    @classmethod
    def from_points(cls, points: Iterable[DeliveryPoint], road_factor: float = 1.25) -> "Graph":
        """Build a complete graph from 2-D coordinates.

        A real road network is sparse, but for this prototype every pair of
        points is connected and the straight-line distance is multiplied by a
        road factor (roads are not perfectly straight).
        """
        points = list(points)
        graph = cls()
        for p in points:
            graph.add_node(p.name)
        for i, a in enumerate(points):
            for b in points[i + 1 :]:
                distance = math.hypot(a.x - b.x, a.y - b.y) * road_factor
                graph.add_edge(a.name, b.name, round(distance, 3))
        return graph

    # -- queries ------------------------------------------------------------
    def nodes(self) -> List[str]:
        return list(self.adj.keys())

    def neighbours(self, node: str) -> List[Tuple[str, float]]:
        return self.adj.get(node, [])

    def edge_count(self) -> int:
        return sum(len(v) for v in self.adj.values()) // 2

    def __len__(self) -> int:
        return len(self.adj)


# ---------------------------------------------------------------------------
# Dijkstra - O((V + E) log V) with a binary heap
# ---------------------------------------------------------------------------
def dijkstra(graph: Graph, source: str) -> Tuple[Dict[str, float], Dict[str, str]]:
    """Return (distances, predecessors) from `source` to every node."""
    dist: Dict[str, float] = {node: INF for node in graph.nodes()}
    prev: Dict[str, str] = {}
    dist[source] = 0.0
    heap: List[Tuple[float, str]] = [(0.0, source)]
    visited = set()

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        for v, w in graph.neighbours(u):
            if d + w < dist[v]:
                dist[v] = d + w
                prev[v] = u
                heapq.heappush(heap, (dist[v], v))
    return dist, prev


def shortest_path(graph: Graph, source: str, target: str) -> Tuple[float, List[str]]:
    """Return (distance, node sequence) for one source-target pair."""
    dist, prev = dijkstra(graph, source)
    if dist.get(target, INF) == INF:
        return INF, []
    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    path.reverse()
    return dist[target], path


def distance_matrix(graph: Graph, nodes: Sequence[str] | None = None) -> Dict[str, Dict[str, float]]:
    """All-pairs shortest paths, computed with one Dijkstra run per node."""
    nodes = list(nodes) if nodes is not None else graph.nodes()
    return {u: dijkstra(graph, u)[0] for u in nodes}


# ---------------------------------------------------------------------------
# Nearest-neighbour TSP approximation - O(V^2)
# ---------------------------------------------------------------------------
def nearest_neighbour(matrix: Dict[str, Dict[str, float]], start: str) -> Tuple[List[str], float]:
    """Greedy tour: always visit the closest unvisited customer."""
    unvisited = set(matrix.keys()) - {start}
    route = [start]
    total = 0.0
    current = start

    while unvisited:
        nxt = min(unvisited, key=lambda node: matrix[current][node])
        total += matrix[current][nxt]
        route.append(nxt)
        unvisited.remove(nxt)
        current = nxt

    total += matrix[current][start]   # return to the depot
    route.append(start)
    return route, total


def tour_length(route: Sequence[str], matrix: Dict[str, Dict[str, float]]) -> float:
    return sum(matrix[route[i]][route[i + 1]] for i in range(len(route) - 1))


# ---------------------------------------------------------------------------
# 2-opt local search - improves the nearest-neighbour tour
# ---------------------------------------------------------------------------
def two_opt(
    route: Sequence[str], matrix: Dict[str, Dict[str, float]], max_passes: int = 50
) -> Tuple[List[str], float]:
    """Reverse segments while that shortens the closed tour.

    Each pass is O(n^2); the tour only gets better, so the result is always at
    least as good as the input route.
    """
    best = list(route)
    best_len = tour_length(best, matrix)
    n = len(best)

    for _ in range(max_passes):
        improved = False
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                # delta of reversing best[i:j+1] without rebuilding the tour
                a, b = best[i - 1], best[i]
                c, d = best[j], best[j + 1]
                delta = matrix[a][c] + matrix[b][d] - matrix[a][b] - matrix[c][d]
                if delta < -1e-9:
                    best[i : j + 1] = reversed(best[i : j + 1])
                    best_len += delta
                    improved = True
        if not improved:
            break
    return best, best_len
