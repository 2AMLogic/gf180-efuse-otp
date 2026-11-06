#!/usr/bin/env bash
# Print one issue-77 comparator probe deck on stdout (single-corner; run it with
# `ngspice -b`). All probes are probe.cir.in with a few fields overridden; the
# per-probe overrides are the table below. README.md says what each probe shows.
#
#   gen_probe.sh <name>      print the deck
#   gen_probe.sh --list      list probe names
#
# The PDK library directory comes from sim/lib/pdk_env.sh (the pinned tree).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

# name: corner rfuse pair_W pair_L latch_W tran_step meas title_prefix
# meas: clk = clkn/tail check; trace = sbl/sref time trace before the edge.
declare -A T=(
  [probe_rf260]="typical 260 8u 0.28u 2u 100p clk -"
  [probe_rf630]="typical 630 8u 0.28u 2u 100p clk -"
  [v_mx8_260]="typical 260 8u 0.28u 8u 100p clk -"
  [v_mx8_630]="typical 630 8u 0.28u 8u 100p clk -"
  [v_pair2_260]="typical 260 2u 0.28u 2u 100p clk -"
  [v_pair2_630]="typical 630 2u 0.28u 2u 100p clk -"
  [v_both_260]="typical 260 2u 0.28u 8u 100p clk -"
  [v_both_630]="typical 630 2u 0.28u 8u 100p clk -"
  [new_1p12_260]="typical 260 4u 1.12u 8u 20p clk -"
  [new_1p12_630]="typical 630 4u 1.12u 8u 20p clk -"
  [new_2p24_260]="typical 260 8u 2.24u 8u 20p clk -"
  [new_2p24_630]="typical 630 8u 2.24u 8u 20p clk -"
  [probe_new_ff_rf140]="ff 140 2u 0.28u 8u 20p trace new_design"
  [probe_new_ff_rf140_100p]="ff 140 2u 0.28u 8u 100p trace new_design"
)

if [[ "${1:-}" == "--list" ]]; then printf '%s\n' "${!T[@]}" | sort; exit 0; fi
[[ $# -eq 1 && -n "${T[$1]:-}" ]] || { echo "usage: gen_probe.sh <name>|--list" >&2; exit 2; }
read -r corner rfuse pair_w pair_l latch_w tran meas prefix <<<"${T[$1]}"

source "$here/../../lib/pdk_env.sh"      # refuses a tree that is not the pin
lib_dir="$PDK_VARIANT_DIR/libs.tech/ngspice"

title="rf=$rfuse $corner/25C/3.30V"
[[ "$prefix" == new_design ]] && title="new design rf=$rfuse $corner/25C/3.30V"

pre='' post=''
if [[ "$meas" == clk ]]; then
  pre=$'meas tran clkn_pre find v(xsa.clkn) at=14.9n\nmeas tran clkn_post find v(xsa.clkn) at=30n\nmeas tran tail find v(xsa.xcmp.tail) at=30n'
  post=$'meas tran sbl find v(sbl) at=14.9n\nmeas tran sref find v(xsa.sref) at=14.9n'
else
  for t in 14.9n 15.2n 15.5n 16n 17n 20n; do
    pre+="meas tran sbl_$t find v(sbl) at=$t"$'\n'"meas tran sref_$t find v(xsa.sref) at=$t"$'\n'
  done
  pre="${pre%$'\n'}"
fi

# Substitute in bash, not sed: the multi-line meas blocks and the library path
# are not safe sed replacement text.
deck="$(cat "$here/probe.cir.in"; echo x)"; deck="${deck%x}"
deck="${deck//%%TITLE%%/$title}"
deck="${deck//%%LIB_DIR%%/$lib_dir}"
deck="${deck//%%CORNER%%/$corner}"
deck="${deck//%%RFUSE%%/$rfuse}"
deck="${deck//%%PAIR_W%%/$pair_w}"
deck="${deck//%%PAIR_L%%/$pair_l}"
deck="${deck//%%LATCH_W%%/$latch_w}"
deck="${deck//%%TRAN%%/$tran}"
deck="${deck//%%MEAS_PRE%%/$pre}"
if [[ -n "$post" ]]; then deck="${deck//%%MEAS_POST%%/$post}"
else deck="${deck//$'%%MEAS_POST%%\n'/}"; fi
printf '%s' "$deck"
