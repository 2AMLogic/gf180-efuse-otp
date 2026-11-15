#!/usr/bin/env bash
# Standalone multi-corner STA of the routed controller with the pinned klt.
#   sta/run.sh [outdir]   reports go to outdir (default sim/controller-sta)
# Regenerates nothing: needs the routed DEF from `layout/pnr.sh`
# (layout/.klt/place-and-route/efuse_otp_ctrl.def, gitignored) and openroad on
# PATH. Reports every request in sta/; exit 0 iff the two functional requests
# (sta-100ns, sta-10ns) are clean at every corner. The negative control
# (sta-negative-control-1ns) must show negative slack, else exit 1.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
export PDK="${PDK:-gf180mcuD}" PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"
out="${1:-sim/controller-sta}"
mkdir -p "$out"
def=layout/.klt/place-and-route/efuse_otp_ctrl.def
[ -f "$def" ] || { echo "$def missing: run layout/pnr.sh first" >&2; exit 2; }
rc=0
for n in sta-100ns sta-10ns sta-negative-control-1ns; do
  klt sta "sta/$n.json" --format json > "$out/$n.report.json"
  python3 -I - "$out/$n.report.json" "$n" <<'PY' || rc=1
import json, sys
d = json.load(open(sys.argv[1])); name = sys.argv[2]
neg = name.startswith("sta-negative")
ok = d["status"] == "ok" and d["geometry_source"] == "routed"
for c in d["corners"]:
    s, h = c["worst_slack_ns"], c["worst_hold_slack_ns"]
    print(f'{name} {c["corner"]} {c["timing_status"]} setup={s} hold={h}')
    ok &= c["timing_status"] == "constrained"
    ok &= (s < 0) if neg else (s >= 0 and h >= 0)
sys.exit(0 if ok else 1)
PY
done
exit $rc
