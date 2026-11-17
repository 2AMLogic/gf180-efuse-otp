#!/usr/bin/env bash
# Place and route the mapped controller netlist rtl/efuse_otp_ctrl.gl.v with the
# pinned klt (never a host-installed one) from layout/pnr-request.json.
#   layout/pnr.sh           run the flow, write layout/pnr-report.json,
#                           layout/efuse_otp_ctrl.gds, layout/efuse_otp_ctrl.asbuilt.v
#                           and layout/efuse_otp_ctrl.gds.sha256. Refuses to write
#                           any of them unless the response is status ok, stage
#                           route, power.pdn true, with zero route DRC and zero
#                           antenna violations.
#   layout/pnr.sh --check   cheap klt --check (input/deck hashes) plus the
#                           committed GDS sha256
#   layout/pnr.sh --check --rerun   full klt --check (re-runs the flow)
# Needs openroad on PATH and the gf180mcuD PDK (PDK_ROOT, default ~/.ciel).
set -euo pipefail
cd "$(dirname "$0")/.."
export PDK="${PDK:-gf180mcuD}" PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
req=layout/pnr-request.json report=layout/pnr-report.json
gds=layout/efuse_otp_ctrl.gds asbuilt=layout/efuse_otp_ctrl.asbuilt.v
if [ "${1:-}" = "--check" ]; then
  shift
  klt place-and-route --check "$report" "$@" "$req"
  (cd layout && sha256sum -c efuse_otp_ctrl.gds.sha256)
  exit 0
fi
out=$(mktemp)
trap 'rm -f "$out"' EXIT
klt place-and-route "$req" --format json > "$out" || { cat "$out" >&2; exit 1; }
python3 -I - "$out" "$report" "$gds" "$asbuilt" <<'PY'
import json, shutil, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "ok", d["status"]
assert d["power"]["pdn"] is True, "power.pdn is not true"
assert d["stage_reached"] == "route", d["stage_reached"]
assert d["route_drc_violation_count"] == 0, d["route_drc_violation_count"]
assert d["antenna_violation_count"] == 0, d["antenna_violation_count"]
shutil.copyfile(sys.argv[1], sys.argv[2])
def src(v):
    return v["path"] if isinstance(v, dict) else v
shutil.copyfile(src(d["gds_path"]), sys.argv[3])
shutil.copyfile(src(d["verilog_path"]), sys.argv[4])
PY
(cd layout && sha256sum efuse_otp_ctrl.gds > efuse_otp_ctrl.gds.sha256)
