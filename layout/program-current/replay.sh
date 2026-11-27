#!/usr/bin/env bash
# Replay the finite-contact diagnostic on the delivered array, using the #407 solvers.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.."
out=$(mktemp -d "${TMPDIR:-/tmp}/program-current.XXXXXXXX")
echo "Writing the graph, mesh, decks, logs and sweep CSVs to $out"

# The original mesh and selected-state bench are archived in two issue comments.
# Only run the six reviewed code blocks, byte-checked before applying the MIM fix.
for id in 7185048631 7185378755; do
    gh api "repos/2AMLogic/gf180-efuse-otp/issues/comments/$id" --jq .body > "$out/$id.md"
done
extract() {
    local comment=$1 script=$2
    awk -v heading="<details><summary>$script</summary>" '
        $0 == heading { found=1; next }
        found && /^```python$/ { code=1; next }
        code && /^```$/ { exit }
        code { print }
    ' "$out/$comment.md" > "$out/$script"
}
extract 7185048631 ef407_vias.py
extract 7185048631 ef407_spice.py
for script in ef407_ctall.py ef407_ctsheets.py ef407_ng_all.py ef407_pvt.py; do
    extract 7185378755 "$script"
done
(
    cd "$out"
    sha256sum -c - <<'HASHES'
0280f68719dd60f9d6ec8b3c63c93333a4f0c0e05b7e3de7f503eb99ddf426c0  ef407_vias.py
2de0697a22e796f0a947ceacc5c76efae17d998f8cf833f90b7f34810b669f46  ef407_spice.py
68cb4768becb414e68ab5b3dab287484d667b864b1bd2803338d2aa12ebad704  ef407_ctall.py
a70dc3b580c1902523146ff39f5063fde8c980d86cd0ccbd24fedbbba05df504  ef407_ctsheets.py
42b01dba77a739ac50cc15ce715a0d023b33d495e0939d1a8cdfe8b4bcfaa896  ef407_ng_all.py
feca218fcb61ac995496f86941462a0d914dabbc2b7f54620e19c475103ea927  ef407_pvt.py
HASHES
    patch -p0 < "$here/mim-via4.patch"
)

export OPENBLAS_NUM_THREADS=1
mesh=(uv run --no-project --python 3.12 --with klayout==0.30.14 --with numpy==2.5.5
      --with shapely==2.2.0 --with scipy==1.18.1 --with triangle==20250106 python)
gds=layout/efuse_otp_array.gds
"${mesh[@]}" "$out/ef407_vias.py" "$gds" > "$out/graph.json"
"${mesh[@]}" "$out/ef407_ctall.py" "$gds" 1 "$out/all"
python3 "$out/ef407_ng_all.py" "$out/all" "$out/addresses"
"${mesh[@]}" "$out/ef407_ctsheets.py" "$gds" 0.25 "$out/worst"
for corner in nom high; do
    python3 "$out/ef407_spice.py" "$out/worst.$corner.json" 1 "$out/refined_$corner.cir"
done
python3 "$out/ef407_pvt.py" "$out/refined_" "$out/pvt"
python3 "$here/controls.py" "$out/refined_high.cir"
