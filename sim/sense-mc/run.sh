#!/usr/bin/env bash
# Sense-path Monte Carlo campaign (T1 item 6, analog): reference-resistor tolerance
# (injected, design-owned) and comparator / mirror offset (PDK MOS mismatch, via
# monte_carlo.mismatch_scale), over the decision-0005 grid (5 process x -40/25/125 C x
# vdd33 2.97/3.30/3.63 V). Two nominal requests at the binding edge of each fuse population
# (intact 260 ohm = A4 upper edge, programmed 630 ohm = A5 lower edge) against the 400 ohm
# reference (A6), the same two against the committed physical reference XRref (ppolyf_u),
# plus a deterministic negative control per population with the reference skewed to the
# wrong side of the fuse range. Submitted with `klt sim --batch-set` (batch
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

# Pinned-klt facets for the yield grading below. The helper defines klt()/
# klt_python() unconditionally, but this bench's own klt invocations --
# klt sim, klt --version -- stay on the host klt: drop the functions right
# after sourcing and keep KLT_PIN/KLT_YIELD.
. "$repo/signoff/klt.sh"
unset -f klt klt_python

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

bench_netlist "$repo/design/efuse_otp_array.spice"

# All klt invocations run from the repo root with repo-relative record paths, so the paths
# stored in set-report.json, set-manifest.json and the yield/samples files resolve from any
# checkout (an absolute worktree path does not exist in CI and breaks input verification).
cd "$repo"
bench_new_record_dir "$repo/sim/sense-mc/records" "$dry"
rec="${rec#"$repo/"}"                    # repo-relative (cwd is $repo); a dry-run temp dir is unchanged

reqs=()
# The netlist draws the reference as a PDK ppolyf_u resistor. Two reference dispositions:
# - ideal-stand-in requests inject the reference tolerance as a design-owned multiplier on a
#   plain-R stand-in (A7 below), so the deck copy replaces that one instance with an ideal R
#   carrying {$rr*mc_inj_rref_r} -- the multiplier klt's injected draw feeds. These stay
#   value-parametric by design (their controls sweep the reference value itself).
# - physical-reference requests keep the committed ppolyf_u device and feed its series
#   multiplier s={mc_inj_xrref_s} instead: s scales the terminal resistors (rt1/rt2) and the
#   body resistor (rb) linearly, so the injected tolerance moves the whole physical
#   resistance including its corner-dependent value (injecting the PDK's own mis_r would
#   scale only the body and under-apply the tolerance).
# The bias resistor XRb stays the real device either way, so every deck needs the model
# library's resistor sections (res_typical/res_ss/res_ff) beside the MOS corner; the PDK
# ships no fs/sf resistor section, so those two corners keep the typical sheet rho (same
# assumption as sim/sense-margin/run.sh).
RREF_LINE='^XRref rn1 sref vss ppolyf_u r_width=1.05e-6 r_length=0.8e-6 m=1$'
XRREF_INJ_LINE='XRref rn1 sref vss ppolyf_u r_width=1.05e-6 r_length=0.8e-6 s={mc_inj_xrref_s} m=1'
# mk <stem> <kind: intact|prog> <rfuse> <rref|phys> <n>
mk() {
  local stem="$1" kind="$2" rf="$3" rr="$4" n="$5" inj_inst inj_param sign
  # The reference is rewritten to carry the klt-injected tolerance multiplier; the committed
  # netlist is untouched. mc_inj_rref_r / mc_inj_xrref_s are emitted per sample by
  # monte_carlo.injected.
  { sed -e "s#@DESIGN@#$lib/design.ngspice#" -e "s#@RFUSE@#$rf#" "$here/../sense-margin/sense.cir.in"
    echo
    if [[ "$rr" == phys ]]; then
      sub efuse_sense | sed -e "s#$RREF_LINE#$XRREF_INJ_LINE#"
    else
      sub efuse_sense | sed -e "s#$RREF_LINE#Rref rn1 sref {$rr*mc_inj_rref_r}#"
    fi
    echo
    sub efuse_comp
  } > "$rec/$stem.cir"
  if [[ "$rr" == phys ]]; then
    grep -q "^XRref rn1 sref vss ppolyf_u r_width=1.05e-6 r_length=0.8e-6 s={mc_inj_xrref_s} m=1\$" "$rec/$stem.cir" \
      || { echo "run.sh: physical XRref line not found" >&2; exit 1; }
    inj_inst="XRref"; inj_param="s"
  else
    grep -q "^Rref rn1 sref {$rr\*mc_inj_rref_r}\$" "$rec/$stem.cir" || { echo "run.sh: Rref line not found" >&2; exit 1; }
    inj_inst="Rref"; inj_param="r"
  fi
  if [[ $kind == intact ]]; then   # intact must read below the reference: positive = correct side
    margin="v(xsa.sref)-v(sbl)"; dec="0.5-v(sense_out)/v(vdd33)"
  else
    margin="v(sbl)-v(xsa.sref)"; dec="v(sense_out)/v(vdd33)-0.5"
  fi
  jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
        --arg tpre "$T_PRE" --arg tout "$T_OUT" --arg margin "$margin" --arg dec "$dec" \
        --arg inj_inst "$inj_inst" --arg inj_param "$inj_param" \
        --argjson n "$n" --argjson seed "$SEED" --argjson sigma "$SIGMA_RREF" \
        --argjson ms "$MISMATCH_SCALE" --argjson dmin "$DECISION_MIN" --arg q "'" \
        --argjson pvt_proc "$PVT_PROCESSES" --argjson pvt_temp "$PVT_TEMPERATURES_C" \
        --argjson pvt_3v3 "$PVT_SUPPLY_3V3" '
    {netlist:$net, engine:"ngspice",
     models:{lib:$lib, pdk:"gf180mcuD"},
     corners:{process:($pvt_proc|map({name:.,
              sections:[., ({"typical":"res_typical","ss":"res_ss","ff":"res_ff"}[.] // "res_typical"), "mimcap_typical"]})),
              supply_v:{vdd33:$pvt_3v3}, temperature_c:$pvt_temp},
     monte_carlo:{n:$n, seed:$seed, vary:"mismatch", seed_scope:"point",
                  mismatch_scale:$ms,
                  injected:[{instance:$inj_inst, parameter:$inj_param, relative_sigma:$sigma, distribution:"gaussian"}]},
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
# Physical reference: the same two nominal populations against the committed XRref.
mk mc_intact_rf${RFUSE_INTACT}_rrphys            intact "$RFUSE_INTACT" phys              "$N_NOMINAL"
mk mc_prog_rf${RFUSE_PROG}_rrphys                prog   "$RFUSE_PROG"   phys              "$N_NOMINAL"

if [[ $dry -eq 1 ]]; then
  bench_dry_run_exit "${reqs[@]}"
fi

# rc: 0 = all pass, 3 = a measurement failed, 4 = partial set (see bench_submit_set).
bench_submit_set "$rec" "${reqs[@]}"

# A partial set (a request refused or errored, e.g. batch_no_capacity) is not evidence:
# stop here, keep the record directory for diagnosis, and never fall back to a local grid.
for q in "${reqs[@]}"; do
  stem="$(basename "$q" .json)"
  [[ -f "$rec/sets/$stem/report.json" ]] || { echo "run.sh: no report for $stem (rc=$rc; see $rec/set-report.json, $rec/klt.err); not a complete set, not evidence" >&2; exit 4; }
done

# Pair each nominal with its control, derive the sample set, grade it. The physical-
# reference nominals are paired with the same value-skewed controls as their ideal
# counterparts: the controls are value-parametric (200/1000 ohm skew) and validate both
# populations' measurement and decision paths.
mkdir -p "$rec/yield"
for pop in intact prog; do
  for mode in "" "_phys"; do
    if [[ $pop == intact ]]; then rf="$RFUSE_INTACT"; ctl="ctl_intact_rf${RFUSE_INTACT}_rr${RREF_CTL_INTACT}"
    else rf="$RFUSE_PROG"; ctl="ctl_prog_rf${RFUSE_PROG}_rr${RREF_CTL_PROG}"; fi
    if [[ -z "$mode" ]]; then nom="mc_${pop}_rf${rf}_rr${RREF_OHM}"
    else nom="mc_${pop}_rf${rf}_rrphys"; fi
    out="$pop$mode"
    "${KLT_YIELD[@]}" yield-samples "$rec/sets/$nom/report.json" --negative-control "$rec/sets/$ctl/report.json" \
        --description "reference skewed to the wrong side of the $pop fuse population" \
        --format json > "$rec/yield/$out.samples.json"
    # Cited report: the analog margin only (margin_v, the ratified row's limit). The latched-
    # decision measurement is graded in a separate report that block-manifest.json does not
    # cite; see README for what each record measured (the latch resolves on the committed DUT,
    # resized under issue 77). Whether that split should change is a signoff decision, not this
    # script's to state a reason for.
    set +e
    "${KLT_YIELD[@]}" yield "$rec/yield/$out.samples.json" --measurement margin_v --min-samples "$MIN_SAMPLES" \
        --target-ci-halfwidth "$CI_HALFWIDTH" --format json > "$rec/yield/$out.yield.json" 2> "$rec/yield/$out.yield.err"
    echo $? > "$rec/yield/$out.yield.rc"
    "${KLT_YIELD[@]}" yield "$rec/yield/$out.samples.json" --measurement decision_margin --min-samples "$MIN_SAMPLES" \
        --target-ci-halfwidth "$CI_HALFWIDTH" --format json > "$rec/yield/$out.decision.yield.json" 2> "$rec/yield/$out.decision.yield.err"
    echo $? > "$rec/yield/$out.decision.yield.rc"
    set -e
  done
done

echo "record: $rec"
python3 -I "$here/summarize.py" "$rec" --pdk-rev "$PDK_REVISION" --stamp "$stamp" \
    --klt "$(klt --version)" --klt-pin "$KLT_PIN" --physical-reference \
    --seed "$SEED" --n-nominal "$N_NOMINAL" --n-control "$N_CONTROL" --sigma-rref "$SIGMA_RREF" \
    --mismatch-scale "$MISMATCH_SCALE" --rref "$RREF_OHM" \
    --rfuse-intact "$RFUSE_INTACT" --rfuse-prog "$RFUSE_PROG" \
    --rref-ctl-intact "$RREF_CTL_INTACT" --rref-ctl-prog "$RREF_CTL_PROG" \
    --min-samples "$MIN_SAMPLES" --ci-halfwidth "$CI_HALFWIDTH"
