#!/usr/bin/env bash
# Sense break-even bench: programmed-resistance sweep through the committed
# efuse_sense subcircuit, to find the fuse resistance at which the sense margin
# crosses zero (issue 389). Same deck, same decision-0005 grid (5 process x
# -40/25/125 C x vdd33 2.97/3.30/3.63 V) and same measurements as
# sim/sense-margin, but the fuse stand-in is swept 300..540 ohm in 40 ohm steps,
# against (a) the ideal 400 ohm reference (A6) and (b) the committed physical
# XRref (ppolyf_u). Submitted with `klt sim --batch-set` (batch only, never
# local), --wait-for-capacity 600. Writes a new append-only record under
# sim/sense-breakeven/records/<UTC stamp>-<pdk rev:7>/. Never overwrites.
#
#   run.sh [--dry-run]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
source "$here/../lib/pdk_env.sh"
bench_parse_args "$@"
pdk_fleet_check || exit 1
lib="$PDK_FLEET_LIB_DIR"

SWEEP_OHMS="300 340 380 420 460 500 540"   # brackets the 328..472 ohm physical-reference estimate
RREF_OHM=400                                # A6, decision 0003
T_EDGE=15n; T_PRE=14.9n; T_OUT=38n

bench_netlist "$repo/design/efuse_otp_array.spice"
bench_new_record_dir "$here/records" "$dry"

reqs=()
RREF_LINE='^XRref rn1 sref vss ppolyf_u r_width=1.05e-6 r_length=0.8e-6 m=1$'
mk() {                                   # mk <stem> <rfuse> <rref|phys>
  local stem="$1" rf="$2" rr="$3"
  { sed -e "s#@DESIGN@#$lib/design.ngspice#" -e "s#@RFUSE@#$rf#" "$here/../sense-margin/sense.cir.in"
    echo
    if [[ "$rr" == phys ]]; then sub efuse_sense; else sub efuse_sense | sed -e "s#$RREF_LINE#Rref rn1 sref $rr#"; fi
    echo
    sub efuse_comp
  } > "$rec/$stem.cir"
  if [[ "$rr" == phys ]]; then
    grep -q "^XRref rn1 sref vss ppolyf_u " "$rec/$stem.cir" || { echo "run.sh: physical XRref not found in efuse_sense" >&2; exit 1; }
  else
    grep -q "^Rref rn1 sref $rr\$" "$rec/$stem.cir" || { echo "run.sh: Rref line not found in efuse_sense" >&2; exit 1; }
  fi
  jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
        --arg tpre "$T_PRE" --arg tout "$T_OUT" \
        --argjson pvt_proc "$PVT_PROCESSES" --argjson pvt_temp "$PVT_TEMPERATURES_C" \
        --argjson pvt_3v3 "$PVT_SUPPLY_3V3" '
    {netlist:$net, engine:"ngspice",
     models:{lib:$lib, pdk:"gf180mcuD"},
     corners:{process:($pvt_proc|map({name:.,
              sections:[., ({"typical":"res_typical","ss":"res_ss","ff":"res_ff"}[.] // "res_typical")]})),
              supply_v:{vdd33:$pvt_3v3}, temperature_c:$pvt_temp},
     analysis:{kind:"tran", args:"20p 40n"},
     measurements:[
       {name:"v_sbl", spice:(".meas tran v_sbl find v(sbl) at=" + $tpre), unit:"V"},
       {name:"v_sref", spice:(".meas tran v_sref find v(xsa.sref) at=" + $tpre), unit:"V"},
       {name:"v_sense_out", spice:(".meas tran v_sense_out find v(sense_out) at=" + $tout), unit:"V"},
       {name:"v_cp", spice:(".meas tran v_cp find v(xsa.cp) at=" + $tout), unit:"V"},
       {name:"v_cn", spice:(".meas tran v_cn find v(xsa.cn) at=" + $tout), unit:"V"}],
     options:{timeout_s:60, ngspice_init:["set measureprec=9"]}}' > "$rec/$stem.json"
  reqs+=("$rec/$stem.json")
}
for r in $SWEEP_OHMS; do mk "ideal_rf${r}_rr${RREF_OHM}" "$r" "$RREF_OHM"; done
for r in $SWEEP_OHMS; do mk "phys_rf${r}_rrphys" "$r" phys; done

if [[ $dry -eq 1 ]]; then bench_dry_run_exit "${reqs[@]}"; fi

bench_submit_set "$rec" "${reqs[@]}"
echo "record: $rec"
python3 -I "$here/summarize.py" "$rec" --rref "$RREF_OHM" --rfuse "$SWEEP_OHMS" \
    --t-pre "$T_PRE" --t-out "$T_OUT" --t-edge "$T_EDGE" \
    --pdk-rev "$PDK_REVISION" --stamp "$stamp" --klt "$(klt --version)"
