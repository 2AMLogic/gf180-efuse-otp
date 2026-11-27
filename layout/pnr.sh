#!/usr/bin/env bash
# Place and route the mapped controller netlist rtl/efuse_otp_ctrl.gl.v with the
# pinned klt (never a host-installed one) from layout/pnr-request.json.
#   layout/pnr.sh           publish the P&R report, routed DEF, as-built netlist, filled
#                           controller GDS, GDS checksum and fill-ctrl.report.json.
#                           Requires status ok, route reached, PDN present,
#                           and zero route DRC and antenna violations. Keep
#                           the verbatim response for the 0.0005 um P&R stream.
#                           Export at 0.001 um (#311) and check density (#310)
#                           before replacing the published files.
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
gds=layout/efuse_otp_ctrl.gds
if [ "${1:-}" = "--check" ]; then
  shift
  klt place-and-route --check "$report" "$@" "$req"
  (cd layout && sha256sum -c efuse_otp_ctrl.gds.sha256)
  klt_python -I layout/dbu_export.py --assert-dbu "$gds"
  exit 0
fi
out=$(mktemp -d layout/.pnr.XXXXXXXX)
trap 'rm -rf "$out"' EXIT
klt place-and-route "$req" --format json > "$out/pnr-report.json" || { cat "$out/pnr-report.json" >&2; exit 1; }
python3 -I - "$out/pnr-report.json" "$out" <<'PY'
import json, shutil, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "ok", d["status"]
assert d["power"]["pdn"] is True, "power.pdn is not true"
assert d["stage_reached"] == "route", d["stage_reached"]
assert d["route_drc_violation_count"] == 0, d["route_drc_violation_count"]
assert d["antenna_violation_count"] == 0, d["antenna_violation_count"]
def src(v):
    return v["path"] if isinstance(v, dict) else v
shutil.copyfile(src(d["def_path"]), f"{sys.argv[2]}/efuse_otp_ctrl.def")
shutil.copyfile(src(d["gds_path"]), f"{sys.argv[2]}/intermediate.gds")
shutil.copyfile(src(d["verilog_path"]), f"{sys.argv[2]}/efuse_otp_ctrl.asbuilt.v")
PY
# Checked final export at the foundry database unit: klt 0.9.2 emits 0.0005 um
# and its output_dbu_um refines only (2AMLogic/klayout-tools#4482), so the 2:1
# coarsening runs here -- exact for every even coordinate, with the property-1
# single-pin net markers re-drawn on the 0.001 um grid inside their pin metal.
# Any other odd coordinate fails with its cell and layer and nothing below is
# written: no report, no stream, no sidecar.
klt_python -I layout/dbu_export.py --pin-markers "$out/intermediate.gds" "$out/routed.gds"
klt_python -I layout/fill_partitions.py --input "$out/routed.gds" --output "$out/efuse_otp_ctrl.gds" \
  --report "$out/fill-ctrl.report.json" --top efuse_otp_ctrl >/dev/null
(cd "$out" && sha256sum efuse_otp_ctrl.gds > efuse_otp_ctrl.gds.sha256)

# All producer checks passed. Each staged file is on the destination filesystem.
mv "$out/pnr-report.json" "$out/efuse_otp_ctrl.def" "$out/efuse_otp_ctrl.asbuilt.v" "$out/efuse_otp_ctrl.gds" \
   "$out/efuse_otp_ctrl.gds.sha256" "$out/fill-ctrl.report.json" layout/
