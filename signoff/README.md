# signoff

The block's verdict of record against the klayout-tools evidence tiers.

| File | Role |
|---|---|
| `attest/item10.json` | `t1-attestation-inventory` for T1 item 10, repo hygiene: the hygiene files and the bare-runner harness checks (checker self-tests, evidence-format check). |
| `attest/item10.envelope.json` | Envelope emitted by `klt signoff --attest 10`; cited for `10` in `block-manifest.json`, pinned by the inventory's sha256. |
| `attest/item9.json` | `t1-attestation-inventory` for T1 item 9, testbenches shipped: the controller, program-select and sense-margin bench files, the cold-start command `sim/cold-start.sh` (`local_only`), and the PDK and tool pins. |
| `attest/item9.envelope.json` | Envelope emitted by `klt signoff --attest 9`; cited for `9` in `block-manifest.json`, pinned by the inventory's sha256. |
| `block-manifest.json` | Block name, kind (`mixed-signal`), the `partition_boundary` (analog and digital nets) and the `evidence` map (`1.digital`, `1.analog`, `2.digital`, `2.analog`, `9`, `10`). |
| `item2-analog.attest.json` | Hand-written generic envelope for T1 item 2, analog: binds `layout/efuse_otp_array.gds` by sha256 with a regeneration claim (`layout/regen-gds.sh`); cited for `2.analog`. |
| `block-manifest.signoff.json` | Committed `klt signoff --manifest` output: the verdict of record. Items 1, 2, 9 and 10 are `met` for both partitions; every other row, for both partitions, is `unmet` / `no_evidence`. |
| `../layout/drc-*.report.json` | Committed `klt drc` reports for T1 item 3 (`layout/drc.sh`). Both are `status: violations`, so item 3 is not cited and stays `unmet`; see `layout/README.md`, "DRC". |
| `klt-pin.txt` | The single place the grader version is pinned. CI installs `$(cat signoff/klt-pin.txt)`. |
| `item1-digital-inventory.json` | `t1-attestation-inventory` for T1 item 1, digital: the RTL source and the committed gate-level netlist `rtl/efuse_otp_ctrl.gl.v`, whose freshness `check` is `rtl/regen-gl.sh --check` (`local_only`: it needs Yosys and the PDK). |
| `item1-digital.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.digital` in `block-manifest.json`, pinned by the inventory's sha256. |
| `item1-analog-inventory.json` | `t1-attestation-inventory` for T1 item 1, analog: the xschem schematics and cell symbols in `design/` and the netlist `design/efuse_otp_array.spice`, whose freshness `check` is `design/regen-netlist.sh --check` (`local_only`: it needs xschem). |
| `item1-analog.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.analog`, pinned by the inventory's sha256. |
| `design-evidence-tiers.md` | Copy of the tiers doc shipped with the pinned klt (`klayout-tools==0.8.0`, `klayout_tools/data/design-evidence-tiers.md`), so the record does not move when an installed klt bundles a different doc. |

## Regenerate the record

Always with the pinned release, never a host-installed `klt`:

```sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff \
  --manifest signoff/block-manifest.json \
  --tiers-doc signoff/design-evidence-tiers.md \
  --format json > signoff/block-manifest.signoff.json
```

Exit 3 means the report was produced with items unmet; that is the expected
state. Any other non-zero exit is a failure.

To bump the pin: change `klt-pin.txt`, replace `design-evidence-tiers.md` with
the copy shipped in the new release, regenerate, and commit all three together.
The committed netlist is a product of the pinned klt, so also run
`rtl/regen-gl.sh` and re-attest (below) in the same commit.

## Re-attest item 1 (digital)

After any change to `rtl/efuse_otp_ctrl.v`, `rtl/synth-request.json` or the pin:

```sh
rtl/regen-gl.sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --attest 1 \
  --inventory signoff/item1-digital-inventory.json \
  -o signoff/item1-digital.attest.json
```

Then set the `content_hash` for `1.digital` in `block-manifest.json` to the
sha256 of `item1-digital-inventory.json` (the manifest pin is the inventory's
hash, not the envelope's), and regenerate the record as above. Verify a
committed envelope with `klt signoff --attest 1 --inventory ... --check
signoff/item1-digital.attest.json` (exit 3 = stale; the `local_only` freshness
check is carried from attest time, not re-run). The item 1 inventory schema has
no `pins` block (that is item 9), so the PDK and Yosys revision are recorded in
the inventory `description`.

## Re-attest item 9 (testbenches shipped)

After any edit to a bench file listed in `attest/item9.json`, to `sim/cold-start.sh`
or to the pins:

```sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --attest 9 \
  --inventory signoff/attest/item9.json -o signoff/attest/item9.envelope.json
```

`--attest` runs `sim/cold-start.sh` (controller bench, then `--dry-run` of the two
analog request sets), so it needs the PDK, ngspice, Icarus and Yosys. Then set the
`content_hash` for `9` in `block-manifest.json` to the sha256 of `attest/item9.json`
and regenerate the record as above. CI runs `--check`, which re-hashes the bench files
and re-checks the pins but does not re-run the `local_only` cold start. The attestation
shows the benches exist, are pinned and launch; it says nothing about whether any
margin or current passes.

## Re-attest item 10 (repo hygiene)

After any edit to `README.md`, `LICENSE`, `.github/workflows/ci.yml`,
`spec/efuse-otp.md` or `attest/item10.json`:

```sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --attest 10 \
  --inventory signoff/attest/item10.json -o signoff/attest/item10.envelope.json
```

Then set the `content_hash` for `10` in `block-manifest.json` to the sha256 of
`attest/item10.json`, and regenerate the record as above. CI runs
`--check signoff/attest/item10.envelope.json`, so editing a hygiene file without
re-attesting fails (exit 3 = stale).
## Re-attest item 1 (analog)

After any change to `design/*.sch`, `design/*.sym` or the pin:

```sh
design/regen-netlist.sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --attest 1 \
  --inventory signoff/item1-analog-inventory.json \
  -o signoff/item1-analog.attest.json
```

Then set the `content_hash` for `1.analog` in `block-manifest.json` to the sha256
of `item1-analog-inventory.json` and regenerate the record as above. CI re-hashes
the sources and the netlist with `--check`; it does not re-run xschem.

## Re-attest item 2 (digital)

After any change to `rtl/efuse_otp_ctrl.gl.v`, `layout/pnr-request.json` or the pin:

```sh
layout/pnr.sh
layout/attest.sh
```

Then set the `content_hash` for `2.digital` in `block-manifest.json` to the
`provenance.input.content_hash` in `layout/pnr.attest.json` (the GDS sha256), and
regenerate the record as above. klt's `--attest` covers items 1, 9 and 10 only, so
this envelope is written by `layout/attest.sh`; the grader checks that the GDS
re-hashes to the pinned value and that the geometry digest matches the claim.
It does not re-run the flow: `layout/pnr.sh --check --rerun` does.

## Re-attest item 2 (analog layout)

After any change to `layout/gen_efuse_otp.py`, `design/efuse_otp_array.spice` or
the pin:

```sh
layout/regen-gds.sh
```

`klt signoff --attest` has no producer for item 2 (klayout-tools#4188, #4221),
so `item2-analog.attest.json` is a hand-written generic envelope: `t1_item` 2,
`provenance.input` the stream and its sha256, and a `provenance.regeneration`
claim carrying the same hash (the grader never runs the generator). Set the new
sha256 (from `layout/efuse_otp_array.gds.sha256`) in `provenance.input.content_hash`,
in `provenance.regeneration.regenerated_hash` and as the `content_hash` for
`2.analog` in `block-manifest.json`, then regenerate the record as above. The
claim is the stream's existence and reproducibility only; it makes no DRC, LVS
or connectivity statement.

## What CI does and does not check

`.github/workflows/ci.yml` has two jobs. `harness` installs only Python and the
pinned klt (no PDK, ngspice, xschem or klayout); `controller` builds the pinned
Icarus 13.0 and Yosys 0.67 (`scripts/ci/install_eda.sh`, cached) and runs
`verification/run.sh`, its `--negative-control` and `rtl/synth.sh`. Together
they check that:

- the controller bench passes, the negative control catches every seeded
  defect, and synthesis reports zero latches;
- the committed item 10 and item 9 envelopes match a fresh attestation;

- the checker self-tests still reject seeded-bad input;
- each evidence directory has a `README.md`, and any `sim/**/records/*.json`
  has the required fields, a PDK revision, and repo-relative paths only
  (vacuously true while there are no records);
- files under `sim/**/records/` are only added, never modified, deleted or renamed;
- the item 1 (analog) attestation still reproduces (`--attest 1 --check`);
- re-grading the manifest reproduces the committed record byte for byte.

**CI does not check that any evidence is correct.** It checks formats,
append-only history, and that the record reproduces.
