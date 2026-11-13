"""Property-based tests (Hypothesis): the heart of the verifier's rigor.

These prove three properties:

1. **Reference correctness** -- the bundled reference solutions satisfy their
   mathematical invariants for *arbitrary* randomized inputs.
2. **Cheat rejection** -- any constant-answer submission is rejected by the
   engine with overwhelming probability.
3. **Partial-solution rejection** -- naive/O(n^2)-with-bug implementations
   that pass examples but fail on hidden inputs are exposed.
"""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from verifier_sandbox import algorithms
from verifier_sandbox.core import (
    VerifierEngine,
    generate_knapsack_case,
    generate_two_sum_case,
    load_builtin_problems,
)

TEXT_ALPHABET = "ab()"
BRACKET_CHARS = "()[]{}"


class TestReferenceProperties:
    @settings(max_examples=100, deadline=None)
    @given(
        st.lists(st.integers(min_value=-1000, max_value=1000), min_size=2, max_size=60),
        st.integers(min_value=-2000, max_value=2000),
    )
    def test_two_sum_pair_is_valid(
        self, nums: list[int], target: int
    ) -> None:
        result = algorithms.two_sum_reference(nums, target)
        if result is None:
            assert all(
                nums[i] + nums[j] != target
                for i in range(len(nums))
                for j in range(i + 1, len(nums))
            )
        else:
            i, j = result
            assert 0 <= i < j < len(nums)
            assert nums[i] + nums[j] == target

    @settings(max_examples=100, deadline=None)
    @given(
        st.lists(st.integers(min_value=1, max_value=50), min_size=1, max_size=15),
        st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=15),
        st.integers(min_value=0, max_value=100),
    )
    def test_knapsack_result_matches_bruteforce(
        self, weights: list[int], values: list[int], capacity: int
    ) -> None:
        n = min(len(weights), len(values))
        weights, values = weights[:n], values[:n]
        expected = 0
        for mask in range(1 << n):
            w = sum(weights[i] for i in range(n) if mask >> i & 1)
            v = sum(values[i] for i in range(n) if mask >> i & 1)
            if w <= capacity:
                expected = max(expected, v)
        assert algorithms.knapsack_reference(weights, values, capacity) == expected

    @settings(max_examples=100, deadline=None)
    @given(
        st.text(alphabet=BRACKET_CHARS, max_size=40),
    )
    def test_bracket_balance_matches_reduction_oracle(
        self, text: str
    ) -> None:
        # Independent oracle: repeatedly delete matched pairs "()[]{}"
        # until a fixpoint; the string is valid iff nothing survives.
        reduced = text
        prev = None
        while prev != reduced:
            prev = reduced
            for pair in ("()", "[]", "{}"):
                reduced = reduced.replace(pair, "")
        assert algorithms.bracket_balance_reference(text) == (reduced == "")

    @settings(max_examples=50, deadline=None)
    @given(
        st.text(alphabet=TEXT_ALPHABET, max_size=12),
        st.text(alphabet=TEXT_ALPHABET, max_size=12),
    )
    def test_lcs_length_matches_dp_bruteforce(self, a: str, b: str) -> None:
        assert algorithms.lcs_length_reference(a, b) == _lcs_bruteforce(a, b)

    @settings(max_examples=60, deadline=None)
    @given(
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=9),
                st.integers(min_value=0, max_value=9),
                st.integers(min_value=1, max_value=20),
            ),
            min_size=0,
            max_size=40,
        ),
        st.integers(min_value=0, max_value=9),
    )
    def test_dijkstra_distance_never_overestimates(
        self, edges: list[tuple[int, int, int]], source: int
    ) -> None:
        graph: dict[int, list[tuple[int, int]]] = {n: [] for n in range(10)}
        for u, v, w in edges:
            if u != v:
                graph[u].append((v, w))
        dist = algorithms.dijkstra_reference(graph, source)
        # Bellman-Ford cross-check on a small fixed-size graph.
        bf: dict[int, float] = {source: 0.0}
        for _ in range(10):
            for u in graph:
                if u in bf:
                    for v, w in graph[u]:
                        if bf.get(v, float("inf")) > bf[u] + w:
                            bf[v] = bf[u] + w
        for node, d in dist.items():
            assert d == bf[node]


def _lcs_bruteforce(a: str, b: str) -> int:
    if not a or not b:
        return 0
    if a[-1] == b[-1]:
        return 1 + _lcs_bruteforce(a[:-1], b[:-1])
    return max(_lcs_bruteforce(a[:-1], b), _lcs_bruteforce(a, b[:-1]))


class TestCheatRejectionProperties:
    """The verifier must reject constant answers for arbitrary constants."""

    @settings(max_examples=15, deadline=None)
    @given(st.integers(min_value=0, max_value=10**6))
    def test_hardcoded_index_pair_rejected(self, fake_index: int) -> None:
        engine = VerifierEngine(
            problems=load_builtin_problems(),
            timeout_s=5.0,
        )
        code = f"def solve(payload):\n    return ({fake_index}, {fake_index})\n"
        result = engine.verify("two_sum", code)
        assert result.verdict == "rejected"

    @settings(max_examples=15, deadline=None)
    @given(st.integers(min_value=0, max_value=500))
    def test_hardcoded_knapsack_value_rejected(self, constant: int) -> None:
        engine = VerifierEngine(
            problems=load_builtin_problems(),
            timeout_s=5.0,
        )
        code = f"def solve(payload):\n    return {constant}\n"
        result = engine.verify("knapsack", code)
        assert result.verdict == "rejected"

    def test_examples_only_solutions_fail_hidden_cases(self) -> None:
        """A solver memorizing only the sample inputs must fail."""
        engine = VerifierEngine(problems=load_builtin_problems(), timeout_s=5.0)
        # Returns the correct LCS only for the classic "abcde"/"ace" example,
        # a plausible cheat after seeing public samples.
        code = (
            "def solve(payload):\n"
            "    if payload.get('a') == 'abcde' and payload.get('b') == 'ace':\n"
            "        return 3\n"
            "    return len(payload.get('a', ''))\n"
        )
        result = engine.verify("lcs_length", code)
        assert result.verdict == "rejected"


class TestGeneratorStatisticalProperties:
    def test_generators_cover_diverse_states(self) -> None:
        rng = random.Random(42)
        targets = {generate_two_sum_case(rng)["target"] for _ in range(200)}
        assert len(targets) > 100  # not degenerate
        knapsacks = {generate_knapsack_case(rng)["capacity"] for _ in range(200)}
        assert len(knapsacks) > 20
