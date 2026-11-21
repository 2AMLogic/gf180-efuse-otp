#!/usr/bin/env bash
# Place and route the mapped controller netlist rtl/efuse_otp_ctrl.gl.v with the
# pinned klt (never a host-installed one) from layout/pnr-request.json.
#   layout/pnr.sh           run the flow, write layout/pnr-report.json,
#                           layout/efuse_otp_ctrl.gds, layout/efuse_otp_ctrl.asbuilt.v
#                           and layout/efuse_otp_ctrl.gds.sha256. Refuses to write
#                           any of them unless the response is status ok, stage
#                           route, power.pdn true, with zero route DRC and zero
#                           antenna violations, and unless the final export below
#                           succeeds. The report stays the verbatim response and
#                           is truthful about the flow's intermediate stream
#                           (0.0005 um, layout/.klt/ scratch); the committed
#                           efuse_otp_ctrl.gds is the final stream, coarsened to
#                           the foundry 0.001 um database unit (issue #311) by
#                           layout/dbu_export.py, which the sidecar and
#                           layout/pnr.attest.json bind.
#   layout/pnr.sh --check   cheap klt --check (input/deck hashes), the
#                           committed GDS sha256, and its declared dbu
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
  klt_python -I layout/dbu_export.py --assert-dbu "$gds"
  exit 0
fi
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
klt place-and-route "$req" --format json > "$out/response.json" || { cat "$out/response.json" >&2; exit 1; }
python3 -I - "$out/response.json" "$out" <<'PY'
import json, shutil, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "ok", d["status"]
assert d["power"]["pdn"] is True, "power.pdn is not true"
assert d["stage_reached"] == "route", d["stage_reached"]
assert d["route_drc_violation_count"] == 0, d["route_drc_violation_count"]
assert d["antenna_violation_count"] == 0, d["antenna_violation_count"]
def src(v):
    return v["path"] if isinstance(v, dict) else v
shutil.copyfile(src(d["gds_path"]), f"{sys.argv[2]}/intermediate.gds")
shutil.copyfile(src(d["verilog_path"]), f"{sys.argv[2]}/asbuilt.v")
PY
# Checked final export at the foundry database unit: klt 0.9.2 emits 0.0005 um
# and its output_dbu_um refines only (2AMLogic/klayout-tools#4482), so the 2:1
# coarsening runs here -- exact for every even coordinate, with the property-1
# single-pin net markers re-drawn on the 0.001 um grid inside their pin metal.
# Any other odd coordinate fails with its cell and layer and nothing below is
# written: no report, no stream, no sidecar.
klt_python -I layout/dbu_export.py --pin-markers "$out/intermediate.gds" "$out/final.gds"
cp "$out/response.json" "$report"
cp "$out/final.gds" "$gds"
cp "$out/asbuilt.v" "$asbuilt"
(cd layout && sha256sum efuse_otp_ctrl.gds > efuse_otp_ctrl.gds.sha256)
