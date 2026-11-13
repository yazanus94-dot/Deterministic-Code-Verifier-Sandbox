# Contributing to Deterministic-Code-Verifier-Sandbox

Thank you for considering a contribution. This project has a hard rule:
**the grader must remain deterministic and sandbox-secure.**

## Ground rules

1. **Determinism first.** Any change to case generation, seeds, or grading
   comparison must preserve the property that the same
   `(problem_id, submission)` pair always yields the same verdict.
2. **No weakening of the sandbox.** Do not add network access, broaden the
   static-scan allowlist, or raise default memory/time budgets without a
   documented threat-model analysis in `docs/security.md`.
3. **Type hints everywhere.** `mypy --strict` must pass.
4. **Property tests for algorithms.** New problems must ship a Hypothesis
   property test proving the reference solution's invariants.

## Workflow

```bash
git clone https://github.com/<you>/Deterministic-Code-Verifier-Sandbox
cd Deterministic-Code-Verifier-Sandbox
pip install -r requirements.txt
pip install -e .
ruff check .
mypy src
pytest -v
```

## Commit style

Small, meaningful commits: `fix: cap stdout size to avoid pipe deadlocks`,
`feat: add bracket-balance problem family`, not `update stuff`.

## Pull requests

- Reference the issue if one exists.
- Include before/after behavior in the description.
- All CI checks (ruff, mypy, pytest incl. property tests) must be green.
