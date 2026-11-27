#!/usr/bin/env bash
# Run `klt lvs` with the pinned klt (never a host-installed one) on the digital
# partition (layout/efuse_otp_ctrl.gds against the as-built gate-level netlist)
# and on the routed analog cells efuse_ls, efuse_rowdrv, efuse_coldrv,
# efuse_comp, efuse_sense, efuse_bitcell, efuse_row and the array top
# efuse_otp_array (each a top of layout/efuse_otp_array.gds, against
# design/efuse_otp_array.spice), keeping the JSON reports as committed evidence.
#   layout/lvs.sh           rewrite layout/lvs-ctrl.report.json,
#                           layout/lvs-ls.report.json,
#                           layout/lvs-rowdrv.report.json,
#                           layout/lvs-coldrv.report.json,
#                           layout/lvs-comp.report.json,
#                           layout/lvs-sense.report.json,
#                           layout/lvs-bitcell.report.json,
#                           layout/lvs-row.report.json and
#                           layout/lvs-array-probe.report.json
#   layout/lvs.sh --check   klt lvs --check on the committed report (input and
#                           deck hashes still match; add --rerun to re-run the
#                           compare)
# The analog parts' --rerun is klt's own. The ctrl part's cannot be: its
# report records reference_conversion.pdk_root as the "$PDK_ROOT" portable
# token (the request sets portable_paths: true), and pinned klt's
# --check --rerun copies that token back into its reconstructed request
# verbatim, so the PDK search resolves it as a cwd-relative path and the rerun
# dies before the compare (klayout-tools#7589). --check --rerun therefore
# keeps klt's cheap hash gate, regenerates a fresh portable report in scratch
# from the same shared request (the PDK root resolved from this invocation's
# environment, so the replay works at the default or any relocated root), and
# diffs it against the committed evidence with the pinned klt's own
# verdict-field exclusion set -- status, the power_connectivity verdict, the
# stream/reference hashes, the pin-order library evidence and
# environment.engine_version all stay compared. The committed reports are
# never touched by a check.
# klt exits 3 when a compare does not match; that is a finding, not a script
# failure, so the verdict is printed and the report is kept as found. The
# ls/rowdrv/coldrv/comp/sense parts end in status: match; the bitcell/row parts
# end in status: mismatch whose every discrepancy is the missing fuse model (no
# fuse device in the curated deck, no efuse subckt in the design netlist) -- see
# layout/README.md, "efuse_bitcell / efuse_row LVS probes".
# The ctrl part needs the PDK, unlike the ls part: the gate-level
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
parts=(ctrl:efuse_otp_ctrl ls:efuse_ls rowdrv:efuse_rowdrv coldrv:efuse_coldrv
       comp:efuse_comp sense:efuse_sense bitcell:efuse_bitcell row:efuse_row
       array-probe:efuse_otp_array)

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# The ctrl request, shared by the record loop and --check --rerun's fresh
# regeneration so a replay re-runs exactly the recorded compare: the PDK root
# is resolved from this invocation's environment, never from the committed
# report's "$PDK_ROOT" token.
ctrl_request() {
  cat <<REQ
{
  "layout": { "file": "layout/efuse_otp_ctrl.gds", "top": "efuse_otp_ctrl",
              "deck": "gf180mcu",
              "abstract_cells": "gf180mcu_fd_sc_mcu7t5v0__*" },
  "reference": { "netlist": "layout/efuse_otp_ctrl.asbuilt.v",
                 "form": "gate-level-verilog",
                 "library": "gf180mcu_fd_sc_mcu7t5v0",
                 "pdk": "${PDK}",
                 "pdk_root": "${PDK_ROOT}",
                 "top": "efuse_otp_ctrl" },
  "options": { "power_connectivity": { "expected_nets": {
               "VDD": "VDD", "VNW": "VDD", "VPW": "VSS", "VSS": "VSS" } } },
  "portable_paths": true
}
REQ
}

# One-line verdict summary of a klt lvs report; LABEL names the run (the
# committed report for a record, the committed name again for a replay).
summarize() {
  python3 -I - "$1" "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[2]))
pc = d.get("power_connectivity", {})
cov = d.get("coverage", {})
print(f'{sys.argv[1]}: status={d["status"]} '
      f'mismatches={d.get("mismatch_count")} '
      f'power={pc.get("status")} engine={d.get("engine")} '
      f'not_recognized={len(cov.get("declared_not_recognized", []))} '
      f'input={d["provenance"]["input"]["content_hash"]}')
PY
}

check=false
rerun=false
check_args=()
if [ "${1:-}" = "--check" ]; then
  check=true
  shift
  for arg in "$@"; do
    if [ "$arg" = "--rerun" ]; then rerun=true; else check_args+=("$arg"); fi
  done
fi

for p in "${parts[@]}"; do
  part=${p%%:*} top=${p##*:}
  report="layout/lvs-$part.report.json"
  if "$check"; then
    if [ "$part" != ctrl ]; then
      klt lvs --check "$report" "$@"
      continue
    fi
    # ctrl: cheap hash gate first (no PDK needed), then, with --rerun, the
    # regeneration + verdict-field diff klt's own --rerun cannot do.
    klt lvs --check "$report" "${check_args[@]}"
    "$rerun" || continue
    rc=0
    klt lvs - --format json > "$tmp/lvs-ctrl.json" <<< "$(ctrl_request)" || rc=$?
    [ "$rc" = 0 ] || [ "$rc" = 3 ] || { cat "$tmp/lvs-ctrl.json" >&2; exit "$rc"; }
    summarize "$report (rerun)" "$tmp/lvs-ctrl.json"
    klt_python - "$report" "$tmp/lvs-ctrl.json" <<'PY'
import json, sys
from klayout_tools._report_verify import diff_verdict_fields
from klayout_tools.lvs import _LVS_RERUN_EXCLUDE_PATHS

committed = json.load(open(sys.argv[1]))
fresh = json.load(open(sys.argv[2]))
diffs = diff_verdict_fields(committed, fresh, exclude=_LVS_RERUN_EXCLUDE_PATHS)
for d in diffs:
    print(f'[DRIFT] {d["field"]}: {d["committed"]!r} (report) '
          f'vs {d["fresh"]!r} (rerun)')
if diffs:
    sys.exit(3)
print('[OK] rerun verdict fields match the committed report')
PY
    continue
  fi
  # ctrl: the routed controller against its as-built gate-level netlist (needs
  # the PDK: the reference resolves each standard cell's pin order from the
  # library's own spice/cdl). ls/comp: the routed cell, extracted from the
  # analog stream (top efuse_ls / efuse_comp), against its .subckt in the
  # analog netlist -- simulation form (X cards calling PDK device
  # subcircuits), which reference.form "subckt-call" converts; no PDK or
  # library needed.
  # rowdrv/coldrv/sense: same, but the reference is flattened under the top
  # (options.flatten_reference keeps only the top circuit) -- efuse_ls in the
  # drivers, efuse_comp in sense, is compared as its devices, not as a
  # hierarchical instance -- and combine_devices merges parallel devices on
  # both sides: the reference's m=3 Mdrv (three W=100 copies), the layout's
  # three 10-finger units and the folded W=60 select's six fingers each meet
  # as one device each side. sense additionally sets reference.deck and
  # options.compare_parameters so the netlist's ppolyf_u resistor calls
  # convert against the deck's device table and their R (deck-derived from
  # the stated r_length/r_width) is compared against the extracted strips'
  # geometry-derived R.
  if [ "$part" = ctrl ]; then
    req="$(ctrl_request)"
  elif [ "$part" = array-probe ]; then
    # Top-level probe: xschem writes the top header as commented
    # `**.subckt efuse_otp_array` / `**.ends`, so KLayout's SPICE reader places
    # the 73 top-level instances (32 rows, 32 row drivers, 8 column drivers,
    # 1 sense block) into its implicit `.TOP` circuit with 0 declared pins
    # (klayout-tools#7918). Compare with reference.top=".TOP", flattened and
    # combined, plus ppolyf_u R comparison (same as sense). Separately named
    # from any future item-4 analog match report (#32).
    req=$(cat <<REQ
{
  "layout": { "file": "layout/efuse_otp_array.gds", "top": "$top", "deck": "gf180mcu" },
  "reference": { "netlist": "design/efuse_otp_array.spice",
                 "form": "subckt-call",
                 "deck": "gf180mcu",
                 "top": ".TOP" },
  "options": { "anchor_top_level_pins": true,
               "flatten_reference": [".TOP"],
               "combine_devices": true,
               "compare_parameters": { "ppolyf_u": ["R"] } },
  "portable_paths": true
}
REQ
)
  elif [ "$part" = sense ]; then
    req=$(cat <<REQ
{
  "layout": { "file": "layout/efuse_otp_array.gds", "top": "$top", "deck": "gf180mcu",
              "declared_pins": ["sbl", "sense_en", "clk", "sense_out", "vdd33", "vprog", "vss"] },
  "reference": { "netlist": "design/efuse_otp_array.spice",
                 "form": "subckt-call",
                 "deck": "gf180mcu",
                 "top": "$top" },
  "options": { "anchor_top_level_pins": true,
               "flatten_reference": ["$top"],
               "combine_devices": ["nfet", "pfet"],
               "compare_parameters": { "ppolyf_u": ["R"], "cap_mim_2f0_m4m5_noshield": ["A", "P"] } },
  "portable_paths": true
}
REQ
)
  else
    opts='{ "anchor_top_level_pins": true }'
    case "$part" in
      rowdrv|coldrv|bitcell|row) opts="{ \"anchor_top_level_pins\": true, \"flatten_reference\": [\"$top\"], \"combine_devices\": true }" ;;
    esac
    req=$(cat <<REQ
{
  "layout": { "file": "layout/efuse_otp_array.gds", "top": "$top", "deck": "gf180mcu" },
  "reference": { "netlist": "design/efuse_otp_array.spice",
                 "form": "subckt-call",
                 "top": "$top" },
  "options": $opts,
  "portable_paths": true
}
REQ
)
  fi
  rc=0
  klt lvs - --format json > "$tmp/report.json" <<< "$req" || rc=$?
  [ "$rc" = 0 ] || [ "$rc" = 3 ] || { cat "$tmp/report.json" >&2; exit "$rc"; }
  cp "$tmp/report.json" "$report"
  summarize "$report" "$report"
done
