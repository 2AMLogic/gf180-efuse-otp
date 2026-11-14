#!/usr/bin/env bash
# Cold-start runner for the controller bench.
#   verification/run.sh                    run every parameter set (32x8 and 1x8,
#                                          min/nominal/max pulse width)
#   verification/run.sh --negative-control run deliberately broken RTL variants;
#                                          exit 0 only if every one is caught
#   verification/run.sh --reports DIR      keep each set's klt report in DIR
# The bench runs through `klt functional-verification` from the pinned klt
# (signoff/klt-pin.txt); the pinned cocotb (requirements.txt) is supplied to
# klt's throwaway environment, never installed into the host.
# Needs: python3 (standard library only), uv on PATH, network for the first
# klt/cocotb fetch, and Icarus Verilog of the version below.
set -euo pipefail
cd "$(dirname "$0")"

EXPECT_IVERILOG="13.0"

ver_iv=$(iverilog -V 2>/dev/null | head -1 | sed -n 's/.*version \([0-9.]*\).*/\1/p')
if [ "${ALLOW_TOOL_MISMATCH:-0}" != 1 ]; then
  [ "$ver_iv" = "$EXPECT_IVERILOG" ] || { echo "iverilog $ver_iv found, $EXPECT_IVERILOG required (ALLOW_TOOL_MISMATCH=1 to override)" >&2; exit 2; }
fi

command -v uvx >/dev/null 2>&1 || { echo "uvx not found; the pinned klt in signoff/klt-pin.txt is reached through it" >&2; exit 2; }

exec python3 -I runner.py "$@"
