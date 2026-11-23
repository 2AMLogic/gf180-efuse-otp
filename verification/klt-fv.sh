#!/usr/bin/env bash
# Regenerate `klt functional-verification` reports for the controller bench,
# one per parameter set, into an explicitly named directory. This is a thin
# wrapper: the run is verification/run.sh, the same single path CI gates on,
# with CONFIGS in runner.py as the single source of parameter sets.
#   verification/klt-fv.sh <outdir>   reports go to outdir (required, created if missing)
# Exit 0 iff every parameter set passes.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$#" -eq 0 ] || [ -z "${1:-}" ]; then
  echo "usage: verification/klt-fv.sh <outdir>" >&2
  echo "outdir is required: regenerate to a temporary directory to compare," >&2
  echo "never over the committed reports in sim/controller-fv" >&2
  exit 1
fi
out="$1"
mkdir -p "$out"
exec verification/run.sh --reports "$(cd "$out" && pwd)"
