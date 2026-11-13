# Verification Strategy

The grader's job is to *prove* correctness, not to spot-check it. The
strategy has four legs; each closes a hole the previous ones leave open.

## 1. Public examples (smoke tests) -- weak on purpose

Fixed inputs like `two_sum([3,-1,7,11,2], 10)`. Any submission that read
the examples can hard-code them. These exist only to fail fast on
syntax errors and obviously broken code.

## 2. Randomized hidden cases -- the workhorse

For a given `(problem_id, submission)` the engine derives
`seed = SHA-256(problem_id || submission)[:8]`, then generates
`len(salts) * cases_per_seed` (default 16) inputs from
`random.Random(seed ^ salt)` streams and grades every one against the
reference solver.

- **Randomized** ⇒ hard-coded answers survive with vanishing probability
  (see the acceptance calculation below).
- **Seeded** ⇒ the exact same 16 cases are regenerated on every machine;
  the verdict is a pure function of the submission text.

### Why a cheat cannot pass

A constant answer matches the expected value for case *c* with probability
≈ 1/|answer space|. For `two_sum`, the answer space is every valid index
pair over a 4–24 element array -- thousands of possibilities per case.
Passing all 16 cases requires winning that lottery 16 times independently;
for a randomized DP or graph problem the space is combinatorially larger.

## 3. Property-based reference tests (Hypothesis)

The reference solvers are themselves untrusted until proven otherwise.
Each one is cross-checked against an *independent* oracle on arbitrary
generated inputs:

| Reference solver | Independent oracle |
|---|---|
| `two_sum_reference` | direct pair-existence check + validity invariants |
| `knapsack_reference` | exhaustive `O(2^n)` brute force |
| `bracket_balance_reference` | independent depth-counter model |
| `lcs_length_reference` | naive recursive LCS |
| `dijkstra_reference` | Bellman-Ford cross-check |

## 4. Adversarial submissions

The test suite ships purpose-built cheats and asserts rejection:

- `return (0, 1)` -- constant index pair (`tests/property/test_properties.py`).
- Constant numeric answers for knapsack.
- **Sample-memorizing solver** -- returns the correct LCS only for the
  public example strings, a plausible answer after seeing samples; must be
  rejected by the hidden case set.
- Five escape-payload families (network, subprocess, filesystem, ctypes,
  dynamic import) asserting the static scanner never regresses.

## What "deterministic" means here, precisely

Same submission + same problem on two different machines, two different
days ⇒ identical 16 cases, identical expected values, identical verdict.
Nothing in the pipeline reads the clock, entropy, hostname, or locale.
