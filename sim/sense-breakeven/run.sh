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
source "$here/../lib/sense_request.sh"
bench_parse_args "$@"
pdk_fleet_check || exit 1

SWEEP_OHMS="300 340 380 420 460 500 540"   # brackets the 328..472 ohm physical-reference estimate
RREF_OHM=400                                # A6, decision 0003

bench_netlist "$repo/design/efuse_otp_array.spice"
bench_new_record_dir "$here/records" "$dry"

reqs=()
for r in $SWEEP_OHMS; do sense_request "ideal_rf${r}_rr${RREF_OHM}" "$r" "$RREF_OHM"; done
for r in $SWEEP_OHMS; do sense_request "phys_rf${r}_rrphys" "$r" phys; done

if [[ $dry -eq 1 ]]; then bench_dry_run_exit "${reqs[@]}"; fi

bench_submit_set "$rec" "${reqs[@]}"
echo "record: $rec"
python3 -I "$here/summarize.py" "$rec" --rref "$RREF_OHM" --rfuse "$SWEEP_OHMS" \
    --t-pre "$T_PRE" --t-out "$T_OUT" --t-edge "$T_EDGE" \
    --pdk-rev "$PDK_REVISION" --stamp "$stamp" --klt "$(klt --version)"
