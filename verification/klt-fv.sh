#!/usr/bin/env bash
# Run the controller cocotb bench through `klt functional-verification` (pinned
# klt, never the host one), one request per parameter set. CONFIGS in runner.py
# is the single source: `runner.py --emit-klt-requests` writes the requests and
# lists each set's expected pulse/settle counts, which the bench reads from the
# environment (as runner.py sets them).
#   verification/klt-fv.sh [outdir]   reports go to outdir (default sim/controller-fv)
# Exit 0 iff every parameter set passes. Needs iverilog on PATH; cocotb is
# supplied to klt's throwaway environment from verification/requirements.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-sim/controller-fv}"
mkdir -p "$out"
klt() { uvx --from "$(cat signoff/klt-pin.txt)" --with-requirements verification/requirements.txt klt "$@"; }
req="$(mktemp -d)"
trap 'rm -rf "$req"' EXIT
rows="$(python3 -I verification/runner.py --emit-klt-requests "$req")"
rc=0
# name rows cols expected-pulse-cycles expected-settle-cycles
while read -r name rows cols pulse settle; do
  EFUSE_ROWS=$rows EFUSE_COLS=$cols EFUSE_PULSE_N=$pulse EFUSE_SETTLE_N=$settle \
    klt functional-verification "$req/fv-$name.json" \
      -o "$out/$name" --format json > "$out/$name.report.json" || rc=1
  python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[2], d["status"], str(d["passed_count"]) + "/" + str(d["test_count"]))' "$out/$name.report.json" "$name"
done <<<"$rows"
exit $rc
