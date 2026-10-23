#!/usr/bin/env bash
# Cold-start runner for the controller bench.
#   verification/run.sh                    run every parameter set (32x8 and 1x8,
#                                          min/nominal/max pulse width)
#   verification/run.sh --negative-control run deliberately broken RTL variants;
#                                          exit 0 only if every one is caught
# Needs: python3 with venv + network for the first `pip install` (cocotb is
# pinned in requirements.txt and installed into verification/.venv, never
# into the host), and Icarus Verilog / Yosys of the versions below.
set -euo pipefail
cd "$(dirname "$0")"

EXPECT_IVERILOG="13.0"
EXPECT_YOSYS="0.67"

ver_iv=$(iverilog -V 2>/dev/null | head -1 | sed -n 's/.*version \([0-9.]*\).*/\1/p')
ver_ys=$(yosys -V 2>/dev/null | sed -n 's/^Yosys \([0-9]*\.[0-9]*\).*/\1/p')
if [ "${ALLOW_TOOL_MISMATCH:-0}" != 1 ]; then
  [ "$ver_iv" = "$EXPECT_IVERILOG" ] || { echo "iverilog $ver_iv found, $EXPECT_IVERILOG required (ALLOW_TOOL_MISMATCH=1 to override)" >&2; exit 2; }
  [ "$ver_ys" = "$EXPECT_YOSYS" ] || { echo "yosys $ver_ys found, $EXPECT_YOSYS required (ALLOW_TOOL_MISMATCH=1 to override)" >&2; exit 2; }
fi

if [ ! -x .venv/bin/python ] || ! cmp -s requirements.txt .venv/requirements.installed; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --quiet -r requirements.txt
  cp requirements.txt .venv/requirements.installed
fi

exec .venv/bin/python -I runner.py "$@"
