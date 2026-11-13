"""Problem registry for the verifier sandbox.

Each problem ships:
* a deterministic randomized input generator,
* the optimal reference solution (imported from ``algorithms``),
* two example submissions: an accepted optimal one and a hard-coded cheat.

The examples double as fixtures for the adversarial test suite.
"""

from __future__ import annotations

from typing import Any

from verifier_sandbox.core import (
    ProblemSpec,
    generate_bracket_case,
    generate_knapsack_case,
    generate_lcs_case,
    generate_shortest_path_case,
    generate_two_sum_case,
)
from verifier_sandbox import algorithms

PROBLEMS: dict[str, ProblemSpec] = {
    p.problem_id: p
    for p in (
        ProblemSpec("two_sum", generate_two_sum_case,
                    lambda p: algorithms.two_sum_reference(p["nums"], p["target"])),
        ProblemSpec("knapsack", generate_knapsack_case,
                    lambda p: algorithms.knapsack_reference(
                        p["weights"], p["values"], p["capacity"])),
        ProblemSpec("shortest_path", generate_shortest_path_case,
                    lambda p: algorithms.dijkstra_reference(p["graph"], p["source"])),
        ProblemSpec("lcs_length", generate_lcs_case,
                    lambda p: algorithms.lcs_length_reference(p["a"], p["b"])),
        ProblemSpec("bracket_balance", generate_bracket_case,
                    lambda p: algorithms.bracket_balance_reference(p["text"])),
    )
}

REFERENCE_SOLUTIONS: dict[str, str] = {
    "two_sum": '''\
def solve(payload):
    nums = payload["nums"]
    target = payload["target"]
    best = None
    seen = {}
    for j, value in enumerate(nums):
        need = target - value
        if need in seen:
            pair = (seen[need], j)
            if best is None or pair < best:
                best = pair
        seen.setdefault(value, j)
    return best
''',
    "hardcoded": '''\
def solve(payload):
    return (0, 1)
''',
}


def payload_examples() -> dict[str, dict[str, Any]]:
    """A fixed example payload per problem, for README and smoke tests."""
    return {
        "two_sum": {"nums": [3, -1, 7, 11, 2], "target": 10},
        "knapsack": {"weights": [2, 3, 5], "values": [10, 15, 25], "capacity": 7},
        "shortest_path": {
            "graph": {0: [(1, 4), (2, 1)], 1: [(3, 1)], 2: [(1, 2), (3, 5)], 3: []},
            "source": 0,
        },
        "lcs_length": {"a": "abcde", "b": "ace"},
        "bracket_balance": {"text": "([{}])"},
    }
