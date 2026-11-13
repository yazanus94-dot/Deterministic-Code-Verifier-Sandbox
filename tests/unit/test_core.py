"""Unit tests: seed derivation, case generation determinism, static scan."""

from __future__ import annotations

import random

import pytest

from verifier_sandbox.core import (
    Verdict,
    VerifierEngine,
    _canonical,
    _seed_for,
    generate_knapsack_case,
    generate_two_sum_case,
    load_builtin_problems,
)
from verifier_sandbox.exceptions import StaticScanError, UnknownProblem
from verifier_sandbox.services import static_scan


class TestSeedDerivation:
    def test_seed_is_pure_function_of_problem_and_code(self) -> None:
        assert _seed_for("two_sum", "def solve(): ...") == _seed_for(
            "two_sum", "def solve(): ..."
        )

    def test_seed_differs_per_submission(self) -> None:
        assert _seed_for("two_sum", "a = 1") != _seed_for("two_sum", "a = 2")

    def test_seed_differs_per_problem(self) -> None:
        assert _seed_for("two_sum", "x") != _seed_for("knapsack", "x")

    def test_seed_fits_in_64_bits(self) -> None:
        assert 0 <= _seed_for("p", "c") < 2**64


class TestCaseGeneration:
    def test_cases_are_deterministic(self) -> None:
        spec = load_builtin_problems()[0]
        first = spec.generate_cases(12345, 4)
        second = spec.generate_cases(12345, 4)
        assert [c.to_json() for c in first] == [c.to_json() for c in second]

    def test_two_sum_generator_valid_pair(self) -> None:
        rng = random.Random(7)
        for _ in range(50):
            payload = generate_two_sum_case(rng)
            nums, target = payload["nums"], payload["target"]
            assert any(
                nums[i] + nums[j] == target
                for i in range(len(nums))
                for j in range(i + 1, len(nums))
            )

    def test_knapsack_generator_bounds(self) -> None:
        rng = random.Random(1)
        for _ in range(50):
            payload = generate_knapsack_case(rng)
            assert 8 <= payload["capacity"] <= 40
            assert len(payload["weights"]) == len(payload["values"])


class TestStaticScan:
    @pytest.mark.parametrize(
        "snippet",
        [
            "import socket",
            "import subprocess\n",
            "x = eval('2+2')",
            "open('flag.txt')",
            "__import__('os').system('rm -rf /')",
            "import pickle",
            "while True:\n    pass",
        ],
    )
    def test_forbidden_patterns_rejected(self, snippet: str) -> None:
        assert static_scan(snippet), f"scan missed: {snippet}"

    def test_clean_solution_passes_scan(self) -> None:
        clean = "def solve(payload):\n    return payload\n"
        assert static_scan(clean) == []


class TestVerifierEngine:
    def test_unknown_problem_raises(self, engine: VerifierEngine) -> None:
        with pytest.raises(UnknownProblem):
            engine.verify("no_such_problem", "def solve(p): return p")

    def test_static_scan_error_propagates(self, engine: VerifierEngine) -> None:
        with pytest.raises(StaticScanError):
            engine.verify("two_sum", "import urllib.request")

    def test_error_verdict_on_runtime_crash(self, engine: VerifierEngine) -> None:
        result = engine.verify("two_sum", "def solve(payload):\n    raise ValueError()")
        assert result.verdict == Verdict.ERROR
        assert result.cases_passed == 0

    def test_accepted_verdict_for_reference(self, engine: VerifierEngine) -> None:
        from problems.registry import REFERENCE_SOLUTIONS

        result = engine.verify("two_sum", REFERENCE_SOLUTIONS["two_sum"])
        assert result.verdict == Verdict.ACCEPTED
        assert result.cases_passed == result.cases_total


class TestCanonicalComparison:
    def test_tuple_equals_list(self) -> None:
        assert _canonical((1, 2)) == _canonical([1, 2])

    def test_int_keys_equal_string_keys(self) -> None:
        assert _canonical({0: 1.5}) == _canonical({"0": 1.5})
