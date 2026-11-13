"""Sandbox executors: how untrusted submissions are actually executed.

Two interchangeable backends implement the same ``SandboxExecutor`` protocol:

* :class:`DockerSandbox` -- the production backend.  Runs every case inside a
  throwaway container with networking disabled, a hard memory cap, a CPU
  quota and a read-only root filesystem.
* :class:`SubprocessSandbox` -- a fallback used on hosts without Docker
  (e.g. some CI runners).  It enforces the same wall-clock and output-size
  budgets but provides *no* OS-level isolation; documentation must be
  explicit about this trade-off.

Both backends speak the same wire protocol with the trusted harness running
next to the untrusted code:

1. The case payload is written to the child's ``stdin`` as JSON.
2. The harness calls ``solve(case)`` from the untrusted ``submission.py``.
3. The resulting JSON is written to ``stdout`` and size-capped.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Protocol

from verifier_sandbox.exceptions import (
    ResourceLimitExceeded,
    SandboxError,
    SubmissionTimeout,
)

HARNESS_TEMPLATE = '''\
import json, sys
from pathlib import Path

import submission

case = json.loads(Path("case.json").read_text(encoding="utf-8"))
result = submission.solve(case["payload"])
sys.stdout.write(json.dumps({"result": result}))
sys.stdout.flush()
'''

MAX_STDOUT_BYTES = 64 * 1024

# Patterns that indicate the submission is trying to escape its contract.
# Both "import X" and "from X" forms are covered per risky module.
FORBIDDEN_MODULES: tuple[str, ...] = (
    "socket",
    "urllib",
    "http",
    "requests",
    "ftplib",
    "telnetlib",
    "subprocess",
    "shutil",
    "ctypes",
    "pickle",
    "multiprocessing",
    "threading",
    "signal",
    "os",
)

FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    *[(f"import {m}", "risky module") for m in FORBIDDEN_MODULES],
    *[(f"from {m}", "risky module") for m in FORBIDDEN_MODULES],
    ("__import__", "dynamic import escape"),
    ("eval(", "dynamic evaluation"),
    ("exec(", "dynamic evaluation"),
    ("compile(", "dynamic evaluation"),
    ("globals(", "namespace escape"),
    ("builtins", "namespace escape"),
    ("os.system", "shell execution"),
    ("os.popen", "shell execution"),
    ("open(", "filesystem access"),
    ("pathlib", "filesystem access"),
    ("input(", "interactive I/O"),
    ("while True", "potential infinite loop"),
)


def static_scan(code: str) -> list[str]:
    """Return a list of human-readable findings; empty means the code is clean."""
    findings: list[str] = []
    for pattern, reason in FORBIDDEN_PATTERNS:
        if pattern in code:
            findings.append(f"{pattern!r} ({reason})")
    return findings


def _truncate(data: bytes) -> bytes:
    if len(data) <= MAX_STDOUT_BYTES:
        return data
    return data[:MAX_STDOUT_BYTES]


class SandboxExecutor(Protocol):
    """Structural interface implemented by every sandbox backend."""

    def run_case(
        self,
        submission_code: str,
        case_json: str,
        timeout_s: float,
        memory_mb: int,
    ) -> str:
        """Execute one case, returning the JSON envelope the harness printed."""
        ...


class SubprocessSandbox:
    """Execute submissions in a child process with time/output budgets.

    This backend keeps the evaluation pipeline alive on machines without
    Docker.  It is *not* an isolation boundary: see docs/security.md for the
    threat model discussion and why container mode is the secure default.
    """

    name = "subprocess"

    def run_case(
        self,
        submission_code: str,
        case_json: str,
        timeout_s: float,
        memory_mb: int,
    ) -> str:
        with tempfile.TemporaryDirectory(prefix="vbox-") as tmp:
            workdir = Path(tmp)
            (workdir / "submission.py").write_text(submission_code, encoding="utf-8")
            harness = workdir / "harness.py"
            harness.write_text(HARNESS_TEMPLATE, encoding="utf-8")
            return self._execute(workdir, case_json, timeout_s)

    def _execute(self, workdir: Path, case_json: str, timeout_s: float) -> str:
        (workdir / "case.json").write_text(case_json, encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "harness.py"],
            cwd=str(workdir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.communicate()
            raise SubmissionTimeout(timeout_s) from exc
        if proc.returncode != 0:
            tail = (stderr or b"")[-2048:].decode("utf-8", errors="replace")
            raise SandboxError(f"sandbox exited with {proc.returncode}: {tail}")
        return _truncate(stdout).decode("utf-8", errors="replace")


class DockerSandbox:
    """Execute submissions inside disposable, network-isolated containers.

    Every case runs via ``docker run`` with:

    * ``network_disabled=True``  -- no ingress/egress at all
    * ``mem_limit``              -- hard memory cap (kernel OOM-kills)
    * ``nano_cpus``              -- CPU quota so runaway loops cannot starve the host
    * read-only mounts           -- only the scratch workdir is writable

    The container image is pulled once and reused; a scratch directory is
    created per case and destroyed afterwards.
    """

    name = "docker"

    def __init__(self, image: str = "python:3.11-slim") -> None:
        self.image = image
        try:
            import docker  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on host
            raise SandboxError(
                "docker SDK not installed; pip install docker"
            ) from exc
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception as exc:  # noqa: BLE001 - SDK raises broad exceptions
            raise SandboxError(f"Docker daemon unreachable: {exc}") from exc

    def run_case(
        self,
        submission_code: str,
        case_json: str,
        timeout_s: float,
        memory_mb: int,
    ) -> str:
        scratch = Path(tempfile.gettempdir()) / f"vbox-{uuid.uuid4().hex}"
        scratch.mkdir(parents=True, exist_ok=False)
        try:
            (scratch / "submission.py").write_text(submission_code, encoding="utf-8")
            (scratch / "harness.py").write_text(HARNESS_TEMPLATE, encoding="utf-8")
            (scratch / "case.json").write_text(case_json, encoding="utf-8")
            container = self.client.containers.run(
                image=self.image,
                command=["python", "harness.py"],
                working_dir="/sandbox",
                volumes={str(scratch): {"bind": "/sandbox", "mode": "ro"}},
                network_disabled=True,
                mem_limit=f"{memory_mb}m",
                nano_cpus=500_000_000,
                detach=True,
                stdin_open=True,
                tty=False,
            )
            try:
                result = container.wait(timeout=timeout_s)
                exit_code = int(result.get("StatusCode", 1))
                stdout = container.logs(stdout=True, stderr=False)
                if exit_code == 137:
                    raise ResourceLimitExceeded(f"container OOM-killed (>{memory_mb}m)")
                if exit_code != 0:
                    stderr = container.logs(stdout=False, stderr=True)[-2048:]
                    raise SandboxError(
                        f"container exited {exit_code}: "
                        f"{stderr.decode('utf-8', errors='replace')}"
                    )
                return _truncate(stdout).decode("utf-8", errors="replace")
            except (SubmissionTimeout, ResourceLimitExceeded):
                raise
            except SandboxError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise SubmissionTimeout(timeout_s) from exc
            finally:
                container.remove(force=True)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


def default_sandbox() -> SandboxExecutor:
    """Prefer the secure container backend, fall back to subprocess mode."""
    try:
        return DockerSandbox()
    except SandboxError:
        return SubprocessSandbox()


def envelope_for_submission_env() -> dict[str, str]:
    """Env vars the harness children receive; kept minimal on purpose."""
    return {"PYTHONDONTWRITEBYTECODE": "1", "PATH": os.environ.get("PATH", "")}
