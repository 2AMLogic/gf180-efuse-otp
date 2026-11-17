#!/usr/bin/env bash
# Write the two T1 item 2 (Layout) attestation envelopes with the pinned klt's
# own producer, `klt signoff --attest 2 --input <stream>`:
#   layout/pnr.attest.json            digital, binds layout/efuse_otp_ctrl.gds
#   signoff/item2-analog.attest.json  analog,  binds layout/efuse_otp_array.gds
# Each carries a regeneration claim naming its generator (echoed, never run by
# the grader). The digital claim is a geometry digest, so GDS write times do not
# matter; it is the `geometry_digest` of `klt stats --format json`, read below.
# Every field of both envelopes comes from klt.
#   layout/attest.sh           rewrite both envelopes
#   layout/attest.sh --check   fail (exit 3) if either committed envelope differs
# The P&R response's own pass conditions (status ok, stage route, power.pdn true,
# zero route DRC and antenna violations) are asserted by layout/pnr.sh, which
# refuses to write the report or the GDS unless they hold.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../signoff/klt.sh
. signoff/klt.sh
mode=(-o)
[ "${1:-}" = "--check" ] && mode=(--check)

geometry_digest=$(klt stats --format json layout/efuse_otp_ctrl.gds | python3 -I -c '
import json, sys
digest = json.load(sys.stdin).get("geometry_digest")
if not digest:
    sys.exit("klt stats reported no geometry_digest")
print(digest)
')

klt signoff --attest 2 \
  --input layout/efuse_otp_ctrl.gds \
  --generator layout/pnr.sh \
  --regenerated-hash "$geometry_digest" --hash-kind geometry \
  "${mode[@]}" layout/pnr.attest.json --no-color

klt signoff --attest 2 \
  --input layout/efuse_otp_array.gds \
  --generator layout/regen-gds.sh \
  --regenerated-hash "sha256:$(cut -d' ' -f1 < layout/efuse_otp_array.gds.sha256)" \
  "${mode[@]}" signoff/item2-analog.attest.json --no-color
