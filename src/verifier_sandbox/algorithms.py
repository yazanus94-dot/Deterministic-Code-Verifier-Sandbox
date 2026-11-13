"""Reference algorithmic solutions used as ground truth by the verifiers.

Every implementation here is deterministic and covers the exact problem
families shipped in ``problems/``.  The verifier never trusts a submission's
own output: it always re-derives the expected answer with these functions.
"""

from __future__ import annotations

from collections.abc import Sequence
from heapq import heappop, heappush
from typing import Any

INF = float("inf")


def two_sum_reference(nums: Sequence[int], target: int) -> tuple[int, int] | None:
    """Return indices (i, j), i < j, with nums[i] + nums[j] == target.

    Deterministic O(n) hash-map solution.  Returns the lexicographically
    smallest valid pair when several exist so grading is fully deterministic.
    """
    best: tuple[int, int] | None = None
    seen: dict[int, int] = {}
    for j, value in enumerate(nums):
        need = target - value
        if need in seen:
            pair = (seen[need], j)
            if best is None or pair < best:
                best = pair
        seen.setdefault(value, j)
    return best


def knapsack_reference(
    weights: Sequence[int], values: Sequence[int], capacity: int
) -> int:
    """0/1 knapsack via bottom-up DP, O(n * capacity) time, O(capacity) space."""
    dp = [0] * (capacity + 1)
    for w, v in zip(weights, values, strict=True):
        for c in range(capacity, w - 1, -1):
            candidate = dp[c - w] + v
            if candidate > dp[c]:
                dp[c] = candidate
    return dp[capacity]


def dijkstra_reference(
    graph: dict[int, list[tuple[int, int]]], source: int
) -> dict[int, float]:
    """Single-source shortest paths for non-negative weights, O(E log V)."""
    dist: dict[int, float] = {source: 0.0}
    heap: list[tuple[float, int]] = [(0.0, source)]
    visited: set[int] = set()
    while heap:
        d, node = heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        for neighbor, weight in graph.get(node, []):
            nd = d + weight
            if nd < dist.get(neighbor, INF):
                dist[neighbor] = nd
                heappush(heap, (nd, neighbor))
    return dist


def lcs_length_reference(a: str, b: str) -> int:
    """Longest common subsequence length, O(len(a) * len(b)) time, O(min) space."""
    if len(a) < len(b):
        a, b = b, a
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        curr = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[-1]


def bracket_balance_reference(s: str) -> bool:
    """Return True when every bracket opens/closes correctly and in order."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
    return not stack


def solve(problem_id: str, payload: dict[str, Any]) -> Any:
    """Dispatch table used by the verifier to compute ground truth."""
    solvers: dict[str, Any] = {
        "two_sum": lambda p: two_sum_reference(p["nums"], p["target"]),
        "knapsack": lambda p: knapsack_reference(
            p["weights"], p["values"], p["capacity"]
        ),
        "shortest_path": lambda p: dijkstra_reference(p["graph"], p["source"]),
        "lcs_length": lambda p: lcs_length_reference(p["a"], p["b"]),
        "bracket_balance": lambda p: bracket_balance_reference(p["text"]),
    }
    if problem_id not in solvers:
        raise KeyError(f"no reference solver registered for {problem_id!r}")
    return solvers[problem_id](payload)
