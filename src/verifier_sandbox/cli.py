"""Command-line interface: verify a submission file against a problem.

Usage::

    python -m verifier_sandbox.cli verify --problem two_sum \
        --submission path/to/submission.py

    python -m verifier_sandbox.cli demo   # verify the bundled reference and
                                          # the bundled hard-coded cheat
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verifier_sandbox.core import VerifierEngine, Verdict, load_builtin_problems
from verifier_sandbox.services import default_sandbox


def _build_engine(args: argparse.Namespace) -> VerifierEngine:
    sandbox_backend = args.sandbox
    if sandbox_backend == "auto":
        sandbox = default_sandbox()
    elif sandbox_backend == "docker":
        from verifier_sandbox.services import DockerSandbox  # noqa: PLC0415

        sandbox = DockerSandbox()
    else:
        from verifier_sandbox.services import SubprocessSandbox  # noqa: PLC0415

        sandbox = SubprocessSandbox()
    return VerifierEngine(
        problems=load_builtin_problems(),
        sandbox=sandbox,
        timeout_s=args.timeout,
        memory_mb=args.memory,
    )


def cmd_demo(engine: VerifierEngine) -> int:
    import problems.registry as registry  # noqa: PLC0415

    reference = registry.REFERENCE_SOLUTIONS["two_sum"]
    cheat = registry.REFERENCE_SOLUTIONS["hardcoded"]
    for label, code in (("reference solution", reference), ("hard-coded cheat", cheat)):
        result = engine.verify("two_sum", code)
        print(f"{label:>20}: {result.verdict:<9} ({result.cases_passed}/{result.cases_total} cases)")
    return 0


def cmd_verify(engine: VerifierEngine, args: argparse.Namespace) -> int:
    code = Path(args.submission).read_text(encoding="utf-8")
    result = engine.verify(args.problem, code)
    print(
        json.dumps(
            {
                "problem": result.problem_id,
                "verdict": result.verdict,
                "cases_passed": result.cases_passed,
                "cases_total": result.cases_total,
                "engine": result.engine,
                "failures": result.failures[:3],
                "errors": result.errors[:3],
            },
            indent=2,
        )
    )
    return 0 if result.verdict == Verdict.ACCEPTED else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verifier-sandbox")
    parser.add_argument("--sandbox", choices=["auto", "docker", "subprocess"],
                        default="auto", help="sandbox backend")
    parser.add_argument("--timeout", type=float, default=5.0,
                        help="per-case wall-clock budget in seconds")
    parser.add_argument("--memory", type=int, default=256,
                        help="per-case memory cap in MB (docker backend)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="grade the bundled reference + cheat")
    p_demo.set_defaults(func=cmd_demo)

    p_verify = sub.add_parser("verify", help="verify a submission file")
    p_verify.add_argument("--problem", required=True)
    p_verify.add_argument("--submission", required=True)
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    engine = _build_engine(args)
    if args.command == "demo":
        return cmd_demo(engine)
    return cmd_verify(engine, args)


if __name__ == "__main__":
    sys.exit(main())
