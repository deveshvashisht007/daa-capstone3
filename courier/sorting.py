"""Comparison-sorting algorithms used to prioritise parcels (Phase 2).

The planner needs parcels ordered by *earliest deadline first* (EDF), with
priority and weight as tie-breakers.  Merge sort is used in production because
it is stable and guarantees O(n log n) in the worst case, which matters when a
late parcel could miss its promised slot.  The other sorts are implemented so
their runtimes can be compared in Phase 4.
"""

from __future__ import annotations

from typing import Callable, List, Sequence

Key = Callable[[object], object]


# ---------------------------------------------------------------------------
# Insertion sort - O(n^2) worst case, O(n) on nearly sorted input, stable
# ---------------------------------------------------------------------------
def insertion_sort(items: Sequence, key: Key = lambda x: x) -> List:
    arr = list(items)
    for i in range(1, len(arr)):
        current = arr[i]
        current_key = key(current)
        j = i - 1
        while j >= 0 and key(arr[j]) > current_key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = current
    return arr


# ---------------------------------------------------------------------------
# Merge sort - O(n log n) always, stable  -> used by the planner
# ---------------------------------------------------------------------------
def merge_sort(items: Sequence, key: Key = lambda x: x) -> List:
    arr = list(items)
    if len(arr) <= 1:
        return arr
    _merge_sort_inplace(arr, 0, len(arr) - 1, key)
    return arr


def _merge_sort_inplace(arr: List, low: int, high: int, key: Key) -> None:
    if low >= high:
        return
    mid = (low + high) // 2
    _merge_sort_inplace(arr, low, mid, key)
    _merge_sort_inplace(arr, mid + 1, high, key)
    _merge(arr, low, mid, high, key)


def _merge(arr: List, low: int, mid: int, high: int, key: Key) -> None:
    left = arr[low : mid + 1]
    right = arr[mid + 1 : high + 1]
    i = j = 0
    k = low
    while i < len(left) and j < len(right):
        # "<=" keeps equal keys in their original order -> stable sort
        if key(left[i]) <= key(right[j]):
            arr[k] = left[i]
            i += 1
        else:
            arr[k] = right[j]
            j += 1
        k += 1
    while i < len(left):
        arr[k] = left[i]
        i += 1
        k += 1
    while j < len(right):
        arr[k] = right[j]
        j += 1
        k += 1


# ---------------------------------------------------------------------------
# Quick sort - O(n log n) average, O(n^2) worst, in-place, not stable
# ---------------------------------------------------------------------------
def quick_sort(items: Sequence, key: Key = lambda x: x) -> List:
    arr = list(items)
    _quick_sort(arr, 0, len(arr) - 1, key)
    return arr


def _quick_sort(arr: List, low: int, high: int, key: Key) -> None:
    while low < high:
        pivot_index = _partition(arr, low, high, key)
        # Recurse into the smaller half first to bound the stack depth.
        if pivot_index - low < high - pivot_index:
            _quick_sort(arr, low, pivot_index - 1, key)
            low = pivot_index + 1
        else:
            _quick_sort(arr, pivot_index + 1, high, key)
            high = pivot_index - 1


def _partition(arr: List, low: int, high: int, key: Key) -> int:
    """Median-of-three pivot selection + Lomuto partition."""
    mid = (low + high) // 2
    # order low, mid, high so that arr[mid] is the median
    if key(arr[mid]) < key(arr[low]):
        arr[low], arr[mid] = arr[mid], arr[low]
    if key(arr[high]) < key(arr[low]):
        arr[low], arr[high] = arr[high], arr[low]
    if key(arr[high]) < key(arr[mid]):
        arr[mid], arr[high] = arr[high], arr[mid]
    arr[mid], arr[high] = arr[high], arr[mid]  # median to the end
    pivot = key(arr[high])
    i = low - 1
    for j in range(low, high):
        if key(arr[j]) <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


# ---------------------------------------------------------------------------
# Heap sort - O(n log n) always, in-place, not stable
# ---------------------------------------------------------------------------
def heap_sort(items: Sequence, key: Key = lambda x: x) -> List:
    arr = list(items)
    n = len(arr)

    def sift_down(start: int, end: int) -> None:
        root = start
        while 2 * root + 1 <= end:
            child = 2 * root + 1
            if child + 1 <= end and key(arr[child]) < key(arr[child + 1]):
                child += 1
            if key(arr[root]) < key(arr[child]):
                arr[root], arr[child] = arr[child], arr[root]
                root = child
            else:
                return

    for start in range((n - 2) // 2, -1, -1):
        sift_down(start, n - 1)
    for end in range(n - 1, 0, -1):
        arr[0], arr[end] = arr[end], arr[0]
        sift_down(0, end - 1)
    return arr


# ---------------------------------------------------------------------------
# Timsort (Python's built-in) - highly optimised hybrid, stable
# ---------------------------------------------------------------------------
def timsort(items: Sequence, key: Key = lambda x: x) -> List:
    return sorted(items, key=key)


# Registry used by the benchmark harness.
SORT_ALGORITHMS = {
    "Insertion Sort": insertion_sort,
    "Merge Sort": merge_sort,
    "Quick Sort": quick_sort,
    "Heap Sort": heap_sort,
    "Timsort (built-in)": timsort,
}


def sort_parcels(parcels: Sequence) -> List:
    """Production prioritisation: stable EDF order via merge sort."""
    return merge_sort(parcels, key=lambda p: p.sort_key)
