#!/usr/bin/env bash
# Regenerate the mapped gate-level netlist rtl/efuse_otp_ctrl.gl.v with the
# pinned klt (never a host-installed one) from rtl/synth-request.json.
#   rtl/regen-gl.sh           rewrite rtl/efuse_otp_ctrl.gl.v
#   rtl/regen-gl.sh --check   regenerate to a temp file and fail if it differs
# Needs yosys on PATH and the gf180mcuD PDK (PDK_ROOT, default ~/.ciel). Fails
# unless the mapped netlist has zero latches (klt's structural count and a
# scan of the netlist for latch cell types).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
mode=write
[ "${1:-}" = "--check" ] && mode=check
export PDK="${PDK:-gf180mcuD}" PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"
gl=rtl/efuse_otp_ctrl.gl.v
report=$(mktemp)
trap 'rm -f "$report" "${tmp:-}"' EXIT
klt synthesize rtl/synth-request.json \
  --format json > "$report"
tmp=$(mktemp)
python3 -I - "$report" "$tmp" <<'PY'
import json, shutil, sys
d = json.load(open(sys.argv[1]))
assert d["status"] == "ok", d["status"]
s = d["structural"]
for k in ("latches", "unexpected_latches", "comb_loops", "multi_driven"):
    assert s[k] == 0, f"structural.{k} = {s[k]}"
shutil.copyfile(d["netlist_path"]["path"], sys.argv[2])
PY
if grep -qiE 'latch|dlat' "$tmp"; then
  echo "latch cell in mapped netlist" >&2
  exit 1
fi
echo "Number of latches: 0 (mapped netlist)"
if [ "$mode" = check ]; then
  cmp "$tmp" "$gl" && echo "$gl is current"
else
  cp "$tmp" "$gl"
fi
