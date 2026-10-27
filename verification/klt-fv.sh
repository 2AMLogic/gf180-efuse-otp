#!/usr/bin/env bash
# Run the controller cocotb bench through `klt functional-verification` (pinned
# klt, never the host one), one request per parameter set in verification/klt/.
#   verification/klt-fv.sh [outdir]   reports go to outdir (default sim/controller-fv)
# The bench reads its expected pulse/settle counts from the environment (as
# runner.py sets them), so the expectations below mirror runner.py CONFIGS.
# Exit 0 iff every parameter set passes. Needs iverilog on PATH; cocotb is
# supplied to klt's throwaway environment from verification/requirements.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-sim/controller-fv}"
mkdir -p "$out"
klt() { uvx --from "$(cat signoff/klt-pin.txt)" --with-requirements verification/requirements.txt klt "$@"; }
rc=0
# name rows cols expected-pulse-cycles expected-settle-cycles
while read -r name rows cols pulse settle; do
  EFUSE_ROWS=$rows EFUSE_COLS=$cols EFUSE_PULSE_N=$pulse EFUSE_SETTLE_N=$settle \
    klt functional-verification "verification/klt/fv-$name.json" \
      -o "$out/$name" --format json > "$out/$name.report.json" || rc=1
  python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[2], d["status"], str(d["passed_count"]) + "/" + str(d["test_count"]))' "$out/$name.report.json" "$name"
done <<'ROWS'
32x8_min 32 8 10 4
32x8_nom 32 8 100 4
32x8_max 32 8 1000 4
1x8_min 1 8 10 4
1x8_nom 1 8 100 4
1x8_max 1 8 1000 1
32x8_clamp_lo 32 8 10 7
32x8_clamp_hi 32 8 1000 4
32x8_100MHz_max 32 8 10000 4
ROWS
exit $rc
