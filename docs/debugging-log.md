# Debugging Log

Real issues hit while building the sandbox, with root causes and fixes.

## Issue 1: correct solutions graded as wrong (tuple vs list)

- **Symptom:** a provably optimal `two_sum` submission failed 16/16 cases.
- **Root cause:** submissions travel through a JSON envelope. Python tuples
  serialize to JSON *arrays*; the host compared `tuple(0, 1) == [0, 1]`,
  which is `False`. Every correct submission was rejected on a type
  technicality, not on correctness.
- **Debugging approach:** logged one failing envelope, printed
  `type(actual)`, spotted the tuple/list mismatch at the wire boundary.
- **Fix:** canonical comparison -- both sides serialized with
  `json.dumps(x, sort_keys=True, separators=(",", ":"))` before equality.
- **Regression test:** `tests/unit/test_core.py::TestCanonicalComparison`.

## Issue 2: reference solvers crashed with missing-argument errors

- **Symptom:** `TypeError: knapsack_reference() missing 2 required
  positional arguments` during grading.
- **Root cause:** the problem registry passed `ProblemSpec.reference`
  pointing directly at multi-argument functions instead of payload-aware
  adapters. Grading crashed *outside* the sandbox, on trusted code.
- **Fix:** every registry entry wraps its solver in a `lambda p: solver(
  p["weights"], ...)`. The generic `algorithms.solve()` dispatcher remains
  as the single source of truth for payload unpacking.
- **Lesson:** trusted code needs the same scrutiny as untrusted code; the
  first crash was in the grader, not the submission.

## Issue 3: "return True" passed the bracket-balance suite

- **Symptom:** during generator review, `bracket_balance` cases were 100%
  balanced strings -- a submission returning a constant `True` scored 16/16.
- **Root cause:** the generator built a balanced string by construction and
  never mutated it. Input distribution bug, not grading bug.
- **Fix:** after building a balanced string, mutate it (~50% of cases) by
  swapping a closer for a wrong one or deleting a character.
- **Lesson:** *every* generator needs a distribution check, not just a
  correctness check. This is now covered by
  `TestGeneratorStatisticalProperties`.

## Issue 4: Docker stdin attach fragility (design-time bug avoided)

- **Symptom (design review):** streaming the case payload over the Docker
  attach-socket required calling `socket._sock.shutdown(2)` -- a private
  attribute -- whose semantics vary across SDK versions.
- **Decision:** replaced stdin streaming with a `case.json` scratch file
  mounted read-only. One line of SDK code, identical for both backends,
  and the untrusted code cannot alter it.
- **See:** `docs/design-decisions.md` §2.
