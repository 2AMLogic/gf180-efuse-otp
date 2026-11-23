#!/usr/bin/env bash
# Run `klt erc` with the pinned klt (never a host-installed one) on the
# digital partition's supply spec (T1 item 11, digital), keeping the JSON
# report as committed evidence.
#   layout/erc.sh                   rewrite layout/erc-ctrl.report.json
#   layout/erc.sh --check           klt erc --check on the committed report
#                                    (input, spec and deck hashes still match;
#                                    add --rerun to re-run the finding pass --
#                                    note --rerun cannot replay --top, which
#                                    the report does not echo, so it only
#                                    works because efuse_otp_ctrl.gds has a
#                                    single top cell)
#   layout/erc.sh --negative-control
#                                   prove the spec can fail: a scratch copy
#                                   with the Metal4 strap layer (and the vias
#                                   naming it) removed from the stackup must
#                                   report erc.unconnected_net on VDD and VSS
# The committed run is --findings-only --omit-antenna-tables: T1 item 11
# grades the erc_findings supply rules (erc.unconnected_net,
# erc.supply_short, erc.missing_tie), not the antenna half, and with no
# --pdk no antenna level is graded, so klt exits 4 (status "not_checked")
# on a clean run by design -- gate on erc_status, not the exit code. klt
# exits 3 when a finding exists; that is a finding, not a script failure,
# so the verdict is printed and the report is kept as found.
# Needs no PDK install and no OpenROAD: --deck gf180mcu is the curated
# registry (same deck hash as the DRC/LVS reports) and the layout is the
# committed stream. Requests use repo-root-relative paths, run from the
# repo root, so the committed report's echoed paths stay portable, like
# layout/lvs.sh's stdin requests.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh

if [ "${1:-}" = "--check" ]; then
  shift
  klt erc --check "layout/erc-ctrl.report.json" "$@"
  exit 0
fi

if [ "${1:-}" = "--negative-control" ]; then
  neg=$(mktemp) out=$(mktemp)
  trap 'rm -f "$neg" "$out"' EXIT
  python3 -I - layout/erc-ctrl.spec.json "$neg" <<'PY'
import json, sys
spec = json.load(open(sys.argv[1]))
removed = "Metal4"
stackup = [e for e in spec["stackup"] if e["name"] != removed]
vias = [v for v in spec["vias"] if removed not in v["between"]]
assert len(stackup) < len(spec["stackup"]) and len(vias) < len(spec["vias"]), \
    "negative control edit removed nothing"
spec["stackup"], spec["vias"] = stackup, vias
json.dump(spec, open(sys.argv[2], "w"), indent=2)
PY
  rc=0
  klt erc layout/efuse_otp_ctrl.gds "$neg" --top efuse_otp_ctrl --deck gf180mcu \
    --findings-only --omit-antenna-tables --format json > "$out" || rc=$?
  verdict=$(python3 -I - "$out" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("unparseable"); raise SystemExit
rules = {(f.get("rule"), f.get("net")) for f in d.get("erc_findings") or []}
need = {("erc.unconnected_net", n) for n in ("VDD", "VSS")}
print("fail" if need <= rules else "no-supply-finding")
PY
)
  if [ "$rc" != 3 ] || [ "$verdict" != "fail" ]; then
    echo "negative control: expected exit 3 with erc.unconnected_net on VDD and VSS" \
         "when the Metal4 strap layer is missing from the stackup, got exit $rc / $verdict" >&2
    exit 1
  fi
  echo "negative control OK: without the Metal4 strap layer in the stackup both" \
       "supplies fragment (exit 3, erc.unconnected_net on VDD and VSS)"
  exit 0
fi

out=$(mktemp)
trap 'rm -f "$out"' EXIT
rc=0
klt erc layout/efuse_otp_ctrl.gds layout/erc-ctrl.spec.json \
  --top efuse_otp_ctrl --deck gf180mcu \
  --findings-only --omit-antenna-tables --format json > "$out" || rc=$?
# 0/3/4 are verdicts (clean / findings / antenna not checked); anything else
# is a script failure and must not touch the committed report.
[ "$rc" = 0 ] || [ "$rc" = 3 ] || [ "$rc" = 4 ] || { cat "$out" >&2; exit "$rc"; }
cp "$out" layout/erc-ctrl.report.json
python3 -I - layout/erc-ctrl.report.json <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
nets = {n["name"]: n.get("matched_islands") for n in d.get("nets") or []}
cov = d.get("erc_coverage") or {}
print(f'{sys.argv[1]}: erc_status={d.get("erc_status")} '
      f'status={d.get("status")} findings={d.get("erc_finding_count")} '
      f'VDD_islands={nets.get("VDD")} VSS_islands={nets.get("VSS")} '
      f'skipped={len(cov.get("skipped") or [])} '
      f'inapplicable={len(cov.get("inapplicable") or [])} '
      f'input={d["provenance"]["input"]["content_hash"]}')
PY
