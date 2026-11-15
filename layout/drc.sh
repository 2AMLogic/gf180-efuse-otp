#!/usr/bin/env bash
# Run `klt drc --deck gf180mcu` on both partitions' GDS with the pinned klt (never
# a host-installed one) and keep the JSON reports as committed evidence.
#   layout/drc.sh           rewrite layout/drc-array.report.json and
#                           layout/drc-ctrl.report.json
#   layout/drc.sh --check   klt drc --check on each committed report (input and
#                           deck content hashes still match; add --rerun to re-run)
# klt exits 3 when a report is not clean; that is a finding, not a script failure,
# so the verdicts are printed and the reports are kept as found. Needs only the
# pinned klt (the curated deck needs no PDK or standalone klayout).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
parts=(array:efuse_otp_array ctrl:efuse_otp_ctrl)
if [ "${1:-}" = "--check" ]; then
  shift
  for p in "${parts[@]}"; do
    klt drc --check "layout/drc-${p%%:*}.report.json" "$@"
  done
  exit 0
fi
for p in "${parts[@]}"; do
  part=${p%%:*} top=${p##*:}
  out=$(mktemp)
  rc=0
  klt drc --deck gf180mcu --top "$top" --format json "layout/$top.gds" > "$out" || rc=$?
  [ "$rc" = 0 ] || [ "$rc" = 3 ] || { cat "$out" >&2; rm -f "$out"; exit "$rc"; }
  cp "$out" "layout/drc-$part.report.json"
  rm -f "$out"
  python3 -I - "layout/drc-$part.report.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(f'{sys.argv[1]}: status={d["status"]} violations={d["violation_count"]} '
      f'deck={d["provenance"]["deck"]["content_hash"]}')
PY
done
