"""Deterministic Code Verifier Sandbox.

A secure, containerized execution environment that grades untrusted
generated code against deterministic, randomized verification suites.
"""

from __future__ import annotations

from verifier_sandbox.core import Verdict, VerifierEngine, VerificationResult
from verifier_sandbox.exceptions import (
    ResourceLimitExceeded,
    SandboxError,
    StaticScanError,
    SubmissionTimeout,
    VerifierError,
)
from verifier_sandbox.services import DockerSandbox, SandboxExecutor, SubprocessSandbox

__version__ = "1.0.0"

__all__ = [
    "Verdict",
    "VerifierEngine",
    "VerificationResult",
    "SandboxExecutor",
    "DockerSandbox",
    "SubprocessSandbox",
    "VerifierError",
    "StaticScanError",
    "SubmissionTimeout",
    "ResourceLimitExceeded",
    "SandboxError",
]
