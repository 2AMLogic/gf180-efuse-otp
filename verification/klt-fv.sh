#!/usr/bin/env bash
# Regenerate the committed `klt functional-verification` reports for the
# controller bench, one per parameter set. This is a thin wrapper: the run is
# verification/run.sh, the same single path CI gates on, with CONFIGS in
# runner.py as the single source of parameter sets.
#   verification/klt-fv.sh [outdir]   reports go to outdir (default sim/controller-fv)
# Exit 0 iff every parameter set passes.
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-sim/controller-fv}"
mkdir -p "$out"
exec verification/run.sh --reports "$(cd "$out" && pwd)"
