#!/usr/bin/env bash
# Print one issue-77 comparator probe deck on stdout (single-corner; run it with
# `ngspice -b`). A deck is composed from the same two sources the sense-margin
# bench itself uses -- sim/sense-margin/sense.cir.in for the bench body, and the
# efuse_sense / efuse_comp subcircuits of design/efuse_otp_array.spice extracted
# with bench_subckt -- assembled the way sim/sense-margin/run.sh assembles its
# decks. What is specific to a probe is added here: the title / .lib / .temp
# header, the .control block, and the comparator size overrides in the table
# below. README.md says what each probe shows.
#
#   gen_probe.sh <name>      print the deck
#   gen_probe.sh --list      list probe names
#
# The PDK library directory comes from sim/lib/pdk_env.sh (the pinned tree).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"

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

# The comparator sizes as design/efuse_otp_array.spice commits them: the input
# pair (XM1/XM2) L and W, and the latch pair (XMx1/XMx2) L and W. Each probe
# rewrites pair L/W and latch W to its own row above. These are the values the
# rewrite matches on, so if the committed netlist stops carrying them the deck is
# refused rather than emitted with a comparator that is neither the probe's size
# nor the netlist's -- the same guard run.sh applies to its Rref rewrite.
NET_PAIR_L=2.24u
NET_PAIR_W=8u
NET_LATCH_L=0.28u
NET_LATCH_W=8u

if [[ "${1:-}" == "--list" ]]; then printf '%s\n' "${!T[@]}" | sort; exit 0; fi
[[ $# -eq 1 && -n "${T[$1]:-}" ]] || { echo "usage: gen_probe.sh <name>|--list" >&2; exit 2; }
read -r corner rfuse pair_w pair_l latch_w tran meas prefix <<<"${T[$1]}"

source "$here/../../lib/pdk_env.sh"      # refuses a tree that is not the pin
lib_dir="$PDK_VARIANT_DIR/libs.tech/ngspice"

bench="$here/../sense.cir.in"
netlist="$repo/design/efuse_otp_array.spice"
for f in "$bench" "$netlist"; do
  [[ -f "$f" ]] || { echo "gen_probe.sh: $f missing" >&2; exit 1; }
done

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

# The bench body and the meas blocks are emitted by bash, not sed: the multi-line
# meas blocks and the library path are not safe sed replacement text. The two
# bench placeholders are substituted exactly as run.sh substitutes them.
deck="$(
  printf '* probe %s\n' "$title"
  printf '.lib %s/sm141064.ngspice %s\n' "$lib_dir" "$corner"
  # The netlist instantiates the PDK resistor (ppolyf_u), which the MOS corner
  # sections above do not pull in (it lives in the res_* sections).
  printf '.lib %s/sm141064.ngspice res_%s\n' "$lib_dir" "$corner"
  printf '.temp 25\n'
  sed -e "s#@DESIGN@#$lib_dir/design.ngspice#g" -e "s#@RFUSE@#$rfuse#g" "$bench"
  echo
  bench_subckt "$netlist" efuse_sense
  echo
  bench_subckt "$netlist" efuse_comp | sed \
    -e "s#^\(XM[12] [a-z0-9]* [a-z0-9]* tail vdd33 pfet_03v3 \)L=$NET_PAIR_L W=$NET_PAIR_W #\1L=$pair_l W=$pair_w #" \
    -e "s#^\(XMx[12] [a-z0-9]* [a-z0-9]* vss vss nfet_03v3 \)L=$NET_LATCH_L W=$NET_LATCH_W #\1L=$NET_LATCH_L W=$latch_w #"
  printf '.control\n'
  printf 'tran %s 40n\n' "$tran"
  printf '%s\n' "$pre"
  printf 'meas tran cp find v(xsa.cp) at=38n\n'
  printf 'meas tran cn find v(xsa.cn) at=38n\n'
  printf 'meas tran so find v(sense_out) at=38n\n'
  if [[ -n "$post" ]]; then printf '%s\n' "$post"; fi
  printf '.endc\n'
  printf '.end\n'
  echo x
)"
deck="${deck%x}"

# Refuse a deck that did not come out as asked: either subcircuit missing from the
# netlist, or a comparator size rewrite that found nothing to rewrite.
need() {                                 # need <fixed string> <what>
  [[ "$deck" == *"$1"* ]] || { echo "gen_probe.sh: $2 -- '$1' is not in the composed deck." >&2
    echo "gen_probe.sh: check efuse_sense / efuse_comp in $netlist (expected input pair L=$NET_PAIR_L W=$NET_PAIR_W, latch L=$NET_LATCH_L W=$NET_LATCH_W); refusing to emit." >&2
    exit 1; }
}
need '.subckt efuse_sense '                                                    "efuse_sense was not extracted"
need '.subckt efuse_comp '                                                     "efuse_comp was not extracted"
need "XM1 outp inp tail vdd33 pfet_03v3 L=$pair_l W=$pair_w nf=1 "             "input pair XM1 size rewrite did not match"
need "XM2 outn inn tail vdd33 pfet_03v3 L=$pair_l W=$pair_w nf=1 "             "input pair XM2 size rewrite did not match"
need "XMx1 outp outn vss vss nfet_03v3 L=$NET_LATCH_L W=$latch_w nf=1 "        "latch XMx1 size rewrite did not match"
need "XMx2 outn outp vss vss nfet_03v3 L=$NET_LATCH_L W=$latch_w nf=1 "        "latch XMx2 size rewrite did not match"

printf '%s' "$deck"
