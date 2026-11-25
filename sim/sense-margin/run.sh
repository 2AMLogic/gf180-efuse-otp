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
source "$here/../lib/sense_request.sh"

bench_parse_args "$@"

# Same fleet-image rule as sim/program-select/run.sh: the fleet ships gf180mcuD,
# the pin is gf180mcuC; the model files read here must be byte-identical.
pdk_fleet_check || exit 1

# ASSUMPTIONS, recorded verbatim in record.json (only 200 and 900 ohm are documented).
INTACT_OHMS="140 200 260"                # A4
PROGRAMMED_OHMS="630 900 open"           # A5; open = 1 Gohm
RREF_OHM=400                             # A6, decision 0003
RREF_CONTROL_OHM=200                     # negative control: reference inside the intact range
RFUSE_CONTROL_OHMS="140 260"             # the intact values re-read against RREF_CONTROL_OHM

bench_netlist "$repo/design/efuse_otp_array.spice"

bench_new_record_dir "$here/records" "$dry"

reqs=()
for r in $INTACT_OHMS; do sense_request "bench_rf${r}_rr${RREF_OHM}" "$r" "$RREF_OHM" -1; done
for r in $PROGRAMMED_OHMS; do sense_request "bench_rf${r}_rr${RREF_OHM}" "$r" "$RREF_OHM" 1; done
# Physical reference: the same fuse values with the committed XRref left in the deck.
for r in $INTACT_OHMS; do sense_request "phys_rf${r}_rrphys" "$r" phys -1; done
for r in $PROGRAMMED_OHMS; do sense_request "phys_rf${r}_rrphys" "$r" phys 1; done
for r in $RFUSE_CONTROL_OHMS; do sense_request "control_rf${r}_rr${RREF_CONTROL_OHM}" "$r" "$RREF_CONTROL_OHM" -1; done

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
