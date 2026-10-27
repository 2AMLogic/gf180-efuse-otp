# signoff

The block's verdict of record against the klayout-tools evidence tiers.

| File | Role |
|---|---|
| `block-manifest.json` | Block name, kind (`mixed-signal`) and the `evidence` map (only `1.digital` so far). |
| `block-manifest.signoff.json` | Committed `klt signoff --manifest` output: the verdict of record. Item 1 (digital) is `met`; every other row, for both partitions, is `unmet` / `no_evidence`. |
| `klt-pin.txt` | The single place the grader version is pinned. CI installs `$(cat signoff/klt-pin.txt)`. |
| `item1-digital-inventory.json` | `t1-attestation-inventory` for T1 item 1, digital: the RTL source and the committed gate-level netlist `rtl/efuse_otp_ctrl.gl.v`, whose freshness `check` is `rtl/regen-gl.sh --check` (`local_only`: it needs Yosys and the PDK). |
| `item1-digital.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.digital` in `block-manifest.json`, pinned by the inventory's sha256. |
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

## What CI does and does not check

`.github/workflows/ci.yml` installs only Python and the pinned klt (no PDK,
ngspice, xschem or klayout). It checks that:

- the checker self-tests still reject seeded-bad input;
- each evidence directory has a `README.md`, and any `sim/**/records/*.json`
  has the required fields, a PDK revision, and repo-relative paths only
  (vacuously true while there are no records);
- files under `sim/**/records/` are only added, never modified, deleted or renamed;
- re-grading the manifest reproduces the committed record byte for byte.

**CI does not check that any evidence is correct.** It checks formats,
append-only history, and that the record reproduces.
