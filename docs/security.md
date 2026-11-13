# Security Considerations

## Threat model

Untrusted submissions are actively hostile. Assumed capabilities:

- Attempt any import that is importable in a bare `python:3.11-slim`.
- Allocate unbounded memory (e.g. `[0] * 10**9`).
- Spin CPU-bound infinite loops.
- Probe the local network from inside the sandbox.
- Write to any path visible to the sandbox user.
- Obfuscate escape attempts to evade pattern matching.

## Defense layers (in order)

1. **Static denylist scan** (host, pre-execution). Rejects
   network/process/filesystem/dynamic-eval patterns. Cheap, deterministic,
   and eliminates the most obvious payloads before any execution.
2. **Container isolation** (`DockerSandbox`):
   - `network_disabled=True` -- no ingress/egress sockets.
   - `mem_limit` -- kernel-level OOM enforcement; cannot be evaded from
     userspace.
   - `nano_cpus=500_000_000` (0.5 CPU) -- runaway loops cannot starve the host.
   - Scratch volume mounted **read-only** -- the only writable path is the
     container's own ephemeral overlay, destroyed with the container.
   - Container removed with `force=True` in a `finally` block; the scratch
     directory is removed in an outer `finally`.
3. **Output capping** -- stdout truncated to 64 KiB so a submission cannot
   exhaust host memory through the result envelope or deadlock the pipe.
4. **Wall-clock timeout** -- client-side `container.wait(timeout=...)` /
   `communicate(timeout=...)` with explicit `kill()` on expiry.

## Honest limitations

- **Subprocess mode is not an isolation boundary.** It exists so the
  pipeline works on Docker-less hosts. On Windows hosts it relies on the
  static scan + timeout + output cap only. `default_sandbox()` prefers
  container mode for this reason.
- **Denylists are evadable.** `getattr(__builtins__, 'eval')`-style
  obfuscation can pass the scanner. The containment answer is layer 2;
  the scanner is a fast pre-filter, not a security boundary.
- **No fork-bomb protection in subprocess mode.** Container mode bounds
  PIDs via the shared kernel default; subprocess mode does not.
- **The verifier host must trust the daemon.** A compromised Docker daemon
  invalidates every guarantee here; out of scope by design.

## Security regression tests

`tests/unit/test_services.py::TestScanBypassAttempts` pins the scanner's
behavior against known escape payloads, and
`tests/integration/test_docker_pipeline.py` proves the container caps are
real by triggering OOM, timeout, and crash paths on purpose.
