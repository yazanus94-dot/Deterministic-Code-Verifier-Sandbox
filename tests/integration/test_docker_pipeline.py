"""Integration tests: full pipeline on the real Docker sandbox backend.

These tests require a running Docker daemon and are skipped gracefully when
it is unavailable.  They execute *actual untrusted code* inside containers,
which makes them slower than unit tests; they are marked ``integration``.
"""

from __future__ import annotations

import pytest

from verifier_sandbox.core import Verdict
from verifier_sandbox.exceptions import (
    ResourceLimitExceeded,
    SandboxError,
    SubmissionTimeout,
)
from verifier_sandbox.services import DockerSandbox

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def docker_sandbox() -> DockerSandbox:
    pytest.importorskip("docker")
    try:
        return DockerSandbox()
    except SandboxError as exc:
        pytest.skip(f"Docker daemon unavailable: {exc}")


class TestDockerIsolation:
    def test_benign_case_round_trip(self, docker_sandbox: DockerSandbox) -> None:
        code = "def solve(payload):\n    return payload['x'] * 2\n"
        envelope = docker_sandbox.run_case(
            code, '{"payload": {"x": 21}}', timeout_s=15.0, memory_mb=256
        )
        assert '"result": 42' in envelope

    def test_timeout_kills_runaway_loop(self, docker_sandbox: DockerSandbox) -> None:
        code = "def solve(payload):\n    return sum(range(10**9))\n"
        with pytest.raises(SubmissionTimeout):
            docker_sandbox.run_case(
                code, '{"payload": {}}', timeout_s=3.0, memory_mb=256
            )

    def test_memory_cap_enforced(self, docker_sandbox: DockerSandbox) -> None:
        code = "def solve(payload):\n    return len([0] * (10**9))\n"
        with pytest.raises((ResourceLimitExceeded, SandboxError, SubmissionTimeout)):
            docker_sandbox.run_case(
                code, '{"payload": {}}', timeout_s=15.0, memory_mb=64
            )

    def test_crash_surfaces_as_sandbox_error(
        self, docker_sandbox: DockerSandbox
    ) -> None:
        code = "def solve(payload):\n    1 / 0\n"
        with pytest.raises(SandboxError):
            docker_sandbox.run_case(
                code, '{"payload": {}}', timeout_s=15.0, memory_mb=256
            )


class TestFullPipelineOnContainers:
    def test_reference_solution_accepted_end_to_end(
        self, docker_engine
    ) -> None:
        from problems.registry import REFERENCE_SOLUTIONS

        result = docker_engine.verify("two_sum", REFERENCE_SOLUTIONS["two_sum"])
        assert result.verdict == Verdict.ACCEPTED
        assert result.engine == "docker"

    def test_hardcoded_cheat_rejected_end_to_end(self, docker_engine) -> None:
        from problems.registry import REFERENCE_SOLUTIONS

        result = docker_engine.verify(
            "two_sum", REFERENCE_SOLUTIONS["hardcoded"]
        )
        assert result.verdict == Verdict.REJECTED
