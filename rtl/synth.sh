#!/usr/bin/env bash
# Synthesize rtl/efuse_otp_ctrl.v with plain Yosys and assert that no latch
# survives. Output: flow/build/synth.log (gitignored). Exit 0 only if synthesis
# completes and the `select -assert-none` in rtl/synth.ys finds no latch cell;
# on failure Yosys names the offending cells and exits non-zero.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p flow/build
yosys -q -l flow/build/synth.log rtl/synth.ys
