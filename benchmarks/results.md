# Benchmark Results

Measured on the reference machine (Windows 11, Python 3.14, Docker Desktop
29.9.3 / linux engine, 2026-11-12). All numbers are medians via
`time.perf_counter` over repeated runs (`benchmarks/benchmark.py`).
They are reproducible; absolute values will shift on other hardware.

## 1. Reference-solver scaling (host-side ground-truth computation)

| Solver | Input size | Median time |
|---|---|---|
| `two_sum_reference` (hash map) | n = 200,000 | **0.031 s** |
| `knapsack_reference` (bottom-up DP) | n = 500, capacity = 400 | **0.012 s** |
| `dijkstra_reference` (heap) | n = 5,000, ≈25k edges | **0.0045 s** |
| `lcs_length_reference` (2-row DP) | 2,000 × 2,000 | **0.55 s** |
| `bracket_balance_reference` (stack) | 1,000 chars | **0.5 µs** |

All reference solvers run comfortably inside the 5 s grading budget even at
these sizes, leaving headroom for the sandbox round-trip itself.

## 2. End-to-end grading cost

| Path | Cost |
|---|---|
| Subprocess backend, one case round-trip | **0.086 s** |
| Subprocess backend, full verify (16 randomized cases) | **1.33 s** |
| Docker backend, one case round-trip (container create+run+remove) | **0.65 s** |
| Docker backend, extrapolated full verify (16 cases) | ≈10.4 s |

## 3. Interpretation

- The **container security premium is ≈0.56 s/case** vs. subprocess mode.
  That premium buys network isolation, kernel OOM enforcement and CPU
  quotas -- a fair price for grading *hostile* code.
- For interactive grading at scale the 16-case suite completes in
  ~1.3 s (subprocess) / ~10 s (containers). Batching cases into one
  container per submission (single create, N harness runs) would cut the
  Docker path roughly 10x and is listed under future improvements.
- LCS dominates the solver table at large inputs; the 2-row memory
  optimization keeps it at O(min(m,n)) space, trading ~15% of the naive
  implementation's speed for a 1000x memory reduction at 2000×2000.
