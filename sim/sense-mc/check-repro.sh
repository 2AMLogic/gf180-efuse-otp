#!/usr/bin/env bash
# Determinism check for a recorded sense-mc run: re-run ONE sample at ONE corner locally
# (a single-unit debug probe, never a grid) from the record's own request and compare the
# injected reference draw and the measured values with the recorded fleet sample.
# seed_scope=point makes a sample a pure function of (seed, corner, sample_index), so n and
# the rest of the grid do not matter.
#
#   check-repro.sh <record dir>      exit 0 = reproduced, 1 = mismatch, 2 = usage / missing input
set -euo pipefail
rec="${1:?usage: check-repro.sh <record dir>}"
rec="$(cd "$rec" && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
rc=0
stems=(mc_intact_rf260_rr400 ctl_intact_rf260_rr200 mc_prog_rf630_rr400 ctl_prog_rf630_rr1000)
# Physical-XRref nominals join whenever the record carries them; older records skip them.
for stem in mc_intact_rf260_rrphys mc_prog_rf630_rrphys; do
  [[ -f "$rec/$stem.json" ]] && stems+=("$stem")
done
for stem in "${stems[@]}"; do
  [[ -f "$rec/$stem.json" && -f "$rec/sets/$stem/report.json" ]] || { echo "check-repro: $stem missing in $rec" >&2; exit 2; }
  cp "$rec/$stem.cir" "$tmp/"
  # Keep each request's own `typical` sections (["typical"] on pre-#323 records,
  # ["typical","res_typical"] on records whose decks carry ppolyf_u devices).
  jq '.corners.process |= map(select(.name=="typical")) | .corners.supply_v={vdd33:[3.3]} | .corners.temperature_c=[25] | .monte_carlo.n=1' \
     "$rec/$stem.json" > "$tmp/$stem.json"
  klt sim --backend local --format json "$tmp/$stem.json" 2>/dev/null > "$tmp/$stem.local.json" || true
  want="$(jq -c '[.corners[]|select(.process=="typical" and .temperature_c==25 and .supply_v.vdd33==3.3 and .monte_carlo.sample_index==0)|
        {inj:.monte_carlo.injected[0].value, m:[.measurements[]|{name,value}]}][0]' "$rec/sets/$stem/report.json")"
  got="$(jq -c '[.corners[0]|{inj:.monte_carlo.injected[0].value, m:[.measurements[]|{name,value}]}][0]' "$tmp/$stem.local.json")"
  # the injected draw must be bit-identical; ngspice values may differ in the last digits between hosts
  if [[ "$(jq -c .inj <<<"$want")" == "$(jq -c .inj <<<"$got")" ]] && \
     jq -en --argjson a "$want" --argjson b "$got" '[range(0; $a.m|length) | (($a.m[.].value - $b.m[.].value)|fabs) < 1e-6] | all' >/dev/null; then
    echo "reproduced  $stem  draw=$(jq .inj <<<"$want")"
  else
    echo "MISMATCH    $stem  recorded=$want local=$got"; rc=1
  fi
done
exit $rc
