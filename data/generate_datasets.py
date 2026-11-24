"""Generate the sample datasets used by the Mini-Courier Planner.

Run from the project root:  python data/generate_datasets.py
Deterministic (fixed seeds) so results are reproducible.
"""

from __future__ import annotations

import csv
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))

# 12 nodes on a ~20 x 15 km city grid (depot in the centre).
POINTS = [
    ("Depot", 10.0, 7.5),
    ("Market", 3.0, 12.0),
    ("Station", 16.5, 12.5),
    ("Hospital", 6.0, 3.0),
    ("School", 13.0, 2.5),
    ("Mall", 18.0, 6.0),
    ("Tower-A", 2.0, 6.0),
    ("Tower-B", 9.0, 13.5),
    ("University", 14.0, 15.0),
    ("Airport", 19.0, 16.0),
    ("Industrial", 4.0, 17.0),
    ("Old-City", 11.0, 1.0),
]
DESTINATIONS = [p[0] for p in POINTS if p[0] != "Depot"]
TIERS = ["standard", "standard", "silver", "silver", "gold", "platinum"]


def write_points() -> None:
    with open(os.path.join(HERE, "delivery_points.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "x", "y"])
        for name, x, y in POINTS:
            writer.writerow([name, x, y])


def random_parcels(n: int, seed: int, deadline_range=(30, 600), weight_range=(0.5, 8.0)):
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "parcel_id": f"PKG{i:04d}",
                "destination": rng.choice(DESTINATIONS),
                "weight_kg": round(rng.uniform(*weight_range), 1),
                "priority": rng.choices([1, 2, 3, 4, 5], weights=[1, 2, 4, 3, 1])[0],
                "deadline_min": rng.randint(*deadline_range),
                "customer_tier": rng.choice(TIERS),
            }
        )
    return rows


# A hand-built small case: distinct deadlines, a mix of heavy/valuable parcels
# so the knapsack choice is easy to explain during the viva.
SMALL = [
    ("PKG0001", "Hospital", 4.0, 5, 45, "platinum"),
    ("PKG0002", "Market", 2.5, 4, 60, "gold"),
    ("PKG0003", "Station", 3.0, 3, 90, "silver"),
    ("PKG0004", "University", 1.5, 2, 120, "standard"),
    ("PKG0005", "Mall", 5.0, 4, 75, "gold"),
    ("PKG0006", "Airport", 6.5, 5, 150, "platinum"),
    ("PKG0007", "Old-City", 2.0, 3, 30, "standard"),
    ("PKG0008", "School", 3.5, 2, 210, "silver"),
    ("PKG0009", "Tower-A", 4.5, 1, 300, "standard"),
    ("PKG0010", "Industrial", 7.0, 3, 180, "gold"),
]


def write_parcels(filename: str, rows) -> None:
    with open(os.path.join(HERE, filename), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["parcel_id", "destination", "weight_kg", "priority", "deadline_min", "customer_tier"],
        )
        writer.writeheader()
        for row in rows:
            if isinstance(row, dict):
                writer.writerow(row)
            else:
                writer.writerow(dict(zip(writer.fieldnames, row)))


def main() -> None:
    write_points()
    write_parcels("parcels_small.csv", SMALL)
    write_parcels("parcels_medium.csv", random_parcels(60, seed=2024))
    write_parcels("parcels_large.csv", random_parcels(400, seed=2025))
    print("Wrote delivery_points.csv, parcels_small.csv, parcels_medium.csv, parcels_large.csv")


if __name__ == "__main__":
    main()
