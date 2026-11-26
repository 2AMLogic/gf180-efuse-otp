#!/usr/bin/env bash
# Standalone multi-corner STA of the routed controller with the pinned klt.
#   sta/run.sh [outdir]   reports go to outdir (default sim/controller-sta)
# Uses the retained controller DEF and OpenROAD on PATH. The 100 ns target requires nonnegative setup and hold at every
# available library corner. The 10 ns headroom run reports slack of either
# sign. The 1 ns negative control must violate setup at every corner.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
export PDK="${PDK:-gf180mcuD}" PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"
out="${1:-sim/controller-sta}"
mkdir -p "$out"
python3 -I sta/check_route.py
rc=0
for n in sta-100ns sta-10ns sta-negative-control-1ns; do
  klt sta "sta/$n.json" --format json > "$out/$n.report.json"
  python3 -I - "$out/$n.report.json" "$n" <<'PY' || rc=1
import json
import math
import sys

path, name = sys.argv[1:]
with open(path) as stream:
    report = json.load(stream)
with open(f"sta/{name}.json") as stream:
    expected = json.load(stream)["pdk"]["corners"]
corners = report["corners"]
ok = report["status"] == "ok" and report["geometry_source"] == "routed"
ok &= sorted(c["corner"] for c in corners) == sorted(expected)
for corner in corners:
    setup = corner["worst_slack_ns"]
    hold = corner["worst_hold_slack_ns"]
    print(f'{name} {corner["corner"]} {corner["timing_status"]} setup={setup} hold={hold}')
    ok &= corner["timing_status"] == "constrained"
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (setup, hold)):
        ok = False
        continue
    if name == "sta-100ns":
        ok &= setup >= 0 and hold >= 0
    elif name == "sta-negative-control-1ns":
        ok &= setup < 0
sys.exit(0 if ok else 1)
PY
done
exit $rc
