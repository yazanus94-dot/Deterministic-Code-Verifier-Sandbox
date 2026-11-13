"""Unit tests: sandbox execution mechanics on the subprocess backend."""

from __future__ import annotations

import pytest

from verifier_sandbox.exceptions import SandboxError, SubmissionTimeout
from verifier_sandbox.services import SubprocessSandbox, static_scan


@pytest.fixture(scope="module")
def sandbox() -> SubprocessSandbox:
    return SubprocessSandbox()


class TestSubprocessSandbox:
    def test_benign_case_round_trip(self, sandbox: SubprocessSandbox) -> None:
        code = "def solve(payload):\n    return payload['x'] + 1\n"
        envelope = sandbox.run_case(code, '{"payload": {"x": 41}}', 5.0, 256)
        assert '"result": 42' in envelope

    def test_timeout_enforced(self, sandbox: SubprocessSandbox) -> None:
        # "import signal" is scan-blocked; use a long finite loop instead.
        code = "def solve(payload):\n    return sum(range(10**9))\n"
        with pytest.raises(SubmissionTimeout):
            sandbox.run_case(code, '{"payload": {}}', 1.0, 256)

    def test_crash_raises_sandbox_error(self, sandbox: SubprocessSandbox) -> None:
        code = "def solve(payload):\n    raise RuntimeError('boom')\n"
        with pytest.raises(SandboxError):
            sandbox.run_case(code, '{"payload": {}}', 5.0, 256)

    def test_large_output_capped(self, sandbox: SubprocessSandbox) -> None:
        code = "def solve(payload):\n    return 'x' * (10 * 1024 * 1024)\n"
        envelope = sandbox.run_case(code, '{"payload": {}}', 10.0, 256)
        assert len(envelope) <= 64 * 1024


class TestScanBypassAttempts:
    """Adversarial payloads that try to sneak past the static scanner."""

    @pytest.mark.parametrize(
        "payload",
        [
            "import socket; s = socket.socket()",
            "import urllib.request as u; u.urlopen('http://evil')",
            "from subprocess import run; run(['ls'])",
            "import shutil; shutil.rmtree('/')",
            "x = __import__('ctypes')",
        ],
    )
    def test_all_escape_attempts_flagged(self, payload: str) -> None:
        assert static_scan(payload)
