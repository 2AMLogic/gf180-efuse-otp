#!/usr/bin/env bash
# Sense-margin bench: the committed efuse_sense subcircuit against a resistor
# standing in for the selected fuse, over the decision-0005 corner grid
# (5 process x -40/25/125 C x vdd33 2.97/3.30/3.63 V). One `klt sim` request per
# fuse value (intact 140/200/260 ohm = A4, programmed 630/900/open = A5), all
# against the 400 ohm reference (A6), plus a negative control with the reference
# moved inside the intact range. Each request declares margin_v >= 0 (signed: positive
# is the correct side of the reference, so the grader sees a limit) as a klt limit; the
# negative control carries the same limit and must read fail. The set is submitted with `klt sim --batch-set`
# (batch only, never local); job ids land in environment.remote of each report.
# Writes a new append-only record under sim/sense-margin/records/<UTC stamp>-<pdk
# rev:7>/. Never overwrites.
#
#   run.sh [--dry-run]
#
# Exit 0 once the record is written. Pass/fail is data in record.json, not a
# script error. A failed batch submit exits non-zero and does not fall back to a
# local grid; a submit that left any of the expected reports missing or
# without corners exits 4 from summarize.py without writing a record, because a
# partial set is not evidence. --dry-run validates the request set with `klt sim
# --dry-run` and deletes nothing it did not create (no record; it uses a temp dir).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
source "$here/../lib/pdk_env.sh"        # refuses a tree that is not the pin

bench_parse_args "$@"

# Same fleet-image rule as sim/program-select/run.sh: the fleet ships gf180mcuD,
# the pin is gf180mcuC; the model files read here must be byte-identical.
pdk_fleet_check || exit 1
lib="$PDK_FLEET_LIB_DIR"

# ASSUMPTIONS, recorded verbatim in record.json (only 200 and 900 ohm are documented).
INTACT_OHMS="140 200 260"                # A4
PROGRAMMED_OHMS="630 900 open"           # A5; open = 1 Gohm
RREF_OHM=400                             # A6, decision 0003
RREF_CONTROL_OHM=200                     # negative control: reference inside the intact range
RFUSE_CONTROL_OHMS="140 260"             # the intact values re-read against RREF_CONTROL_OHM
T_EDGE=15n                               # clock edge; bias and sbl/sref settle before it
T_PRE=14.9n                              # margin read, just before the edge
T_OUT=38n                                # latched sense_out read

bench_netlist "$repo/design/efuse_otp_array.spice"

bench_new_record_dir "$here/records" "$dry"

reqs=()
# The netlist draws the reference as a PDK ppolyf_u resistor; this bench is a
# value-parametric study (its controls sweep the reference value itself), so
# the deck copy replaces that one instance with a plain R at the swept value --
# the same standing as the rfuse stand-in above. The bias resistor XRb stays
# the real device, so every deck needs the model library's resistor sections
# (res_typical/res_ss/res_ff) beside the MOS corner; the PDK ships no fs/sf
# resistor section, so those two corners keep the typical sheet rho (A8).
RREF_LINE='^XRref rn1 sref vss ppolyf_u r_width=1.05e-6 r_length=0.8e-6 m=1$'
mk() {                                   # mk <stem> <rfuse> <rref|phys> <sign>
  local stem="$1" rf="$2" rr="$3" sgn="$4" val="$2"   # sgn: +1 programmed (sbl > sref), -1 intact
  [[ "$rf" == open ]] && val=1G
  { sed -e "s#@DESIGN@#$lib/design.ngspice#" -e "s#@RFUSE@#$val#" "$here/sense.cir.in"
    echo
    if [[ "$rr" == phys ]]; then      # keep the committed ppolyf_u XRref
      sub efuse_sense
    else
      sub efuse_sense | sed -e "s#$RREF_LINE#Rref rn1 sref $rr#"
    fi
    echo
    sub efuse_comp
  } > "$rec/$stem.cir"
  if [[ "$rr" == phys ]]; then
    grep -q "^XRref rn1 sref vss ppolyf_u " "$rec/$stem.cir" || { echo "run.sh: physical XRref not found in efuse_sense" >&2; exit 1; }
  else
    grep -q "^Rref rn1 sref $rr\$" "$rec/$stem.cir" || { echo "run.sh: Rref line not found in efuse_sense" >&2; exit 1; }
  fi
  jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
        --arg tpre "$T_PRE" --arg tout "$T_OUT" --arg sgn "$sgn" \
        --argjson pvt_proc "$PVT_PROCESSES" --argjson pvt_temp "$PVT_TEMPERATURES_C" \
        --argjson pvt_3v3 "$PVT_SUPPLY_3V3" '
    {netlist:$net, engine:"ngspice",
     models:{lib:$lib, pdk:"gf180mcuD"},
     corners:{process:($pvt_proc|map({name:.,
              sections:[., ({"typical":"res_typical","ss":"res_ss","ff":"res_ff"}[.] // "res_typical")]})),
              supply_v:{vdd33:$pvt_3v3}, temperature_c:$pvt_temp},
     analysis:{kind:"tran", args:"20p 40n"},  # 100p under-resolves the 200p edge: decisions flipped with the step (issue 77)
     measurements:[
       {name:"margin_v", spice:(".meas tran margin_v find par(\u0027" + $sgn + "*(v(sbl)-v(xsa.sref))\u0027) at=" + $tpre), unit:"V", limits:{min:0}},
       {name:"v_sbl", spice:(".meas tran v_sbl find v(sbl) at=" + $tpre), unit:"V"},
       {name:"v_sref", spice:(".meas tran v_sref find v(xsa.sref) at=" + $tpre), unit:"V"},
       {name:"v_sense_out", spice:(".meas tran v_sense_out find v(sense_out) at=" + $tout), unit:"V"},
       {name:"v_cp", spice:(".meas tran v_cp find v(xsa.cp) at=" + $tout), unit:"V"},
       {name:"v_cn", spice:(".meas tran v_cn find v(xsa.cn) at=" + $tout), unit:"V"},
       {name:"v_vdd33", spice:(".meas tran v_vdd33 find v(vdd33) at=" + $tout), unit:"V"}],
     options:{timeout_s:60, ngspice_init:["set measureprec=9"]}}' > "$rec/$stem.json"
  reqs+=("$rec/$stem.json")
}
for r in $INTACT_OHMS; do mk "bench_rf${r}_rr${RREF_OHM}" "$r" "$RREF_OHM" -1; done
for r in $PROGRAMMED_OHMS; do mk "bench_rf${r}_rr${RREF_OHM}" "$r" "$RREF_OHM" 1; done
# Physical reference: the same fuse values with the committed XRref left in the deck.
for r in $INTACT_OHMS; do mk "phys_rf${r}_rrphys" "$r" phys -1; done
for r in $PROGRAMMED_OHMS; do mk "phys_rf${r}_rrphys" "$r" phys 1; done
for r in $RFUSE_CONTROL_OHMS; do mk "control_rf${r}_rr${RREF_CONTROL_OHM}" "$r" "$RREF_CONTROL_OHM" -1; done

if [[ $dry -eq 1 ]]; then
  bench_dry_run_exit "${reqs[@]}"
fi

# rc: 0 = all pass, 3 = a measurement failed, 4 = partial set (see bench_submit_set).
bench_submit_set "$rec" "${reqs[@]}"

echo "record: $rec"
python3 -I "$here/summarize.py" "$rec" --rref "$RREF_OHM" --rref-control "$RREF_CONTROL_OHM" \
    --rfuse-intact "$INTACT_OHMS" --rfuse-programmed "$PROGRAMMED_OHMS" \
    --rfuse-control "$RFUSE_CONTROL_OHMS" --physical-reference \
    --t-pre "$T_PRE" --t-out "$T_OUT" --t-edge "$T_EDGE" \
    --pdk-rev "$PDK_REVISION" --stamp "$stamp" \
    --klt "$(klt --version)"
