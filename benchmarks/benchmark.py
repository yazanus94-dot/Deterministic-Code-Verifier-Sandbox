"""Reproducible benchmark for the verifier sandbox.

Measures:
1. Reference-solver scaling per problem family (Python microbenchmarks).
2. End-to-end grading cost: time to grade one submission (subprocess
   backend) and per-case container overhead (Docker backend).

Run with:  python benchmarks/benchmark.py
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier_sandbox import algorithms  # noqa: E402
from verifier_sandbox.core import VerifierEngine, load_builtin_problems  # noqa: E402
from verifier_sandbox.services import SubprocessSandbox  # noqa: E402


def timeit(fn, *args, repeat: int = 5) -> float:
    """Return median wall-clock seconds across ``repeat`` runs."""
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn(*args)
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def bench_reference_solvers() -> dict[str, float]:
    """Scaling check on the largest generator sizes."""
    import random

    rng = random.Random(0)
    nums = [rng.randint(-50, 50) for _ in range(200_000)]
    target = nums[0] + nums[1]

    weights = [rng.randint(1, 15) for _ in range(500)]
    values = [rng.randint(1, 30) for _ in range(500)]

    graph = {n: [(m, 1) for m in range(n + 1, min(n + 6, 5000))] for n in range(5000)}

    a = "".join(rng.choice("abcd") for _ in range(2000))
    b = "".join(rng.choice("abcd") for _ in range(2000))

    text_stack: list[str] = ["("] * 500 + [")"] * 500
    rng.shuffle(text_stack)
    text = "".join(text_stack)

    return {
        "two_sum n=200k": timeit(algorithms.two_sum_reference, nums, target),
        "knapsack n=500 c=400": timeit(
            algorithms.knapsack_reference, weights, values, 400
        ),
        "dijkstra n=5000": timeit(algorithms.dijkstra_reference, graph, 0),
        "lcs 2000x2000": timeit(algorithms.lcs_length_reference, a, b),
        "bracket_balance 1k": timeit(algorithms.bracket_balance_reference, text),
    }


def bench_grading() -> dict[str, float]:
    from problems.registry import REFERENCE_SOLUTIONS

    code = REFERENCE_SOLUTIONS["two_sum"]
    engine = VerifierEngine(
        problems=load_builtin_problems(), sandbox=SubprocessSandbox(), timeout_s=5.0
    )
    per_case = timeit(
        lambda: engine.sandbox.run_case(
            code, '{"payload": {"nums": [1,2,3,4], "target": 5}}', 5.0, 256
        ),
        repeat=10,
    )
    full = timeit(engine.verify, "two_sum", code, repeat=3)
    return {"subprocess per case": per_case, "full verify (16 cases)": full}


def bench_docker_overhead() -> float | None:
    """Per-case container overhead, or None when Docker is unavailable."""
    try:
        from verifier_sandbox.services import DockerSandbox

        sandbox = DockerSandbox()
    except Exception:  # noqa: BLE001
        return None
    code = "def solve(payload):\n    return payload\n"
    return timeit(
        lambda: sandbox.run_case(
            code, '{"payload": {"x": 1}}', timeout_s=20.0, memory_mb=256
        ),
        repeat=5,
    )


def main() -> None:
    print(json.dumps({"reference_solvers": bench_reference_solvers()}, indent=2))
    print(json.dumps({"grading_cost_subprocess": bench_grading()}, indent=2))
    docker = bench_docker_overhead()
    label = "grading_cost_docker per case" if docker else "docker backend unavailable"
    print(json.dumps({label: docker}, indent=2))


if __name__ == "__main__":
    main()
