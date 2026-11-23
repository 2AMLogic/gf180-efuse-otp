#!/usr/bin/env bash
# Regenerate layout/efuse_otp_array.gds (and .report.json, .sha256) from
# design/efuse_otp_array.spice with the pinned klt and the pinned PDK tree
# (never a host-installed klt).
#   layout/regen-gds.sh           rewrite the committed files
#   layout/regen-gds.sh --check   exit 0 if they match, 3 if they have drifted
# The generator also checks the fuse cell against the PDK primitive (exit 4),
# reads the emitted stream back to re-run that comparison on what ships, and
# coarsens it to the foundry 0.001 um database unit (issue #311) at the final
# write -- fatal on any coordinate the 2:1 conversion cannot represent exactly.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=../sim/lib/pdk_env.sh
. "$root/sim/lib/pdk_env.sh"
# shellcheck source=../signoff/klt.sh
. "$root/signoff/klt.sh"
fuse="$PDK_VARIANT_DIR/libs.ref/gf180mcu_fd_pr/gds/efuse.gds"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

klt_python -I "$root/layout/gen_efuse_otp.py" \
  --klt "$KLT_ARGV" --netlist "$root/design/efuse_otp_array.spice" \
  --pdk "$(jq -er .variant "$root/sim/pdk.json")" --pdk-root "$PDK_ROOT" \
  --fuse-gds "$fuse" -o "$tmp/efuse_otp_array.gds" --report "$tmp/report.json" >/dev/null
sha="$(sha256sum "$tmp/efuse_otp_array.gds" | cut -d' ' -f1)"

if [ "${1:-}" = "--check" ]; then
  cmp -s "$tmp/efuse_otp_array.gds" "$root/layout/efuse_otp_array.gds" || { echo "GDS drifted (now $sha)" >&2; exit 3; }
  cmp -s "$tmp/report.json" "$root/layout/efuse_otp_array.report.json" || { echo "report drifted" >&2; exit 3; }
  exit 0
fi
cp "$tmp/efuse_otp_array.gds" "$root/layout/efuse_otp_array.gds"
cp "$tmp/report.json" "$root/layout/efuse_otp_array.report.json"
echo "$sha  efuse_otp_array.gds" > "$root/layout/efuse_otp_array.gds.sha256"
echo "$sha"
