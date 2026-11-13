#!/usr/bin/env bash
# Sense-path Monte Carlo campaign (T1 item 6, analog): reference-resistor tolerance
# (injected, design-owned) and comparator / mirror offset (PDK MOS mismatch, via
# monte_carlo.mismatch_scale), over the decision-0005 grid (5 process x -40/25/125 C x
# vdd33 2.97/3.30/3.63 V). Two nominal requests at the binding edge of each fuse population
# (intact 260 ohm = A4 upper edge, programmed 630 ohm = A5 lower edge) against the 400 ohm
# reference (A6), plus a deterministic negative control per population with the reference
# skewed to the wrong side of the fuse range. Submitted with `klt sim --batch-set` (batch
# only, never local); job ids land in environment.remote of each report. Then `klt yield`
# (pinned klt, `[yield]` extra) grades each nominal/control pair.
#
# Writes a new append-only record under sim/sense-mc/records/<UTC stamp>-<pdk rev:7>/.
#
#   run.sh [--dry-run]
#
# Exit 0 once the record is written. Pass/fail is data in record.json. A failed batch
# submit exits non-zero and does not fall back to a local grid.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
source "$here/../lib/pdk_env.sh"

bench_parse_args "$@"

pdk_fleet_check || exit 1
lib="$PDK_FLEET_LIB_DIR"

KLT_PIN="$(cat "$repo/signoff/klt-pin.txt")"
KLT_YIELD=(uvx --from "${KLT_PIN%%==*}[yield]==${KLT_PIN##*==}" klt)

# ASSUMPTIONS, recorded verbatim in record.json from this one definition: each is either
# passed to summarize.py below or written into the requests built here and read back
# from them (DECISION_MIN, the corner grid). T_PRE/T_OUT reach the record directory as
# the .meas lines of those requests, not as a record.json field.
RREF_OHM=400                 # A6, decision 0003
RFUSE_INTACT=260             # A4 upper edge (binding for the intact population)
RFUSE_PROG=630               # A5 lower edge (binding for the programmed population)
RREF_CTL_INTACT=200          # control: reference inside the intact range
RREF_CTL_PROG=1000           # control: reference above the programmed range
SIGMA_RREF=0.05              # ASSUMPTION A7: relative 1-sigma of the reference resistor; no documented source
MISMATCH_SCALE=1             # PDK MOS mismatch at its model default (sw_stat_mismatch=1)
SEED=36036
N_NOMINAL=12                 # per corner; 45 corners -> 540 samples per nominal request
N_CONTROL=6                  # per corner; 270 samples per control request
MIN_SAMPLES=200
CI_HALFWIDTH=0.01
DECISION_MIN=0.2             # resolved decision: sense_out/vdd33 at least 0.2 past the 0.5 midpoint (0.7 / 0.3 rails of sim/sense-margin)
T_PRE=14.9n
T_OUT=38n

netlist="$repo/design/efuse_otp_array.spice"
[[ -f "$netlist" ]] || { echo "run.sh: $netlist missing" >&2; exit 1; }
sub() { bench_subckt "$netlist" "$1"; }  # one .subckt block from the committed netlist

# All klt invocations run from the repo root with repo-relative record paths, so the paths
# stored in set-report.json, set-manifest.json and the yield/samples files resolve from any
# checkout (an absolute worktree path does not exist in CI and breaks input verification).
cd "$repo"
bench_new_record_dir "$repo/sim/sense-mc/records" "$dry"
rec="${rec#"$repo/"}"                    # repo-relative (cwd is $repo); a dry-run temp dir is unchanged

reqs=()
# mk <stem> <kind: intact|prog> <rfuse> <rref> <n>
mk() {
  local stem="$1" kind="$2" rf="$3" rr="$4" n="$5" sign
  # The reference is rewritten to carry the klt-injected tolerance multiplier; the committed
  # netlist is untouched. mc_inj_rref_r is emitted per sample by monte_carlo.injected.
  { sed -e "s#@DESIGN@#$lib/design.ngspice#" -e "s#@RFUSE@#$rf#" "$here/../sense-margin/sense.cir.in"
    echo
    sub efuse_sense | sed -e "s#^Rref sref rn1 400 #Rref sref rn1 {$rr*mc_inj_rref_r} #"
    echo
    sub efuse_comp
  } > "$rec/$stem.cir"
  grep -q "^Rref sref rn1 {$rr\*mc_inj_rref_r} " "$rec/$stem.cir" || { echo "run.sh: Rref line not found" >&2; exit 1; }
  if [[ $kind == intact ]]; then   # intact must read below the reference: positive = correct side
    margin="v(xsa.sref)-v(sbl)"; dec="0.5-v(sense_out)/v(vdd33)"
  else
    margin="v(sbl)-v(xsa.sref)"; dec="v(sense_out)/v(vdd33)-0.5"
  fi
  jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
        --arg tpre "$T_PRE" --arg tout "$T_OUT" --arg margin "$margin" --arg dec "$dec" \
        --argjson n "$n" --argjson seed "$SEED" --argjson sigma "$SIGMA_RREF" \
        --argjson ms "$MISMATCH_SCALE" --argjson dmin "$DECISION_MIN" --arg q "'" '
    {netlist:$net, engine:"ngspice",
     models:{lib:$lib, pdk:"gf180mcuD"},
     corners:{process:(["typical","ff","ss","fs","sf"]|map({name:., sections:[.]})),
              supply_v:{vdd33:[2.97,3.30,3.63]}, temperature_c:[-40,25,125]},
     monte_carlo:{n:$n, seed:$seed, vary:"mismatch", seed_scope:"point",
                  mismatch_scale:$ms,
                  injected:[{instance:"Rref", parameter:"r", relative_sigma:$sigma, distribution:"gaussian"}]},
     analysis:{kind:"tran", args:"20p 40n"},
     measurements:[
       {name:"margin_v", spec_row:"P10", unit:"V", limits:{min:0},
        spice:(".meas tran margin_v find par(" + $q + $margin + $q + ") at=" + $tpre)},
       {name:"decision_margin", spec_row:"P10", unit:"V/V", limits:{min:$dmin},
        spice:(".meas tran decision_margin find par(" + $q + $dec + $q + ") at=" + $tout)}],
     options:{timeout_s:60, ngspice_init:["set measureprec=9"]}}' > "$rec/$stem.json"
  reqs+=("$rec/$stem.json")
}
mk mc_intact_rf${RFUSE_INTACT}_rr${RREF_OHM}     intact "$RFUSE_INTACT" "$RREF_OHM"       "$N_NOMINAL"
mk mc_prog_rf${RFUSE_PROG}_rr${RREF_OHM}         prog   "$RFUSE_PROG"   "$RREF_OHM"       "$N_NOMINAL"
mk ctl_intact_rf${RFUSE_INTACT}_rr${RREF_CTL_INTACT} intact "$RFUSE_INTACT" "$RREF_CTL_INTACT" "$N_CONTROL"
mk ctl_prog_rf${RFUSE_PROG}_rr${RREF_CTL_PROG}   prog   "$RFUSE_PROG"   "$RREF_CTL_PROG"  "$N_CONTROL"

if [[ $dry -eq 1 ]]; then
  bench_dry_run "${reqs[@]}"
  rm -rf "$rec"; echo "dry run: request set validated; temp dir removed"; exit 0
fi

# rc: 0 = all pass, 3 = a measurement failed, 4 = partial set (see bench_submit_set).
bench_submit_set "$rec" "${reqs[@]}"

# A partial set (a request refused or errored, e.g. batch_no_capacity) is not evidence:
# stop here, keep the record directory for diagnosis, and never fall back to a local grid.
for q in "${reqs[@]}"; do
  stem="$(basename "$q" .json)"
  [[ -f "$rec/sets/$stem/report.json" ]] || { echo "run.sh: no report for $stem (rc=$rc; see $rec/set-report.json, $rec/klt.err); not a complete set, not evidence" >&2; exit 4; }
done

# Pair each nominal with its control, derive the sample set, grade it.
mkdir -p "$rec/yield"
for pop in intact prog; do
  if [[ $pop == intact ]]; then nom="mc_intact_rf${RFUSE_INTACT}_rr${RREF_OHM}"; ctl="ctl_intact_rf${RFUSE_INTACT}_rr${RREF_CTL_INTACT}"
  else nom="mc_prog_rf${RFUSE_PROG}_rr${RREF_OHM}"; ctl="ctl_prog_rf${RFUSE_PROG}_rr${RREF_CTL_PROG}"; fi
  "${KLT_YIELD[@]}" yield-samples "$rec/sets/$nom/report.json" --negative-control "$rec/sets/$ctl/report.json" \
      --description "reference skewed to the wrong side of the $pop fuse population" \
      --format json > "$rec/yield/$pop.samples.json"
  # Cited report: the analog margin only. The latched-decision measurement is graded in a
  # separate, uncited report: the committed sense-margin record shows the comparator never
  # resolves for a resistive fuse, so its negative control cannot discriminate (see README).
  set +e
  "${KLT_YIELD[@]}" yield "$rec/yield/$pop.samples.json" --measurement margin_v --min-samples "$MIN_SAMPLES" \
      --target-ci-halfwidth "$CI_HALFWIDTH" --format json > "$rec/yield/$pop.yield.json" 2> "$rec/yield/$pop.yield.err"
  echo $? > "$rec/yield/$pop.yield.rc"
  "${KLT_YIELD[@]}" yield "$rec/yield/$pop.samples.json" --measurement decision_margin --min-samples "$MIN_SAMPLES" \
      --target-ci-halfwidth "$CI_HALFWIDTH" --format json > "$rec/yield/$pop.decision.yield.json" 2> "$rec/yield/$pop.decision.yield.err"
  echo $? > "$rec/yield/$pop.decision.yield.rc"
  set -e
done

ngspice_version="$(ngspice -v | sed -n 's/^\*\* ngspice-\([0-9.]*\).*/\1/p' | head -1)"
echo "record: $rec"
python3 -I "$here/summarize.py" "$rec" --pdk-rev "$PDK_REVISION" --stamp "$stamp" \
    --ngspice "$ngspice_version" --klt "$(klt --version)" --klt-pin "$KLT_PIN" \
    --seed "$SEED" --n-nominal "$N_NOMINAL" --n-control "$N_CONTROL" --sigma-rref "$SIGMA_RREF" \
    --mismatch-scale "$MISMATCH_SCALE" --rref "$RREF_OHM" \
    --rfuse-intact "$RFUSE_INTACT" --rfuse-prog "$RFUSE_PROG" \
    --rref-ctl-intact "$RREF_CTL_INTACT" --rref-ctl-prog "$RREF_CTL_PROG" \
    --min-samples "$MIN_SAMPLES" --ci-halfwidth "$CI_HALFWIDTH"
