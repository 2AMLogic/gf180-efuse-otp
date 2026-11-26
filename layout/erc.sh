#!/usr/bin/env bash
# Run the pinned klt on the supply specs for the controller and analog array.
#   layout/erc.sh                      refresh the two committed reports
#   layout/erc.sh --check [--rerun]    check report hashes, optionally rerun ERC
#   layout/erc.sh --negative-control   remove the Metal4 routing plane and
#                                      require every supply to fragment
# Each stream has one top cell, so --check --rerun can infer its top.
# ERC exits 3 for findings and 4 for ungraded antenna checks. Preserve each
# measured result, including partial connectivity coverage, in its report.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

negative_control() {
  local rc=0
  python3 -I - "$spec" "$work/negative.json" <<'PYTHON'
import json, sys
spec = json.load(open(sys.argv[1]))
removed = "Metal4"
stackup = [e for e in spec["stackup"] if e["name"] != removed]
vias = [v for v in spec["vias"] if removed not in v["between"]]
assert len(stackup) < len(spec["stackup"]) and len(vias) < len(spec["vias"]), \
    "negative control edit removed nothing"
spec["stackup"], spec["vias"] = stackup, vias
json.dump(spec, open(sys.argv[2], "w"), indent=2)
PYTHON
  klt erc "$stream" "$work/negative.json" --top "$top" --deck gf180mcu \
    --findings-only --omit-antenna-tables --format json > "$work/result.json" || rc=$?
  if [ "$rc" != 3 ]; then
    echo "$top: removing Metal4 returned $rc, expected 3" >&2
    return 1
  fi
  python3 -I - "$work/result.json" "${supplies[@]}" <<'PYTHON'
import json, sys
report = json.load(open(sys.argv[1]))
broken = {f["net"] for f in report["erc_findings"] if f["rule"] == "erc.unconnected_net"}
expected = set(sys.argv[2:])
if not expected <= broken:
    sys.exit(f"Negative control did not fragment {sorted(expected - broken)}")
print(f"Negative control fragmented {', '.join(sorted(expected))}")
PYTHON
}

refresh() {
  local rc=0
  klt erc "$stream" "$spec" --top "$top" --deck gf180mcu \
    --findings-only --omit-antenna-tables --format json > "$work/result.json" || rc=$?
  case "$rc" in
    0|3|4) ;;
    *) cat "$work/result.json" >&2; return "$rc" ;;
  esac
  cp "$work/result.json" "$report"
  python3 -I - "$report" <<'PYTHON'
import json, sys
d = json.load(open(sys.argv[1]))
islands = " ".join(f'{n["name"]}_islands={n["matched_islands"]}' for n in d["nets"])
cov = d["erc_coverage"]
print(f'{sys.argv[1]}: erc_status={d["erc_status"]} status={d["status"]} '
      f'findings={d["erc_finding_count"]} {islands} skipped={len(cov["skipped"])} '
      f'inapplicable={len(cov["inapplicable"])} input={d["provenance"]["input"]["content_hash"]}')
PYTHON
}

mode=${1:-refresh}
if [ "$#" -gt 0 ]; then shift; fi
for part in ctrl array; do
  top="efuse_otp_$part"
  stream="layout/$top.gds"
  spec="layout/erc-$part.spec.json"
  report="layout/erc-$part.report.json"
  case "$mode" in
    --check) klt erc --check "$report" "$@" ;;
    --negative-control)
      if [ "$part" = ctrl ]; then supplies=(VDD VSS); else supplies=(vdd33 vprog vss); fi
      negative_control ;;
    refresh) refresh ;;
    *) echo "Usage: $0 [--check [--rerun] | --negative-control]" >&2; exit 2 ;;
  esac
done
