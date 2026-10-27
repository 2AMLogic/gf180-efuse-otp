#!/usr/bin/env bash
# Write the T1 item 2 (digital) attestation layout/pnr.attest.json: a generic
# envelope bound to the routed GDS, carrying the regeneration claim (generator
# layout/pnr.sh, geometry digest, so GDS write times do not matter). klt has no
# `--attest 2`, so this envelope is assembled here from the committed P&R report;
# it fails unless that report is status ok, stage route, power.pdn true, with zero
# route DRC and antenna violations.
#   layout/attest.sh           rewrite layout/pnr.attest.json
#   layout/attest.sh --check   fail if the committed envelope differs
set -euo pipefail
cd "$(dirname "$0")/.."
mode=write
[ "${1:-}" = "--check" ] && mode=check
out=layout/pnr.attest.json
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
uvx --from "$(cat signoff/klt-pin.txt)" python -I - "$tmp" <<'PY'
import json, sys
from klayout_tools import _provenance as p
r = json.load(open("layout/pnr-report.json"))
gds = "layout/efuse_otp_ctrl.gds"
checks = {
    "status ok": r["status"] == "ok",
    "stage_reached route": r["stage_reached"] == "route",
    "power.pdn true": r["power"]["pdn"] is True,
    "route_drc_violation_count 0": r["route_drc_violation_count"] == 0,
    "antenna_violation_count 0": r["antenna_violation_count"] == 0,
}
bad = [k for k, v in checks.items() if not v]
assert not bad, f"P&R report fails: {bad}"
env = {
    "schema_version": 1,
    "kind": "generic",
    "status": "pass",
    "t1_item": 2,
    "summary": "T1 item 2 (Layout, digital): routed GDS from klt place-and-route "
    "(layout/pnr-report.json: " + ", ".join(checks) + ")",
    "source": "layout/pnr-report.json",
    "provenance": {
        "klt_version": r["provenance"]["klt_version"],
        "klayout_version": None,
        "pdk": None,
        "deck": None,
        "input": {
            "path": {"path": gds, "scope": "repo"},
            "content_hash": "sha256:" + p.sha256_file(gds).removeprefix("sha256:"),
        },
        "regeneration": {
            "generator": "layout/pnr.sh",
            "regenerated_hash": p.layout_geometry_digest(gds),
            "hash_kind": "geometry",
        },
    },
}
with open(sys.argv[1], "w") as f:
    json.dump(env, f, indent=2)
    f.write("\n")
PY
if [ "$mode" = check ]; then
  cmp "$tmp" "$out" && echo "$out is current"
else
  cp "$tmp" "$out"
fi
