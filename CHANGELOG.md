# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-11-12

### Added
- `VerifierEngine`: deterministic grading of untrusted submissions via
  seeded randomized case sets derived from `SHA-256(problem_id, submission)`.
- `DockerSandbox`: containerized execution with network disabled, 256 MB
  memory cap, 0.5 CPU quota, and read-only scratch mounts.
- `SubprocessSandbox`: non-isolated fallback for hosts without Docker.
- Static scanner rejecting network, process, filesystem, and dynamic-eval
  escape attempts before any execution.
- Five problem families (two_sum, knapsack, shortest_path, lcs_length,
  bracket_balance) with optimal reference solutions.
- Property-based test suite (Hypothesis) proving the verifier rejects
  hard-coded and partially-hard-coded solutions.
- Docker Compose services for the verifier, test suite, and benchmark.
- GitHub Actions CI (lint, type-check, tests with coverage artifact).
