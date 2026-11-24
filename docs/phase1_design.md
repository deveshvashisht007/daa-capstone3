# Phase 1 - Courier Problem Design and Planning

**Capstone:** Mini-Courier Planner | **Course:** Design & Analysis of Algorithms (ETCCDA302)
**Mapped COs:** CO1, CO2, CO3, CO4 | **Bloom level:** L5 (Create/Evaluate)

This document defines the problem, the data model, the algorithm pipeline and the
design rationale that the later phases implement.

---

## 1. Problem statement

A courier depot receives a list of parcels. Each parcel has a destination, a weight,
a business priority and a delivery deadline. One van with a fixed weight capacity must
make a single trip that

1. delivers the **most valuable** set of parcels (priority/deadline based value),
2. never exceeds the van capacity,
3. visits every selected destination using a **short** route, and
4. finishes fast enough to be usable in an operational setting.

The prototype must also **measure and explain** the cost of each algorithmic step.

### Formal model

Given

* `P = {p₁, p₂, …, pₙ}` - parcels, each with weight `wᵢ`, value `vᵢ`, destination `dᵢ`,
* `G = (V, E, c)` - undirected weighted graph of the city, depot `s ∈ V`,
* `C` - van capacity in kg,

choose

* `S ⊆ P` with `Σ wᵢ ≤ C` that maximises `Σ vᵢ`   (0/1 knapsack), and
* a closed tour `T = (s = t₀, t₁, …, t_k, t_{k+1} = s)` over the distinct
  destinations of `S` that minimises `Σ c(tⱼ, tⱼ₊₁)`  (TSP over the road metric).

Value is derived from business attributes:

```
value(p) = 100 × priority(p) + min(60, (600 − deadline(p)) // 10) + tier_bonus
tier_bonus: standard 0, silver 25, gold 50, platinum 80
```

so an urgent platinum parcel is worth roughly five times a relaxed standard one.

---

## 2. Data design

### 2.1 Parcel attributes

| Field | Type | Meaning | Used by |
|---|---|---|---|
| `parcel_id` | string | unique label | reporting, boxes |
| `destination` | string | node name in the graph | routing |
| `weight_kg` | float | physical weight | knapsack capacity, boxes |
| `priority` | int 1-5 | business priority | value, sorting tie-break |
| `deadline_min` | int | minutes until promised delivery | value, EDF sort |
| `customer_tier` | enum | standard/silver/gold/platinum | value |

### 2.2 Delivery points / graph format

`data/delivery_points.csv` stores `name, x, y` in kilometres. The graph is built as a
**complete undirected graph**: edge weight = Euclidean distance × 1.25 road factor
(roads are not straight). A complete graph keeps the prototype independent of map data;
the Dijkstra implementation works unchanged on a sparse road network if real edges are
supplied later.

| Node | x | y |
|---|---|---|
| Depot | 10.0 | 7.5 |
| Market | 3.0 | 12.0 |
| Station | 16.5 | 12.5 |
| Hospital | 6.0 | 3.0 |
| School | 13.0 | 2.5 |
| Mall | 18.0 | 6.0 |
| Tower-A | 2.0 | 6.0 |
| Tower-B | 9.0 | 13.5 |
| University | 14.0 | 15.0 |
| Airport | 19.0 | 16.0 |
| Industrial | 4.0 | 17.0 |
| Old-City | 11.0 | 1.0 |

### 2.3 Datasets

| File | Size | Purpose |
|---|---|---|
| `parcels_small.csv` | 10 parcels | hand-built, traceable in a viva |
| `parcels_medium.csv` | 60 parcels | realistic daily load |
| `parcels_large.csv` | 400 parcels | scaling / stress test |

All datasets are produced by `data/generate_datasets.py` with fixed seeds, so every
reported runtime and route is reproducible.

### 2.4 Assumptions

1. One van, one trip, weight is the only binding capacity (no volume constraint).
2. Every parcel in the selected set must be delivered on this trip.
3. Road distances are symmetric and non-negative → Dijkstra is valid.
4. A parcel heavier than the van capacity is simply not selectable; a parcel heavier
   than a physical box is still packed in its own oversized box (flagged in output).
5. Travel time is proportional to distance; deadlines are checked, not simulated.

---

## 3. System architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                            main.py (CLI)                             │
│        demo │ dp-table │ benchmark │ verify                          │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │                               │
        ┌───────▼────────┐              ┌───────▼────────┐
        │   planner.py   │              │ performance.py │
        │  (integration) │              │  (Phase 4)     │
        └───┬────┬───┬───┘              └───────┬────────┘
            │    │   │                          │
   ┌────────▼┐ ┌─▼─────────┐ ┌──────────▼──┐   │
   │sorting  │ │knapsack   │ │graph        │◄──┘
   │Phase 2a │ │Phase 2b   │ │Phase 3      │
   └─────────┘ └───────────┘ └─────────────┘
        │            │              │
        └────────────┴──────┬───────┘
                            ▼
                    models.py (Parcel, plans)
```

| Module | Responsibility | Key functions |
|---|---|---|
| `models.py` | plain data objects, derived value | `Parcel.priority_score`, `PlanResult` |
| `sorting.py` | five comparison sorts + EDF wrapper | `merge_sort`, `sort_parcels` |
| `knapsack.py` | exact DP, reference brute force, FFD | `knapsack_dp`, `pack_boxes` |
| `graph.py` | graph, Dijkstra, NN TSP, 2-opt | `dijkstra`, `nearest_neighbour`, `two_opt` |
| `planner.py` | pipeline + readable report | `CourierPlanner.plan`, `format_plan` |
| `performance.py` | timing harness, CSV, charts | `run_all`, `benchmark_*` |
| `verify.py` | cross-checks against references | `run_checks` |

---

## 4. Algorithm selection and justification

| Decision | Chosen | Rejected alternative | Reason |
|---|---|---|---|
| Parcel ordering | **Merge sort** | Quick sort, heap sort | Stable (equal deadlines keep receipt order) and O(n log n) worst case. A bad pivot in quick sort could delay urgent parcels. |
| Load selection | **0/1 knapsack DP** | Greedy value/weight, fractional knapsack | Parcels are indivisible; greedy can be arbitrarily far from optimal. DP is exact and produces a table that can be demonstrated. |
| Box packing | **First-Fit Decreasing** | Exact bin packing (ILP) | Bin packing is NP-hard; FFD is O(n log n) and guarantees ≤ 11/9·OPT + 6/9. |
| Shortest paths | **Dijkstra (binary heap)** | BFS, Bellman-Ford, Floyd-Warshall | Weights are non-negative and vary; Dijkstra is O((V+E) log V) and one run per node builds the tour matrix cheaper than O(V³) Floyd-Warshall at this size. |
| Route | **Nearest neighbour + 2-opt** | Exact TSP (Held-Karp / permutations) | Exact TSP is O(n²2ⁿ) / O(n!). The heuristic is O(n²) per improvement pass and typically within 2-5% of optimal. |
| Correctness evidence | DP vs brute force, all sorts vs `sorted()` | - | Independent references catch off-by-one and stability bugs. |

---

## 5. Detailed design (pseudocode)

### 5.1 Merge sort with EDF key

```
MERGE-SORT(A):
    if |A| <= 1: return A
    split A into L, R at mid
    return MERGE(MERGE-SORT(L), MERGE-SORT(R))

MERGE(L, R):
    while both non-empty: append the smaller head (<= keeps stability)
    append the remainder
```

Key: `(deadline_min, -priority, weight_kg)` → earliest deadline first, then the most
important parcel, then the lighter one.

### 5.2 0/1 knapsack DP

```
KNAPSACK(items, C):                       # C in 10 g units
    dp[0..n][0..C] = 0
    for i = 1..n:
        for w = 0..C:
            dp[i][w] = dp[i-1][w]                       # skip item i
            if weight[i] <= w:
                dp[i][w] = max(dp[i][w], dp[i-1][w-weight[i]] + value[i])
    backtrack from dp[n][C] to recover the chosen items
```

Space-optimised variant uses one row and iterates `w` downwards (used in benchmarks).

### 5.3 Dijkstra

```
DIJKSTRA(G, s):
    dist[*] = ∞; dist[s] = 0; heap = [(0, s)]
    while heap:
        (d, u) = pop-min
        if visited[u]: continue
        for (v, w) in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w; prev[v] = u; push (dist[v], v)
```

The planner runs it once from the depot (to show per-stop distances) and once per
selected stop to build the tour's distance matrix.

### 5.4 Nearest-neighbour TSP + 2-opt

```
NN(start):
    current = start; tour = [start]
    while unvisited: pick closest unvisited node, append it
    append start; return tour

2-OPT(tour):
    repeat until no improvement:
        for i < j:
            delta = c(t[i-1],t[j]) + c(t[i],t[j+1]) - c(t[i-1],t[i]) - c(t[j],t[j+1])
            if delta < 0: reverse tour[i..j]
```

Only the O(1) delta is computed per candidate, so a pass is O(n²).

### 5.5 Integrated route-planning logic

1. Sort all parcels (Phase 2a) — this order is kept everywhere for determinism.
2. Run the knapsack on the sorted list (Phase 2b) → selected parcels.
3. Derive the **distinct destinations** of selected parcels (one stop per customer).
4. Build a distance matrix over `{depot} ∪ destinations` with Dijkstra.
5. Nearest-neighbour tour from the depot, then 2-opt improvement.
6. Report legs, total km, NN-vs-2-opt improvement, and per-step timings.

Packing the boxes (FFD) is independent of routing and can be done by warehouse staff
while the route is computed.

---

## 6. Complexity analysis

| Step | Time | Space | Notes |
|---|---|---|---|
| Merge sort | Θ(n log n) | Θ(n) | stable, worst-case guarantee |
| Quick sort | Θ(n log n) avg, Θ(n²) worst | Θ(log n) stack | median-of-three pivot |
| Heap sort | Θ(n log n) | Θ(1) | in-place, not stable |
| 0/1 knapsack (2-D) | Θ(n·W) | Θ(n·W) | W = capacity in 10 g units |
| 0/1 knapsack (1-D) | Θ(n·W) | Θ(W) | value only |
| Brute force reference | Θ(2ⁿ·n) | Θ(n) | verification only |
| FFD packing | O(n log n + n·b) | O(n) | b = boxes |
| Dijkstra (one source) | O((V+E) log V) | O(V) | complete graph: E = V(V−1)/2 |
| Distance matrix | O(V·(V+E) log V) | O(V²) | V = stops + 1 |
| NN tour | O(V²) | O(V) | greedy |
| 2-opt | O(V²) per pass | O(V) | at most `max_passes` passes |
| Whole pipeline | O(n log n + n·W + V² log V) | O(n·W + V²) | dominated by knapsack |

---

## 7. Validation plan

| Check | Reference | Where |
|---|---|---|
| All five sorts produce the same order as `sorted()` | Python Timsort | `verify.py` check 1 |
| Merge sort is stable for equal keys | definition | check 2 |
| DP value equals brute-force optimum (3 instances) | exhaustive subsets | check 3 |
| 1-D DP equals 2-D DP; weight ≤ capacity | DP invariants | checks 4-5 |
| Dijkstra distance matches hand-computed graph | manual trace | check 6 |
| TSP tour is a valid closed tour; 2-opt never worsens it | tour definition | checks 7-8 |
| Integrated plan: capacity respected, every selected destination visited | plan invariants | `tests/test_algorithms.py` |

Plus 11 unit tests covering empty input, zero capacity, oversized parcels, disconnected
graphs, single-stop tours and stability.

---

## 8. Risks, limitations and planned improvements

| Risk / limitation | Mitigation / future work |
|---|---|
| DP is pseudo-polynomial: capacity in 10 g units makes `W` large | Scale capacity to 100 g or 1 kg buckets, or use branch-and-bound with a fractional-knapsack bound. |
| One trip only | Extend to multiple vans / trips (bin packing over trips, then VRP). |
| Deadlines are not simulated in time | Add travel-time windows and penalty for late arrival. |
| NN + 2-opt is not optimal | Held-Karp DP for ≤ 15 stops; Or-opt/3-opt or OR-Tools for larger instances. |
| Complete graph ignores one-way streets | Load a real sparse road graph; Dijkstra code is unchanged. |
| Single-threaded | Cache the distance matrix and parallelise per-source Dijkstra. |
