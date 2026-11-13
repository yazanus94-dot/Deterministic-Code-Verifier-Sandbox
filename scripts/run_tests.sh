#!/usr/bin/env bash
set -euo pipefail
pytest tests/unit tests/property -v
pytest tests/integration -v --timeout=120 2>/dev/null || pytest tests/integration -v
pytest --cov=verifier_sandbox --cov-report=term-missing
