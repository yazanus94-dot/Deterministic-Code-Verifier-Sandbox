# Design Decisions

## 1. Seed bound to submission text

**Decision:** `seed = SHA-256(problem_id || submission_text)`, not a global
fixed seed, not a random seed.

**Trade-off:**

| Option | Copy-paste of accepted answers | Determinism |
|---|---|---|
| Global fixed seed | trivially safe to share answers | yes |
| Random seed | prevented | **no** -- grading not reproducible |
| Content-bound seed (chosen) | prevented (different text ⇒ different cases) | yes |

A submission that "passed" once cannot have its exact answers reused by
another submission: any textual change reshuffles the case set.

## 2. Case delivery via scratch files, not stdin

**Decision:** write `case.json` into the scratch directory instead of piping
it over stdin.

**Reasoning:** the Docker attach-socket API for stdin is low-level and
brittle (shutdown semantics differ across SDK versions). A file mounted
read-only into the container is one line of SDK code and works identically
for both backends. Untrusted code cannot modify it (read-only mount) and
cannot read the expected answer (it is not in the payload).

## 3. Denylist static scan *before* execution

**Decision:** reject submissions containing escape-shaped patterns before
running anything.

**Trade-off:** a denylist has false negatives (obfuscated escapes) and false
positives (a benign `open(` in a string). We accept both: false negatives
are caught by the container's second line of defense (no network, no
writable paths, memory/CPU caps), and false positives only cost the
author of a suspicious submission, not the grader's integrity.

## 4. Subprocess fallback, honestly labeled

**Decision:** keep a non-isolated subprocess backend for Docker-less hosts.

**Reasoning:** the evaluation pipeline should not collapse on machines
without a daemon, but we refuse to pretend it is secure:
`docs/security.md` states plainly that subprocess mode is *not* an isolation
boundary. `default_sandbox()` prefers Docker when available.

## 5. Canonical JSON comparison

**Decision:** compare `json.dumps(actual, sort_keys=True, separators=...)`
against `json.dumps(expected, ...)`.

**Reasoning:** the wire protocol is JSON, so tuples become lists and int
dict keys become strings. Comparing Python objects directly would fail
correct submissions; comparing raw JSON would be vulnerable to ordering
noise. Canonical serialization resolves both.

## 6. Memory before wall-clock as the primary resource lever

**Decision:** 256 MB default memory cap, 0.5 CPU quota, 5 s timeout.

**Reasoning:** memory is the resource attackers exhaust most easily
(`[0] * 10**9`); the kernel OOM-kill is instant and cannot be evaded.
Timeouts are the noisy signal (I/O stalls, cold JIT) so they are the safety
net, not the primary cap.
