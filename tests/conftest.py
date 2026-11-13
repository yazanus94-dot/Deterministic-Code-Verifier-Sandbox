"""Shared fixtures for the verifier sandbox test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from verifier_sandbox.core import VerifierEngine, load_builtin_problems
from verifier_sandbox.services import SandboxExecutor, SubprocessSandbox

FAST_TIMEOUT = float(os.environ.get("VBOX_TEST_TIMEOUT", "5"))


@pytest.fixture(scope="session")
def engine() -> VerifierEngine:
    """Fast engine on the subprocess backend: used by unit/property tests."""
    return VerifierEngine(
        problems=load_builtin_problems(),
        sandbox=SubprocessSandbox(),
        timeout_s=FAST_TIMEOUT,
    )


@pytest.fixture(scope="session")
def docker_engine() -> Iterator[VerifierEngine]:
    """Engine on the real Docker backend; skipped when daemon is offline."""
    pytest.importorskip("docker")
    from verifier_sandbox.services import DockerSandbox, SandboxError

    try:
        sandbox: SandboxExecutor = DockerSandbox()
    except SandboxError as exc:
        pytest.skip(f"Docker daemon unavailable: {exc}")
    yield VerifierEngine(
        problems=load_builtin_problems(), sandbox=sandbox, timeout_s=10.0
    )
