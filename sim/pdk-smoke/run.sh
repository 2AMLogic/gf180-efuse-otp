#!/usr/bin/env bash
# Run the PDK smoke simulation (typical, 27 C, single corner) and write a new
# append-only record under sim/pdk-smoke/records/<UTC stamp>-<pdk rev:7>/.
# Never overwrites a record. Exit 0 only if every device converged.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
source "$here/../lib/pdk_env.sh"        # refuses a tree that is not the pin

lib="$PDK_VARIANT_DIR/libs.tech/ngspice"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
rec="$here/records/$stamp-${PDK_REVISION:0:7}"
mkdir -p "$here/records"
mkdir "$rec"                             # fails if it exists: no overwrite

sed "s#@DESIGN@#$lib/design.ngspice#; s#@LIB@#$lib/sm141064.ngspice#" \
  "$here/smoke.cir.in" > "$rec/netlist.cir"
ngspice_version="$(ngspice -v | sed -n 's/^\*\* ngspice-\([0-9.]*\).*/\1/p' | head -1)"

set +e
(cd "$rec" && ngspice -b -o smoke.log netlist.cir >/dev/null 2>&1)
rc=$?
set -e

# Per-device verdict comes from the log: both SMOKE lines present, drain
# current finite and > 0, full sweep length, and no ngspice error text.
bad=0; grep -qiE 'error|no convergence|singular matrix|timestep too small' "$rec/smoke.log" && bad=1
devs="[]"
for d in n33:nfet_03v3:34 p33:pfet_03v3:34 n60:nfet_06v0:61 p60:pfet_06v0:61; do
  IFS=: read -r key model npts <<<"$d"
  op="$(sed -n "s/^SMOKE_OP $key id=//p" "$rec/smoke.log")"
  dc="$(sed -n "s/^SMOKE_DC $key points=\([0-9]*\) idmax=\(.*\)/\1 \2/p" "$rec/smoke.log")"
  read -r pts idmax <<<"${dc:-0 nan}"
  conv=false
  if [[ $bad -eq 0 && $rc -eq 0 && -n "$op" && "$pts" == "$npts" ]] \
     && awk -v a="${op:-0}" -v b="${idmax:-0}" 'BEGIN{exit !(a+0>0 && b+0>0)}'; then conv=true; fi
  devs="$(jq -c --arg k "$key" --arg m "$model" --arg op "${op:-}" --arg im "${idmax:-}" \
            --argjson p "${pts:-0}" --argjson c "$conv" \
            '. + [{name:$k, model:$m, op_id_a:$op, dc_points:$p, dc_idmax_a:$im, converged:$c}]' <<<"$devs")"
done

jq -n --arg rev "$PDK_REVISION" --arg var "$(jq -r .variant "$here/../pdk.json")" \
      --arg ng "$ngspice_version" --arg ts "$stamp" --argjson devs "$devs" --argjson rc "$rc" \
  '{pdk_revision:$rev, variant:$var, corner:"typical", temp_c:27,
    ngspice_version:$ng, timestamp_utc:$ts, ngspice_exit:$rc, devices:$devs,
    all_converged: ($devs | all(.converged))}' > "$rec/record.json"

echo "record: $rec"
jq -e .all_converged "$rec/record.json" >/dev/null
