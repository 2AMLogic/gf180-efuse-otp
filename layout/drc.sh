#!/usr/bin/env bash
# Run `klt drc --deck gf180mcu` on both partitions' GDS with the pinned klt (never
# a host-installed one) plus the routed efuse_ls, efuse_rowdrv and efuse_coldrv
# cells (each the top of the analog stream),
# and keep the JSON reports as committed evidence.
#   layout/drc.sh           rewrite layout/drc-array.report.json,
#                           layout/drc-ctrl.report.json and
#                           layout/drc-ls.report.json,
#                           layout/drc-rowdrv.report.json and
#                           layout/drc-coldrv.report.json
#   layout/drc.sh --check   klt drc --check on each committed report (input and
#                           deck content hashes still match; add --rerun to re-run)
# klt exits 3 when a report is not clean; that is a finding, not a script failure,
# so the verdicts are printed and the reports are kept as found. Needs only the
# pinned klt (the curated deck needs no PDK or standalone klayout).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
# part:name:top[:file] -- a routed cell (efuse_ls, rowdrv, coldrv) is DRC'd inside the analog
# stream (top efuse_ls of efuse_otp_array.gds), so its GDS differs from its top.
parts=(array:efuse_otp_array ctrl:efuse_otp_ctrl ls:efuse_ls:efuse_otp_array
       rowdrv:efuse_rowdrv:efuse_otp_array coldrv:efuse_coldrv:efuse_otp_array)
if [ "${1:-}" = "--check" ]; then
  shift
  for p in "${parts[@]}"; do
    klt drc --check "layout/drc-${p%%:*}.report.json" "$@"
  done
  exit 0
fi
for p in "${parts[@]}"; do
  part=${p%%:*}
  rest=${p#*:}
  top=${rest%%:*}
  file=${rest#*:}
  file=${file%%:*}
  [ -n "$file" ] || file=$top
  out=$(mktemp)
  rc=0
  klt drc --deck gf180mcu --top "$top" --format json "layout/$file.gds" > "$out" || rc=$?
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
