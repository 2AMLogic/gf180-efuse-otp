#!/usr/bin/env bash
# Write the two T1 item 2 (Layout) attestation envelopes with the pinned klt's
# own producer, `klt signoff --attest 2 --input <stream>`:
#   layout/pnr.attest.json            digital, binds layout/efuse_otp_ctrl.gds
#   signoff/item2-analog.attest.json  analog,  binds layout/efuse_otp_array.gds
# Each carries a regeneration claim naming its generator (echoed, never run by
# the grader). The digital claim is a geometry digest, so GDS write times do not
# matter; klt has no public source for that digest (klayout-tools#5551), so the
# one command below reads it from the private klayout_tools._provenance. Every
# other field of both envelopes comes from the producer.
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

# The only private-API use left in this repo; see klayout-tools#5551.
geometry_digest=$(klt_python -I -c '
import sys
from klayout_tools._provenance import layout_geometry_digest
digest = layout_geometry_digest(sys.argv[1])
if digest is None:
    sys.exit("no geometry digest for " + sys.argv[1])
print(digest)
' layout/efuse_otp_ctrl.gds)

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
