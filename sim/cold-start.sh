#!/usr/bin/env bash
# Single cold-start entry point for the item-9 testbench inventory
# (signoff/attest/item9.json). From a fresh clone with the tools in sim/README.md:
#
#   sim/cold-start.sh
#
# Runs the controller bench, then validates (--dry-run) each analog bench's `klt sim`
# request set. --dry-run checks the request set only; it does not run a corner and
# says nothing about margin or current. The full corner campaigns are the documented
# batch commands (sim/README.md, "Testbench inventory"): sim/program-select/run.sh
# and sim/sense-margin/run.sh without --dry-run. Exit 0 iff every step succeeds.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"

echo "== controller bench (verification/run.sh)"
"$repo/verification/run.sh"

# program-select --dry-run leaves its generated decks in a new records/ directory
# ("delete it"); remove only what this script created so records stay append-only.
echo "== program-select request set (dry run)"
before="$(ls -1 "$here/program-select/records" 2>/dev/null || true)"
"$here/program-select/run.sh" --dry-run
for d in $(ls -1 "$here/program-select/records"); do
  grep -qx "$d" <<<"$before" || rm -rf "$here/program-select/records/$d"
done

echo "== sense-margin request set (dry run)"
"$here/sense-margin/run.sh" --dry-run
echo "cold start OK: controller bench passed; analog request sets validate (no corner was run)"
