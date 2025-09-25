#!/usr/bin/env bash
set -euo pipefail

shopt -s nullglob globstar

mapfile -t test_files < <(printf '%s\n' tests/**/*.py tests/*.py 2>/dev/null || true)

if (( ${#test_files[@]} > 0 )); then
  echo "Running pytest on ${#test_files[@]} test file(s)..."
  python -m pytest -q
else
  echo "No tests found under ./tests. Skipping pytest."
fi
