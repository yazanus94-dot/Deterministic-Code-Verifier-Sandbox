"""Core grading engine: deterministic verification of untrusted submissions.

The engine composes three layers:

1. :func:`static_scan`  -- reject submissions that reach outside their contract
2. :class:`ProblemSpec` -- randomized case generation with fixed seeds
3. :class:`VerifierEngine` -- execute every case in a sandbox and compare
   against a reference solution recomputed *in the host process*.

Determinism contract
--------------------
For a given ``(problem_id, seed)`` pair the generated case set is identical
on every machine and every run (``random.Random(seed)``).  The verdict is
therefore a pure function of the submission text: no wall-clock jitter, no
case-set drift, no grader discretion.  Two graders running the same engine
must agree bit-for-bit on the verdict.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from verifier_sandbox import algorithms
from verifier_sandbox.exceptions import StaticScanError, UnknownProblem
from verifier_sandbox.services import SandboxExecutor, SubprocessSandbox, static_scan

SEED_SALTS: tuple[int, ...] = (1_040_729, 1_048_583, 1_047_281, 1_049_017)
CASES_PER_SEED = 4


@dataclass(frozen=True)
class Case:
    """One verification case: an input and the expected output."""

    seed: int
    index: int
    payload: dict[str, Any]
    expected: Any

    def to_json(self) -> str:
        return json.dumps(
            {"payload": self.payload, "expected": self.expected},
            sort_keys=True,
        )


@dataclass
class ProblemSpec:
    """A problem family: id, randomized input generation and reference solver."""

    problem_id: str
    generator: Any  # callable[[random.Random], dict[str, Any]]
    reference: Any  # callable[[dict[str, Any]], Any]

    def generate_cases(self, seed: int, count: int = CASES_PER_SEED) -> list[Case]:
        """Generate ``count`` cases deterministically from ``seed``."""
        cases: list[Case] = []
        for index in range(count):
            rng = random.Random(seed + index)
            payload = self.generator(rng)
            cases.append(
                Case(seed=seed + index, index=index, payload=payload,
                     expected=self.reference(payload))
            )
        return cases


@dataclass
class VerificationResult:
    """Outcome of verifying a single submission."""

    problem_id: str
    verdict: str
    cases_passed: int
    cases_total: int
    failures: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    engine: str = "subprocess"

    @property
    def passed(self) -> bool:
        return self.verdict == "accepted"


class Verdict:
    """String constants so verdicts are comparable across processes."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


def _seed_for(problem_id: str, submission_code: str) -> int:
    """Derive the case-set seed from problem id + submission content.

    Binding the seed to the submission defeats copy-paste of accepted
    answers between submissions while keeping grading deterministic.
    """
    digest = hashlib.sha256(
        f"{problem_id}:{submission_code}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big")


class VerifierEngine:
    """Grade a submission against a randomized, seeded verification suite."""

    def __init__(
        self,
        problems: Sequence[ProblemSpec],
        sandbox: SandboxExecutor | None = None,
        timeout_s: float = 5.0,
        memory_mb: int = 256,
        seeds: Sequence[int] = SEED_SALTS,
        cases_per_seed: int = CASES_PER_SEED,
    ) -> None:
        self.problems = {p.problem_id: p for p in problems}
        self.sandbox = sandbox or SubprocessSandbox()
        self.timeout_s = timeout_s
        self.memory_mb = memory_mb
        self.seed_salts = list(seeds)
        self.cases_per_seed = cases_per_seed

    def get_problem(self, problem_id: str) -> ProblemSpec:
        try:
            return self.problems[problem_id]
        except KeyError as exc:
            raise UnknownProblem(problem_id) from exc

    def _iter_cases(self, problem: ProblemSpec, seed: int) -> Iterator[Case]:
        for salt in self.seed_salts:
            for case in problem.generate_cases(seed ^ salt, self.cases_per_seed):
                yield case

    def verify(
        self, problem_id: str, submission_code: str
    ) -> VerificationResult:
        """Run the full deterministic verification pipeline."""
        problem = self.get_problem(problem_id)
        findings = static_scan(submission_code)
        if findings:
            raise StaticScanError(findings)

        seed = _seed_for(problem_id, submission_code)
        passed = 0
        total = 0
        failures: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for case in self._iter_cases(problem, seed):
            total += 1
            try:
                envelope = self.sandbox.run_case(
                    submission_code=submission_code,
                    case_json=json.dumps(
                        {"payload": case.payload}, sort_keys=True
                    ),
                    timeout_s=self.timeout_s,
                    memory_mb=self.memory_mb,
                )
            except Exception as exc:  # noqa: BLE001 - graded as error verdict
                errors.append(
                    {
                        "seed": case.seed,
                        "index": case.index,
                        "error": str(exc),
                    }
                )
                continue
            actual = self._extract_result(envelope)
            if _canonical(actual) == _canonical(case.expected):
                passed += 1
            else:
                failures.append(
                    {
                        "seed": case.seed,
                        "index": case.index,
                        "expected": case.expected,
                        "actual": actual,
                    }
                )

        if errors:
            verdict = Verdict.ERROR
        elif passed == total:
            verdict = Verdict.ACCEPTED
        else:
            verdict = Verdict.REJECTED
        return VerificationResult(
            problem_id=problem_id,
            verdict=verdict,
            cases_passed=passed,
            cases_total=total,
            failures=failures,
            errors=errors,
            engine=getattr(self.sandbox, "name", "custom"),
        )

    @staticmethod
    def _extract_result(envelope: str) -> Any:
        envelope = envelope.strip()
        if not envelope:
            return None
        data = json.loads(envelope)
        return data.get("result")


def _canonical(value: Any) -> str:
    """Canonical JSON form so tuples/lists and int-keyed dicts compare equal
    across the JSON wire boundary."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def load_builtin_problems() -> list[ProblemSpec]:
    """Instantiate the problem families shipped with the package."""
    return [
        ProblemSpec(
            problem_id="two_sum",
            generator=generate_two_sum_case,
            reference=lambda p: algorithms.two_sum_reference(p["nums"], p["target"]),
        ),
        ProblemSpec(
            problem_id="knapsack",
            generator=generate_knapsack_case,
            reference=lambda p: algorithms.knapsack_reference(
                p["weights"], p["values"], p["capacity"]
            ),
        ),
        ProblemSpec(
            problem_id="shortest_path",
            generator=generate_shortest_path_case,
            reference=lambda p: algorithms.dijkstra_reference(p["graph"], p["source"]),
        ),
        ProblemSpec(
            problem_id="lcs_length",
            generator=generate_lcs_case,
            reference=lambda p: algorithms.lcs_length_reference(p["a"], p["b"]),
        ),
        ProblemSpec(
            problem_id="bracket_balance",
            generator=generate_bracket_case,
            reference=lambda p: algorithms.bracket_balance_reference(p["text"]),
        ),
    ]


# ---------------------------------------------------------------------------
# Randomized generators.  Each must be a pure function of the rng argument.
# ---------------------------------------------------------------------------

def generate_two_sum_case(rng: random.Random) -> dict[str, Any]:
    n = rng.randint(4, 24)
    nums = [rng.randint(-50, 50) for _ in range(n)]
    i, j = rng.sample(range(n), 2)
    target = nums[i] + nums[j]
    return {"nums": nums, "target": target}


def generate_knapsack_case(rng: random.Random) -> dict[str, Any]:
    n = rng.randint(3, 12)
    weights = [rng.randint(1, 15) for _ in range(n)]
    values = [rng.randint(1, 30) for _ in range(n)]
    capacity = rng.randint(8, 40)
    return {"weights": weights, "values": values, "capacity": capacity}


def generate_shortest_path_case(rng: random.Random) -> dict[str, Any]:
    nodes = list(range(rng.randint(5, 12)))
    graph: dict[int, list[tuple[int, int]]] = {n: [] for n in nodes}
    for u in nodes:
        for v in nodes:
            if u != v and rng.random() < 0.35:
                weight = rng.randint(1, 20)
                graph[u].append((v, weight))
    source = rng.choice(nodes)
    return {"graph": graph, "source": source}


def generate_lcs_case(rng: random.Random) -> dict[str, Any]:
    alphabet = "abcd"
    a = "".join(rng.choice(alphabet) for _ in range(rng.randint(3, 18)))
    b = "".join(rng.choice(alphabet) for _ in range(rng.randint(3, 18)))
    return {"a": a, "b": b}


def generate_bracket_case(rng: random.Random) -> dict[str, Any]:
    openers = "([{"
    closers = ")]}"
    stack: list[str] = []
    text = ""
    for _ in range(rng.randint(2, 20)):
        if stack and rng.random() < 0.45:
            text += closers[openers.index(stack.pop())]
        else:
            opener = rng.choice(openers)
            stack.append(opener)
            text += opener
    while stack:
        text += closers[openers.index(stack.pop())]
    # Inject imbalance ~50% of the time so "return True" cannot survive.
    if text and rng.random() < 0.5:
        pos = rng.randrange(len(text))
        if text[pos] in closers:
            wrong = rng.choice([c for c in closers if c != text[pos]])
            text = text[:pos] + wrong + text[pos + 1 :]
        else:
            text = text[:pos] + text[pos + 1 :]
    return {"text": text}
