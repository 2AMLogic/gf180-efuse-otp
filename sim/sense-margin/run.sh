#!/usr/bin/env bash
# Sense-margin bench: the committed efuse_sense subcircuit against a resistor
# standing in for the selected fuse, over the decision-0005 corner grid
# (5 process x -40/25/125 C x vdd33 2.97/3.30/3.63 V). One `klt sim` request per
# fuse value (intact 140/200/260 ohm = A4, programmed 630/900/open = A5), all
# against the 400 ohm reference (A6), plus a negative control with the reference
# moved inside the intact range. The set is submitted with `klt sim --batch-set`
# (batch only, never local); job ids land in environment.remote of each report.
# Writes a new append-only record under sim/sense-margin/records/<UTC stamp>-<pdk
# rev:7>/. Never overwrites.
#
#   run.sh [--dry-run]
#
# Exit 0 once the record is written. Pass/fail is data in record.json, not a
# script error. A failed batch submit exits non-zero and does not fall back to a
# local grid. --dry-run validates the request set with `klt sim --dry-run` and
# deletes nothing it did not create (it leaves no record; it uses a temp dir).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
source "$here/../lib/pdk_env.sh"        # refuses a tree that is not the pin

dry=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry=1; shift ;;
    *) echo "usage: run.sh [--dry-run]" >&2; exit 2 ;;
  esac
done

# Same fleet-image rule as sim/program-select/run.sh: the fleet ships gf180mcuD,
# the pin is gf180mcuC; the model files read here must be byte-identical.
libc="$PDK_VARIANT_DIR/libs.tech/ngspice"
lib="$PDK_ROOT/gf180mcuD/libs.tech/ngspice"
for f in sm141064.ngspice sm141064.spice design.ngspice; do
  cmp -s "$libc/$f" "$lib/$f" || { echo "run.sh: $f differs between gf180mcuC and gf180mcuD" >&2; exit 1; }
done

# ASSUMPTIONS, recorded verbatim in record.json (only 200 and 900 ohm are documented).
INTACT_OHMS="140 200 260"                # A4
PROGRAMMED_OHMS="630 900 open"           # A5; open = 1 Gohm
RREF_OHM=400                             # A6, decision 0003
RREF_CONTROL_OHM=200                     # negative control: reference inside the intact range
T_EDGE=15n                               # clock edge; bias and sbl/sref settle before it
T_PRE=14.9n                              # margin read, just before the edge
T_OUT=38n                                # latched sense_out read

netlist="$repo/design/efuse_otp_array.spice"
[[ -f "$netlist" ]] || { echo "run.sh: $netlist missing" >&2; exit 1; }
sub() {                                  # print one .subckt ... .ends block from the committed netlist
  awk -v n="$1" '$1==".subckt" && $2==n {p=1} p {print} p && $1==".ends" {exit}' "$netlist"
}

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ $dry -eq 1 ]]; then
  rec="$(mktemp -d)"
else
  rec="$here/records/$stamp-${PDK_REVISION:0:7}"
  mkdir -p "$here/records"
  mkdir "$rec"                           # fails if it exists: no overwrite
fi

reqs=()
mk() {                                   # mk <stem> <rfuse> <rref>
  local stem="$1" rf="$2" rr="$3" val="$2"
  [[ "$rf" == open ]] && val=1G
  { sed -e "s#@DESIGN@#$lib/design.ngspice#" -e "s#@RFUSE@#$val#" "$here/sense.cir.in"
    echo
    sub efuse_sense | sed -e "s#^Rref sref rn1 400 #Rref sref rn1 $rr #"
    echo
    sub efuse_comp
  } > "$rec/$stem.cir"
  grep -q "^Rref sref rn1 $rr " "$rec/$stem.cir" || { echo "run.sh: Rref line not found in efuse_sense" >&2; exit 1; }
  jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
        --arg tpre "$T_PRE" --arg tout "$T_OUT" '
    {netlist:$net, engine:"ngspice",
     models:{lib:$lib, pdk:"gf180mcuD"},
     corners:{process:(["typical","ff","ss","fs","sf"]|map({name:., sections:[.]})),
              supply_v:{vdd33:[2.97,3.30,3.63]}, temperature_c:[-40,25,125]},
     analysis:{kind:"tran", args:"100p 40n"},
     measurements:[
       {name:"v_sbl", spice:(".meas tran v_sbl find v(sbl) at=" + $tpre), unit:"V"},
       {name:"v_sref", spice:(".meas tran v_sref find v(xsa.sref) at=" + $tpre), unit:"V"},
       {name:"v_sense_out", spice:(".meas tran v_sense_out find v(sense_out) at=" + $tout), unit:"V"},
       {name:"v_cp", spice:(".meas tran v_cp find v(xsa.cp) at=" + $tout), unit:"V"},
       {name:"v_cn", spice:(".meas tran v_cn find v(xsa.cn) at=" + $tout), unit:"V"},
       {name:"v_vdd33", spice:(".meas tran v_vdd33 find v(vdd33) at=" + $tout), unit:"V"}],
     options:{timeout_s:60, ngspice_init:["set measureprec=9"]}}' > "$rec/$stem.json"
  reqs+=("$rec/$stem.json")
}
for r in $INTACT_OHMS $PROGRAMMED_OHMS; do mk "bench_rf${r}_rr${RREF_OHM}" "$r" "$RREF_OHM"; done
for r in 140 260; do mk "control_rf${r}_rr${RREF_CONTROL_OHM}" "$r" "$RREF_CONTROL_OHM"; done

if [[ $dry -eq 1 ]]; then
  for q in "${reqs[@]}"; do
    klt sim --dry-run --format json --backend batch "$q" | jq -c '{unit_count,backend,warnings}'
  done
  rm -rf "$rec"
  echo "dry run: request set validated; temp dir removed"
  exit 0
fi

# 0 = all pass, 3 = some measurement failed, 4 = a request errored or was
# refused (partial set). Anything else is a tool failure. A failed or refused
# submit is reported, never re-run on local ngspice.
set +e
klt sim --batch-set "${reqs[@]}" --max-in-flight 4 --capacity-retries 3 \
    -o "$rec/sets" --format json > "$rec/set-report.json" 2> "$rec/klt.err"
rc=$?
set -e
if [[ $rc -ne 0 && $rc -ne 3 && $rc -ne 4 ]]; then
  echo "klt sim --batch-set failed (rc=$rc); see $rec/klt.err" >&2
  exit "$rc"
fi

ngspice_version="$(ngspice -v | sed -n 's/^\*\* ngspice-\([0-9.]*\).*/\1/p' | head -1)"
echo "record: $rec"
python3 -I "$here/summarize.py" "$rec" --rref "$RREF_OHM" --rref-control "$RREF_CONTROL_OHM" \
    --rfuse-intact "$INTACT_OHMS" --rfuse-programmed "$PROGRAMMED_OHMS" \
    --t-pre "$T_PRE" --t-out "$T_OUT" --t-edge "$T_EDGE" \
    --pdk-rev "$PDK_REVISION" --stamp "$stamp" \
    --ngspice "$ngspice_version" --klt "$(klt --version)"
