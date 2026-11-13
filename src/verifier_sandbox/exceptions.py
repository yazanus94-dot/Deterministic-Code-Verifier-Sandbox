"""Exception hierarchy for the verifier sandbox."""

from __future__ import annotations


class VerifierError(Exception):
    """Base class for all verifier sandbox errors."""


class StaticScanError(VerifierError):
    """Raised when a submission contains forbidden patterns/imports."""

    def __init__(self, findings: list[str]) -> None:
        self.findings = findings
        joined = ", ".join(findings)
        super().__init__(f"Static scan rejected submission: {joined}")


class SandboxError(VerifierError):
    """Raised when the sandbox itself fails to execute a submission."""


class SubmissionTimeout(VerifierError):
    """Raised when a submission exceeds its wall-clock budget."""

    def __init__(self, timeout_s: float) -> None:
        self.timeout_s = timeout_s
        super().__init__(f"Submission exceeded time budget of {timeout_s}s")


class ResourceLimitExceeded(VerifierError):
    """Raised when a submission exceeds its memory budget."""


class UnknownProblem(VerifierError):
    """Raised when a requested problem id is not registered."""
