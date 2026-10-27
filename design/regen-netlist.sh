#!/usr/bin/env bash
# Regenerate the SPICE netlist design/efuse_otp_array.spice from the xschem
# schematics with the pinned klt (never a host-installed one, never raw xschem).
#   design/regen-netlist.sh           rewrite design/efuse_otp_array.spice
#   design/regen-netlist.sh --check   exit 0 if it matches, 3 if it has drifted
# Runs from design/ because the PDK xschemrc puts $PWD on the symbol path,
# which is how the hierarchical cell symbols (*.sym here) are found. Needs
# xschem and the pinned PDK tree (sim/lib/pdk_env.sh).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
extra=()
[ "${1:-}" = "--check" ] && extra=(--check)
# shellcheck source=../sim/lib/pdk_env.sh
. "$root/sim/lib/pdk_env.sh"
cd "$root/design"
exec uvx --from "$(cat "$root/signoff/klt-pin.txt")" klt netlist efuse_otp_array.sch \
  -o "$root/design/efuse_otp_array.spice" "${extra[@]}" \
  --rcfile "$PDK_VARIANT_DIR/libs.tech/xschem/xschemrc" \
  --pdk "$(jq -er .variant "$root/sim/pdk.json")" --pdk-root "$PDK_ROOT"
