#!/usr/bin/env bash
# layout/drc.sh                  regenerate the curated and native DRC reports
# layout/drc.sh --check          verify their input and deck hashes
# layout/drc.sh --check --rerun  also reproduce their verdicts
# Native runs need the pinned Ciel tree (CIEL_ROOT, default ~/.ciel) and KLayout.
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
check=false
rerun=false
native_check_args=()
if [[ ${1:-} == --check ]]; then
  check=true
  shift
  for arg in "$@"; do
    if [[ $arg == --rerun ]]; then rerun=true; else native_check_args+=("$arg"); fi
  done
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Exit 3 from a fresh run means violations. Preserve them in the report.
run_drc() {
  local rc=0
  klt drc "$@" --format json > "$tmp/report.json" || rc=$?
  case "$rc" in
    0|3) ;;
    *) cat "$tmp/report.json" >&2; return "$rc" ;;
  esac
}

parts=(array:efuse_otp_array ctrl:efuse_otp_ctrl ls:efuse_ls:efuse_otp_array
       rowdrv:efuse_rowdrv:efuse_otp_array coldrv:efuse_coldrv:efuse_otp_array
       comp:efuse_comp:efuse_otp_array sense:efuse_sense:efuse_otp_array)
for p in "${parts[@]}"; do
  IFS=: read -r part top file <<< "$p"
  report="layout/drc-$part.report.json"
  if "$check"; then
    if [ -n "${file:-}" ]; then
      # Per-cell report. klt's own --rerun is top-less (klayout-tools#7000:
      # the report records no --top, so the replay checks every top cell, and
      # a cell-scoped coverage set drifts when the stream's other tops change
      # the deck's applicable rules -- e.g. a voltage-domain marker under one
      # cell beside a cell without one). The hash gate stays klt's; the full
      # replay re-runs the recorded scoped invocation and byte-compares, the
      # same contract the native loop below already uses.
      klt drc --check "$report"
      "$rerun" || continue
      run_drc --deck gf180mcu --top "$top" "layout/$file.gds"
      cmp "$tmp/report.json" "$report" || exit 3
    else
      klt drc --check "$report" "$@"
    fi
  else
    run_drc --deck gf180mcu --top "$top" "layout/${file:-$top}.gds"
    cp "$tmp/report.json" "$report"
    jq -r --arg file "$report" '"\($file): status=\(.status) violations=\(.violation_count) deck=\(.provenance.deck.content_hash)"' "$report"
  fi
done

# Keep a relative deck path in klt's JSON so --check works on another host.
# shellcheck source=../sim/lib/pdk_env.sh
. sim/lib/pdk_env.sh
array_variant=$(jq -er .variant sim/pdk.json)
ctrl_variant=$(jq -er .provenance.pdk.name layout/pnr-report.json)
cd "$tmp"
ln -s "$PDK_ROOT" pdk
for part in array ctrl; do
  variant=$array_variant
  if [[ $part == ctrl ]]; then variant=$ctrl_variant; fi
  top=efuse_otp_$part
  gds="$root/layout/$top.gds"
  report="$root/layout/drc-$part.native.report.json"
  if "$check"; then
    klt drc --check "$report" "${native_check_args[@]}"
    "$rerun" || continue
  fi

  native=(--engine klayout --deck gf180mcu --pdk "$variant" --pdk-root "$PDK_ROOT"
          --deck-file "pdk/$variant/libs.tech/klayout/tech/drc/gf180mcu.drc"
          --deck-var "variant=$variant" --deck-var decks=all --deck-var threads=1
          --min-klayout-version 0.30.9)
  # klt requires an exact set to count zero-marker rules as checked. The
  # empty-layout listing is independent of the stream. Some PDK categories
  # (density and DBU) are emitted only on a finding. A positive rule count
  # establishes execution for those, even after the geometry changes.
  klt drc "${native[@]}" --list-rule-categories > categories
  printf '%s\n' EF.{01..03} EF.04{a..d} EF.{05..15} EF.16{a,b} EF.{17..21} EF.22{a,b} >> categories
  rc=0
  klt drc "${native[@]}" --top "$top" "$gds" --max-violations 0 --format json > probe.json || rc=$?
  case "$rc" in
    0|3) ;;
    4) jq -e '.status == "coverage_unknown"' probe.json >/dev/null ;;
    *) cat probe.json >&2; exit "$rc" ;;
  esac
  jq -r '.rule_counts | to_entries[] | select(.value > 0) | .key' probe.json >> categories
  LC_ALL=C sort -u categories > expected
  run_drc "${native[@]}" --top "$top" "$gds" --expect-rule-categories-file expected
  if "$check"; then
    # klt 0.9.2's native --rerun omits the original deck variables.
    cmp "$report" "$tmp/report.json" || exit 3
  else
    cp "$tmp/report.json" "$report"
  fi
  jq -r --arg file "layout/drc-$part.native.report.json" \
    '"\($file): status=\(.status) violations=\(.violation_count) EF rules checked=\([.coverage.rules_checked[] | select(startswith("EF."))] | length)"' "$report"
done
