#!/usr/bin/env bash
# Synthesize rtl/efuse_otp_ctrl.v with plain Yosys and assert that no latch
# survives. Output: flow/build/synth.log (gitignored). Exit 0 only if synthesis
# completes and the `select -assert-none` in rtl/latch-assert.ys (script-
# included by rtl/synth.ys) finds no latch cell; on failure Yosys names the
# offending cells and exits non-zero.
#
#   rtl/synth.sh                     the gate, on the committed design
#   rtl/synth.sh --negative-control  the control: synthesize the committed
#                                    latch-bearing fixture through the SAME
#                                    pattern text and pass only if the gate
#                                    fires; log in flow/build/synth-negctl.log
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p flow/build

if [ "${1:-}" = "--negative-control" ]; then
  # The control passes only if Yosys fails with the selection assertion: a
  # clean run means the gate is blind (typo'd patterns), and any other failure
  # (fixture missing or empty, broken script) proves nothing about the gate.
  log=flow/build/synth-negctl.log
  rc=0
  yosys -q -l "$log" rtl/synth-negctl.ys || rc=$?
  if grep -q "selection is not empty" "$log" 2>/dev/null; then
    echo "negative control ok: the latch gate fired on rtl/latch-negative-control.v (yosys exit $rc)"
    exit 0
  fi
  if [ "$rc" -eq 0 ]; then
    echo "negative control FAILED: the fixture synthesized clean; the latch gate did not fire" >&2
  else
    echo "negative control FAILED: yosys exited $rc without firing the latch assertion (fixture missing/empty or broken script); see $log" >&2
  fi
  exit 1
fi

[ $# -eq 0 ] || { echo "usage: rtl/synth.sh [--negative-control]" >&2; exit 2; }
yosys -q -l flow/build/synth.log rtl/synth.ys
