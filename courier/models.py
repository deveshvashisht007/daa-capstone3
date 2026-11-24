"""Domain models used by every phase of the Mini-Courier Planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Parcel
# ---------------------------------------------------------------------------
@dataclass
class Parcel:
    """A single parcel waiting to be delivered.

    Attributes
    ----------
    parcel_id      : unique identifier printed on the label
    destination    : name of the delivery point (must exist in the graph)
    weight_kg      : physical weight, used as the knapsack "weight"
    priority       : business priority 1 (low) .. 5 (critical)
    deadline_min   : minutes left until the promised delivery time
    customer_tier  : standard / silver / gold / platinum
    """

    parcel_id: str
    destination: str
    weight_kg: float
    priority: int
    deadline_min: int
    customer_tier: str = "standard"

    # -- derived value ------------------------------------------------------
    @property
    def priority_score(self) -> int:
        """Monetary-like value used by the knapsack objective.

        Higher priority, earlier deadline and better customer tier all make a
        parcel more valuable, so the DP prefers it when capacity is scarce.
        """
        tier_bonus = {"standard": 0, "silver": 25, "gold": 50, "platinum": 80}.get(
            self.customer_tier.lower(), 0
        )
        urgency = max(0, 600 - self.deadline_min) // 10  # up to 60 points
        return self.priority * 100 + urgency + tier_bonus

    @property
    def sort_key(self) -> tuple:
        """Earliest deadline first, then highest priority, then lightest."""
        return (self.deadline_min, -self.priority, self.weight_kg)

    def __str__(self) -> str:  # compact, table friendly
        return (
            f"{self.parcel_id:<7} {self.destination:<12} "
            f"{self.weight_kg:>6.2f} kg  P{self.priority}  "
            f"{self.deadline_min:>4} min  {self.customer_tier:<8} "
            f"value={self.priority_score}"
        )


# ---------------------------------------------------------------------------
# Delivery point
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DeliveryPoint:
    """A node of the courier graph (depot or customer location)."""

    name: str
    x: float
    y: float


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class PackingPlan:
    """Output of the knapsack + first-fit-decreasing box packing."""

    selected: List[Parcel] = field(default_factory=list)
    skipped: List[Parcel] = field(default_factory=list)
    total_value: int = 0
    total_weight: float = 0.0
    boxes: List[List[Parcel]] = field(default_factory=list)


@dataclass
class RoutePlan:
    """Output of the nearest-neighbour + 2-opt route construction."""

    order: List[str] = field(default_factory=list)      # node names, depot first
    legs: List[tuple] = field(default_factory=list)     # (from, to, km)
    total_km: float = 0.0
    nn_km: float = 0.0                                  # length before 2-opt
    improvement_pct: float = 0.0
    depot_distances: Dict[str, float] = field(default_factory=dict)
    depot_paths: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class PlanResult:
    """Everything the courier needs for one trip."""

    depot: str
    capacity_kg: float
    box_capacity_kg: float = 5.0
    sorted_parcels: List[Parcel] = field(default_factory=list)
    packing: PackingPlan = field(default_factory=PackingPlan)
    route: RoutePlan = field(default_factory=RoutePlan)
    timings_ms: Dict[str, float] = field(default_factory=dict)
