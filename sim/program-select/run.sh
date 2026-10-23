#!/usr/bin/env bash
# Program-select width sweep: nfet_06v0 select + fuse, PVT grid per decision
# 0005, fuse at 140/200/260 ohm. The grid is a `klt sim` request (corners x
# supply/temperature), one request per (fuse, width) pair, submitted together
# with `klt sim --batch-set` (batch only, never local). The job ids land in
# environment.remote of each report. Writes a new append-only record under
# sim/program-select/records/<UTC stamp>-<pdk rev:7>/. Never overwrites.
#
#   run.sh [--backend local|batch] [--dry-run]
#
# Exit 0 once the record is written. Pass/fail against 10 mA is data in
# record.json, not a script error. A failed batch submit exits non-zero and
# does not fall back to a local grid.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
source "$here/../lib/pdk_env.sh"        # refuses a tree that is not the pin

backend_args=(); dry=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend) backend_args=(--backend "$2"); shift 2 ;;
    --dry-run) dry=1; shift ;;
    *) echo "usage: run.sh [--backend local|batch] [--dry-run]" >&2; exit 2 ;;
  esac
done

# The batch fleet image ships variant gf180mcuD, not the pinned gf180mcuC. The
# model files this bench reads are the same bytes in both at the pinned
# revision; check that at run time and use the D paths so the request is valid
# on either backend. Any difference refuses the run.
libc="$PDK_VARIANT_DIR/libs.tech/ngspice"
lib="$PDK_ROOT/gf180mcuD/libs.tech/ngspice"
for f in sm141064.ngspice sm141064.spice design.ngspice; do
  cmp -s "$libc/$f" "$lib/$f" || { echo "run.sh: $f differs between gf180mcuC and gf180mcuD" >&2; exit 1; }
done
# ASSUMPTIONS, recorded verbatim in record.json (no documented source).
RROUTE_OHM=20
WIDTHS_UM="20 40 60 80 100"
IREQ_A=0.010                             # A2, spec/efuse-otp.md section 2
FUSE_OHMS="140 200 260"                  # A4 range; only 200 ohm is documented
VMAX_RATING=6.0                          # nfet_06v0 label in sm141064.ngspice; no numeric limit found
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
rec="$here/records/$stamp-${PDK_REVISION:0:7}"
mkdir -p "$here/records"
mkdir "$rec"                             # fails if it exists: no overwrite

# Fuse current = drop across the routing resistor / its value (same loop current
# as the fuse). Plain .meas cards, not expr: the fleet runner predates
# measurements[].expr (needs klt 0.7.0) and does not resolve i(vi).
reqs=()
for r in $FUSE_OHMS; do
  if [[ "$r" == 200 ]]; then
    fuse='Xfuse na nb efuse pblow=0'     # PDK efuse subckt (200 ohm)
  else
    fuse="Rfuse na nb $r"                # pblow cannot reach 140/260
  fi
  for w in $WIDTHS_UM; do
    stem="cell_r${r}_w${w}"
    sed -e "s#@DESIGN@#$lib/design.ngspice#" \
        -e "s#@RROUTE@#$RROUTE_OHM#" -e "s#@FUSE@#$fuse#" -e "s#@WSEL@#${w}u#" \
        "$here/cell.cir.in" > "$rec/$stem.cir"
    jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
          --argjson ireq "$IREQ_A" --arg iexpr "(v(nb)-v(d))/$RROUTE_OHM" '
      {netlist:$net, engine:"ngspice",
       models:{lib:$lib, pdk:"gf180mcuD"},
       corners:{process:(["typical","ff","ss","fs","sf"]|map({name:., sections:[., "efuse"]})),
                supply_v:{vdd:[4.5,5.0,5.5]}, temperature_c:[-40,25,125]},
       analysis:{kind:"dc", args:"Vdmy 0 1 1"},
       measurements:[
         {name:"i_fuse", spice:(".meas dc i_fuse find par(\u0027" + $iexpr + "\u0027) at=0"), unit:"A", limits:{min:$ireq}},
         {name:"vgs", spice:".meas dc vgs find v(g) at=0", unit:"V"},
         {name:"vds", spice:".meas dc vds find v(d) at=0", unit:"V"}],
       options:{timeout_s:10}}' > "$rec/$stem.json"
    reqs+=("$rec/$stem.json")
  done
done

if [[ $dry -eq 1 ]]; then
  for q in "${reqs[@]}"; do
    klt sim --dry-run --format json --backend batch "$q" | jq -c '{unit_count,backend,warnings}'
  done
  echo "dry run: $rec holds the generated decks and requests only; delete it"
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
python3 -I "$here/summarize.py" "$rec" --ireq "$IREQ_A" --vmax "$VMAX_RATING" \
    --rroute "$RROUTE_OHM" --pdk-rev "$PDK_REVISION" --stamp "$stamp" \
    --ngspice "$ngspice_version" --klt "$(klt --version)"
