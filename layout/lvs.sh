#!/usr/bin/env bash
# Run `klt lvs` with the pinned klt (never a host-installed one) on the digital
# partition (layout/efuse_otp_ctrl.gds against the as-built gate-level netlist)
# and on the routed efuse_ls cell (top of layout/efuse_otp_array.gds against its
# .subckt in design/efuse_otp_array.spice), keeping the JSON reports as
# committed evidence.
#   layout/lvs.sh           rewrite layout/lvs-ctrl.report.json and
#                           layout/lvs-ls.report.json
#   layout/lvs.sh --check   klt lvs --check on the committed report (input and
#                           deck hashes still match; add --rerun to re-run the
#                           compare)
# klt exits 3 when a compare does not match; that is a finding, not a script
# failure, so the verdict is printed and the report is kept as found.
# The ctrl part needs the PDK, unlike drc.sh or the ls part: the gate-level
# reference resolves each standard cell's pin order from the library's own
# spice/cdl under <PDK_ROOT>/gf180mcuD/libs.ref, so CI (which installs no PDK)
# cannot run it. PDK_ROOT defaults to ~/.ciel, layout/pnr.sh's default; the
# root is passed to klt explicitly so the report records one resolved install
# instead of an ambiguous search. Requests are fed on stdin from the repo
# root, so their relative paths resolve there and stay portable in the
# committed reports.
set -euo pipefail
cd "$(dirname "$0")/.."
export PDK="${PDK:-gf180mcuD}" PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
parts=(ctrl:efuse_otp_ctrl ls:efuse_ls)
if [ "${1:-}" = "--check" ]; then
  shift
  for p in "${parts[@]}"; do
    klt lvs --check "layout/lvs-${p%%:*}.report.json" "$@"
  done
  exit 0
fi
for p in "${parts[@]}"; do
  part=${p%%:*} top=${p##*:}
  out=$(mktemp)
  rc=0
  # ctrl: the routed controller against its as-built gate-level netlist (needs
  # the PDK: the reference resolves each standard cell's pin order from the
  # library's own spice/cdl). ls: the routed efuse_ls cell, extracted from the
  # analog stream (top efuse_ls), against its .subckt in the analog netlist --
  # simulation form (X cards calling PDK device subcircuits), which
  # reference.form "subckt-call" converts; no PDK or library needed.
  if [ "$part" = ctrl ]; then
    req=$(cat <<REQ
{
  "layout": { "file": "layout/${top}.gds", "top": "$top", "deck": "gf180mcu",
              "abstract_cells": "gf180mcu_fd_sc_mcu7t5v0__*" },
  "reference": { "netlist": "layout/${top}.asbuilt.v",
                 "form": "gate-level-verilog",
                 "library": "gf180mcu_fd_sc_mcu7t5v0",
                 "pdk": "${PDK}",
                 "pdk_root": "${PDK_ROOT}",
                 "top": "$top" },
  "options": { "power_connectivity": { "expected_nets": {
               "VDD": "VDD", "VNW": "VDD", "VPW": "VSS", "VSS": "VSS" } } },
  "portable_paths": true
}
REQ
)
  else
    req=$(cat <<REQ
{
  "layout": { "file": "layout/efuse_otp_array.gds", "top": "$top", "deck": "gf180mcu" },
  "reference": { "netlist": "design/efuse_otp_array.spice",
                 "form": "subckt-call",
                 "top": "$top" },
  "options": { "anchor_top_level_pins": true },
  "portable_paths": true
}
REQ
)
  fi
  klt lvs - --format json > "$out" <<< "$req" || rc=$?
  [ "$rc" = 0 ] || [ "$rc" = 3 ] || { cat "$out" >&2; rm -f "$out"; exit "$rc"; }
  cp "$out" "layout/lvs-$part.report.json"
  rm -f "$out"
  python3 -I - "layout/lvs-$part.report.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
pc = d.get("power_connectivity", {})
cov = d.get("coverage", {})
print(f'{sys.argv[1]}: status={d["status"]} '
      f'mismatches={d.get("mismatch_count")} '
      f'power={pc.get("status")} engine={d.get("engine")} '
      f'not_recognized={len(cov.get("declared_not_recognized", []))} '
      f'input={d["provenance"]["input"]["content_hash"]}')
PY
done
