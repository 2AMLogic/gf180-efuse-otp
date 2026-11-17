#!/usr/bin/env bash
# Resolve the pinned gf180mcu variant directory; refuse any other revision.
#
# Source it (exports PDK_ROOT, PDK_VARIANT_DIR, PDK_REVISION) or run it
# (prints the variant directory).
#
#   CIEL_ROOT   ciel root, default $HOME/.ciel
#
# Exit 0: tree found and its SOURCES revision equals the pin.
# Exit 1: pin unreadable, no tree found, or SOURCES at another revision.

_pdk_env_main() {
  local here pin variant root dir src
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  command -v jq >/dev/null || { echo "pdk_env: jq is required" >&2; return 1; }
  pin="$(jq -er .open_pdks_revision "$here/../pdk.json")" \
    && variant="$(jq -er .variant "$here/../pdk.json")" \
    || { echo "pdk_env: cannot read the pin from sim/pdk.json" >&2; return 1; }
  root="${CIEL_ROOT:-$HOME/.ciel}"
  dir="$root/ciel/gf180mcu/versions/$pin/$variant"
  if [[ ! -d "$dir" ]]; then
    echo "pdk_env: no tree for pinned revision $pin at $dir (CIEL_ROOT=$root); other trees are not used" >&2
    return 1
  fi
  src="$(cat "$dir/SOURCES" 2>/dev/null)"
  if [[ "$src" != "open_pdks $pin" ]]; then
    echo "pdk_env: $dir/SOURCES reads '${src:-<missing>}', expected 'open_pdks $pin'" >&2
    return 1
  fi
  PDK_ROOT="$root/ciel/gf180mcu/versions/$pin"
  PDK_VARIANT_DIR="$dir"
  PDK_REVISION="$pin"
  export PDK_ROOT PDK_VARIANT_DIR PDK_REVISION
}

# Fleet-image rule: the fleet ships gf180mcuD, the pin is gf180mcuC. The model
# files the benches read must be byte-identical in both; which files is
# fleet_checked_model_files in sim/pdk.json, the one list bench_record.py
# renders into variant_simulated. Defined on source, not run on source. On
# success exports PDK_FLEET_LIB_DIR (the D ngspice dir); returns 1 if a file
# differs or is missing.
pdk_fleet_check() {
  local here libc lib f files
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  libc="$PDK_VARIANT_DIR/libs.tech/ngspice"
  lib="$PDK_ROOT/gf180mcuD/libs.tech/ngspice"
  files="$(jq -r '.fleet_checked_model_files[]' "$here/../pdk.json")" \
    || { echo "pdk_fleet_check: cannot read fleet_checked_model_files from sim/pdk.json" >&2; return 1; }
  [[ -n "$files" ]] \
    || { echo "pdk_fleet_check: fleet_checked_model_files in sim/pdk.json is empty" >&2; return 1; }
  while IFS= read -r f; do
    cmp -s "$libc/$f" "$lib/$f" || { echo "run.sh: $f differs between gf180mcuC and gf180mcuD" >&2; return 1; }
  done <<< "$files"
  PDK_FLEET_LIB_DIR="$lib"
  export PDK_FLEET_LIB_DIR
}

# Shared run.sh boilerplate for the sim/* benches. Defined on source, not run.

# bench_parse_args "$@": sets dry=1 on --dry-run; any other argument is a usage
# error (exit 2).
# shellcheck disable=SC2034  # dry is read by the sourcing run.sh
bench_parse_args() {
  dry=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry=1; shift ;;
      *) echo "usage: run.sh [--dry-run]" >&2; exit 2 ;;
    esac
  done
}

# bench_subckt <netlist> <name>: print one .subckt ... .ends block.
bench_subckt() {
  awk -v n="$2" '$1==".subckt" && $2==n {p=1} p {print} p && $1==".ends" {exit}' "$1"
}

# bench_new_record_dir <records dir> <dry 0|1>: sets stamp and rec. Dry runs get
# a temp dir; otherwise a new append-only <records dir>/<stamp>-<pdk rev:7>,
# created with a plain mkdir so an existing record is never overwritten.
bench_new_record_dir() {
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  if [[ "$2" -eq 1 ]]; then
    rec="$(mktemp -d)"
  else
    rec="$1/$stamp-${PDK_REVISION:0:7}"
    mkdir -p "$1"
    mkdir "$rec"                         # fails if it exists: no overwrite
  fi
}

# bench_dry_run <request.json...>: validate each request against the batch
# backend without submitting (no grid, no record). The caller owns cleanup.
bench_dry_run() {
  local q
  for q in "$@"; do
    klt sim --dry-run --format json --backend batch "$q" | jq -c '{unit_count,backend,warnings}'
  done
}

# bench_submit_set <rec> <request.json...>: submit the set to the batch fleet,
# report to <rec>/set-report.json, stderr to <rec>/klt.err. Sets rc: 0 = all
# pass, 3 = some measurement failed, 4 = a request errored or was refused
# (partial set); both are left to the caller. Any other rc is a tool failure
# and exits. Never re-runs a failed or refused submit on local ngspice.
bench_submit_set() {
  local rec="$1"; shift
  set +e
  klt sim --batch-set "$@" --max-in-flight 4 --capacity-retries 3 --wait-for-capacity 600 \
      -o "$rec/sets" --format json > "$rec/set-report.json" 2> "$rec/klt.err"
  rc=$?
  set -e
  if [[ $rc -ne 0 && $rc -ne 3 && $rc -ne 4 ]]; then
    echo "klt sim --batch-set failed (rc=$rc); see $rec/klt.err" >&2
    exit "$rc"
  fi
}

# The ratified decision-0005 PVT corner grid (spec/decisions/0005-pvt-corner-set.md):
# process typical/ff/ss/fs/sf, temperature -40/25/125 C, logic/sense supply
# 3.3 V +-10%, program supply 5.0 V +-10%. JSON literals, passed to the request
# builders with jq --argjson; each bench names its own supply axes and maps its
# own model sections from these values.
PVT_PROCESSES='["typical","ff","ss","fs","sf"]'
PVT_TEMPERATURES_C='[-40,25,125]'
PVT_SUPPLY_3V3='[2.97,3.30,3.63]'
PVT_SUPPLY_5V0='[4.5,5.0,5.5]'
export PVT_PROCESSES PVT_TEMPERATURES_C PVT_SUPPLY_3V3 PVT_SUPPLY_5V0

if _pdk_env_main; then
  [[ "${BASH_SOURCE[0]}" == "$0" ]] && echo "$PDK_VARIANT_DIR"
  (return 0 2>/dev/null) && return 0 || exit 0
else
  (return 0 2>/dev/null) && return 1 || exit 1
fi
