#!/usr/bin/env bash
set -euo pipefail

shopt -s nullglob globstar

# Discover files that match pytest's default naming
mapfile -t test_files < <(printf '%s\n' \
  tests/**/test_*.py tests/**/**/*_test.py \
  tests/test_*.py tests/*_test.py 2>/dev/null || true)

if (( ${#test_files[@]} > 0 )); then
  echo "Running pytest on ${#test_files[@]} test file(s)..."
  # Allow pytest to return nonzero
  set +e
  python -m pytest -q
  pytest_exit=$?
  set -e
  if [[ "$pytest_exit" -eq 5 ]]; then
    echo "Pytest exited with code 5 (no tests collected). Treating as success."
    exit 0
  fi
  exit "$pytest_exit"
else
  echo "No tests found under ./tests. Skipping pytest."
fi
