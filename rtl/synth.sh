#!/usr/bin/env bash
# Synthesize rtl/efuse_otp_ctrl.v with plain Yosys and report the latch count.
# Output: flow/build/synth.log (gitignored). Exit 0 only if synthesis completes
# and the log shows "Number of latches: 0".
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p flow/build
yosys -q -l flow/build/synth.log rtl/synth.ys >/dev/null
# `stat` lists every cell type; count any latch cell types it reports.
n=$(awk '/\$_?[A-Za-z]*DLATCH|\$_?[A-Za-z]*LATCH|\$dlatch/ {s+=$1} END {print s+0}' flow/build/synth.log)
echo "Number of latches: $n" | tee -a flow/build/synth.log
[ "$n" -eq 0 ]
