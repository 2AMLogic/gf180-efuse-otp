#!/usr/bin/env bash
# Program-current corner verification (spec row P06 / claim C1): the real program
# path from design/efuse_otp_array.spice (column driver + level shifter, row driver
# + level shifter, 60 um select) delivering current into a selected cell, over the
# decision-0005 grid: 5 process x -40/25/125 C x three supply pairs (vdd33, vprog) of
# (2.97, 4.5), (3.30, 5.0), (3.63, 5.5) V -- 45 corners per request -- fuse 140/200/260
# ohm. The two supplies step together (`klt sim` zips the supply_v axes) and are not
# crossed, so mixed supply combinations are not covered. One `klt sim`
# request per fuse value plus a negative control (select narrowed to 4 um), submitted
# together with `klt sim --batch-set` (batch only, never local). Job ids land in
# environment.remote of each report. Writes a new append-only record under
# sim/corner-verification/records/<UTC stamp>-<pdk rev:7>/. Never overwrites.
# The sense-margin row is NOT re-run here; it is cited from sim/sense-margin/records/.
#
#   run.sh [--dry-run]
#
# Exit 0 once the record is written. Pass/fail against 10 mA is data in record.json,
# not a script error. A failed batch submit exits non-zero and does not fall back to
# a local grid. --dry-run validates the request set with `klt sim --dry-run` and
# leaves no record (it uses a temp dir).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
source "$here/../lib/pdk_env.sh"        # refuses a tree that is not the pin

bench_parse_args "$@"

# Same fleet-image rule as sim/program-select/run.sh (fleet ships gf180mcuD, pin is C).
pdk_fleet_check || exit 1
lib="$PDK_FLEET_LIB_DIR"

# ASSUMPTIONS, recorded verbatim in record.json (no documented source).
RROUTE_OHM=20                            # same lumped value as sim/program-select
IREQ_A=0.010                             # A2, spec/efuse-otp.md section 2
FUSE_OHMS="140 200 260"                  # A4; only 200 ohm is documented
W_CONTROL=4u                             # negative control: select narrowed from 60u

netlist="$repo/design/efuse_otp_array.spice"
[[ -f "$netlist" ]] || { echo "run.sh: $netlist missing" >&2; exit 1; }
sub() { bench_subckt "$netlist" "$1"; }  # one .subckt block from the committed netlist

bench_new_record_dir "$here/records" "$dry"

reqs=()
mk() {                                   # mk <stem> <fuse ohm> <select width|keep>
  local stem="$1" r="$2" w="$3" cell efuse=false
  cell="$(sub efuse_bitcell)"
  if [[ "$r" != 200 ]]; then             # the PDK efuse model is 200 ohm only
    cell="$(sed -e "s#^XXf bl n efuse pblow=0#RXf bl n $r#" <<<"$cell")"
    grep -q "^RXf bl n $r\$" <<<"$cell" || { echo "run.sh: XXf line not found in efuse_bitcell" >&2; exit 1; }
  else
    efuse=true                           # PDK efuse subckt lives in the `efuse` model section
  fi
  if [[ "$w" != keep ]]; then
    cell="$(sed -e "/^XXsel /s# W=60u # W=$w #" <<<"$cell")"
    grep -q "^XXsel .* W=$w " <<<"$cell" || { echo "run.sh: XXsel width not found in efuse_bitcell" >&2; exit 1; }
  fi
  { sed -e "s#@DESIGN@#$lib/design.ngspice#" -e "s#@RROUTE@#$RROUTE_OHM#" "$here/program.cir.in"
    echo; echo "$cell"
    echo; sub efuse_rowdrv
    echo; sub efuse_coldrv
    echo; sub efuse_ls
  } > "$rec/$stem.cir"
  jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
        --argjson ireq "$IREQ_A" --arg r "$r" --argjson efuse "$efuse" '
    {netlist:$net, engine:"ngspice",
     models:{lib:$lib, pdk:"gf180mcuD"},
     corners:{process:(["typical","ff","ss","fs","sf"]|map({name:., sections:([.] + (if $efuse then ["efuse"] else [] end))})),
              supply_v:{vdd33:[2.97,3.30,3.63], vprog:[4.5,5.0,5.5]}, temperature_c:[-40,25,125]},
     analysis:{kind:"dc", args:"Vdmy 0 1 1"},
     measurements:[
       {name:"i_fuse", spice:(".meas dc i_fuse find par(\u0027(v(blc)-v(xcell.n))/" + $r + "\u0027) at=0"), unit:"A", limits:{min:$ireq}},
       {name:"v_wl", spice:".meas dc v_wl find v(wl) at=0", unit:"V"},
       {name:"v_bl", spice:".meas dc v_bl find v(bl) at=0", unit:"V"},
       {name:"v_sel_d", spice:".meas dc v_sel_d find v(xcell.n) at=0", unit:"V"}],
     options:{timeout_s:30}}' > "$rec/$stem.json"
  reqs+=("$rec/$stem.json")
}
for r in $FUSE_OHMS; do mk "prog_rf${r}" "$r" keep; done
mk "control_rf260_w${W_CONTROL}" 260 "$W_CONTROL"

if [[ $dry -eq 1 ]]; then
  bench_dry_run "${reqs[@]}"
  rm -rf "$rec"
  echo "dry run: request set validated; temp dir removed"
  exit 0
fi

# rc: 0 = all pass, 3 = a measurement failed, 4 = partial set (see bench_submit_set).
bench_submit_set "$rec" "${reqs[@]}"

echo "record: $rec"
python3 -I "$here/summarize.py" "$rec" --ireq "$IREQ_A" --rroute "$RROUTE_OHM" \
    --fuse-ohms "$FUSE_OHMS" --w-control "$W_CONTROL" \
    --pdk-rev "$PDK_REVISION" --stamp "$stamp" \
    --klt "$(klt --version)"
