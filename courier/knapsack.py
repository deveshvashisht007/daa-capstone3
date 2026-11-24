"""0/1 knapsack dynamic programming (Phase 2 - optimal parcel selection).

The courier can carry at most `capacity_kg` on one trip.  Every parcel has a
weight and a business value (priority score).  Choosing the subset with the
maximum total value is the classic 0/1 knapsack problem.

Weights are converted to integer centi-kilograms so the DP uses exact integer
capacities (floating point capacities would break the table indices).
"""

from __future__ import annotations

import itertools
from typing import List, Sequence, Tuple

from .models import PackingPlan, Parcel

SCALE = 100  # 1 kg -> 100 integer units (10 g resolution)


# ---------------------------------------------------------------------------
# Core DP: O(n * W) time and space, exact optimum
# ---------------------------------------------------------------------------
def knapsack_dp(parcels: Sequence[Parcel], capacity_kg: float) -> PackingPlan:
    """Return the value-optimal set of parcels for one trip."""
    capacity = int(round(capacity_kg * SCALE))
    n = len(parcels)
    weights = [int(round(p.weight_kg * SCALE)) for p in parcels]
    values = [p.priority_score for p in parcels]

    # dp[i][w] = best value using the first i parcels with capacity w
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        wi, vi = weights[i - 1], values[i - 1]
        prev_row, row = dp[i - 1], dp[i]
        for w in range(capacity + 1):
            best = prev_row[w]                     # skip parcel i
            if wi <= w:
                take = prev_row[w - wi] + vi       # take parcel i
                if take > best:
                    best = take
            row[w] = best

    # Backtrack to recover which parcels were chosen.
    chosen_idx = []
    w = capacity
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            chosen_idx.append(i - 1)
            w -= weights[i - 1]
    chosen_idx.reverse()

    chosen_set = set(chosen_idx)
    selected = [parcels[i] for i in chosen_idx]
    skipped = [p for i, p in enumerate(parcels) if i not in chosen_set]

    return PackingPlan(
        selected=selected,
        skipped=skipped,
        total_value=dp[n][capacity],
        total_weight=sum(p.weight_kg for p in selected),
    )


# ---------------------------------------------------------------------------
# Space-optimised DP: O(n * W) time, O(W) space (used in benchmarks)
# ---------------------------------------------------------------------------
def knapsack_value_only(parcels: Sequence[Parcel], capacity_kg: float) -> int:
    capacity = int(round(capacity_kg * SCALE))
    dp = [0] * (capacity + 1)
    for parcel in parcels:
        wi = int(round(parcel.weight_kg * SCALE))
        vi = parcel.priority_score
        # Traverse backwards so each parcel can be used at most once.
        for w in range(capacity, wi - 1, -1):
            candidate = dp[w - wi] + vi
            if candidate > dp[w]:
                dp[w] = candidate
    return dp[capacity]


# ---------------------------------------------------------------------------
# Brute force reference: O(2^n) - only for tiny instances / verification
# ---------------------------------------------------------------------------
def knapsack_bruteforce(parcels: Sequence[Parcel], capacity_kg: float) -> int:
    best = 0
    n = len(parcels)
    for r in range(n + 1):
        for combo in itertools.combinations(range(n), r):
            weight = sum(parcels[i].weight_kg for i in combo)
            if weight <= capacity_kg + 1e-9:
                value = sum(parcels[i].priority_score for i in combo)
                if value > best:
                    best = value
    return best


# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------
def dp_table_snapshot(
    parcels: Sequence[Parcel], capacity_kg: float, step_kg: int = 1
) -> Tuple[List[List[int]], List[int]]:
    """Build the full DP table and return a readable slice of it.

    Returns (table, capacities) where `table[i][j]` is the best value using the
    first `i` parcels (i=0 is the all-zero row) and `capacities[j]` kg of load.
    Columns are sampled every `step_kg` kg so the output stays printable.
    """
    capacity = int(round(capacity_kg * SCALE))
    step = step_kg * SCALE
    capacities = list(range(0, capacity + 1, step))
    weights = [int(round(p.weight_kg * SCALE)) for p in parcels]
    values = [p.priority_score for p in parcels]

    dp = [[0] * (capacity + 1) for _ in range(len(parcels) + 1)]
    for i in range(1, len(parcels) + 1):
        wi, vi = weights[i - 1], values[i - 1]
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]
            if wi <= w and dp[i - 1][w - wi] + vi > dp[i][w]:
                dp[i][w] = dp[i - 1][w - wi] + vi

    table = [[dp[i][c] for c in capacities] for i in range(len(parcels) + 1)]
    return table, [c // SCALE for c in capacities]


def pack_boxes(parcels: Sequence[Parcel], box_capacity_kg: float = 5.0) -> List[List[Parcel]]:
    """First-Fit Decreasing bin packing -> physical boxes for the trip.

    FFD is a fast approximation: sort by weight descending, then place each
    parcel into the first box that still has room (or open a new box).
    """
    boxes: List[List[Parcel]] = []
    loads: List[float] = []
    for parcel in sorted(parcels, key=lambda p: p.weight_kg, reverse=True):
        placed = False
        for i, load in enumerate(loads):
            if load + parcel.weight_kg <= box_capacity_kg + 1e-9:
                boxes[i].append(parcel)
                loads[i] += parcel.weight_kg
                placed = True
                break
        if not placed:
            boxes.append([parcel])
            loads.append(parcel.weight_kg)
    return boxes
