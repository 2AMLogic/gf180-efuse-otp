# signoff

The block's verdict of record against the klayout-tools evidence tiers.

| File | Role |
|---|---|
| `attest/item10.json` | `t1-attestation-inventory` for T1 item 10, repo hygiene: the hygiene files and the bare-runner harness checks (checker self-tests, evidence-format check). |
| `attest/item10.envelope.json` | Envelope emitted by `klt signoff --attest 10`; cited for `10` in `block-manifest.json`, pinned by the inventory's sha256. |
| `attest/item8.json` | `t1-attestation-inventory` for T1 item 8, characterization report (klayout-tools 0.9.0 schema): the report `measurements/characterization/README.md`, the records each spec row cites, a presence check per cited record, and the controller Fmax, power and area bound per `klt sta` corner. P08, P09, P10 and C2 cite the graded post-#85 sense-margin corner reports (`sim/sense-margin/records/20261109T002043Z-f6eeac7`) and, for P10 and C2, the `sim/sense-mc` yield reports. Those citations say the bench evidence exists and is graded; the ranges behind it (A4-A6, reference-tolerance sigma) stay `ASSUMPTION`s in the report. |
| `attest/item8.envelope.json` | Envelope emitted by `klt signoff --attest 8`; cited for `8.analog` and `8.digital` in `block-manifest.json`, pinned by the inventory's sha256. |
| `attest/item9.json` | `t1-attestation-inventory` for T1 item 9, testbenches shipped: the controller, program-select and sense-margin bench files, the shared record-provenance module `sim/lib/bench_record.py` both analog summarizers import, the cold-start command `sim/cold-start.sh` (`local_only`), and the PDK and tool pins. |
| `attest/item9.envelope.json` | Envelope emitted by `klt signoff --attest 9`; cited for `9` in `block-manifest.json`, pinned by the inventory's sha256. |
| `block-manifest.json` | Block name, kind (`mixed-signal`), the `partition_boundary` (analog and digital nets) and the `evidence` map (`1.digital`, `1.analog`, `2.digital`, `2.analog`, `8.digital`, `8.analog`, `9`, `10`). |
| `item2-analog.attest.json` | Envelope emitted by `klt signoff --attest 2 --input layout/efuse_otp_array.gds` (via `layout/attest.sh`): binds the stream by sha256 with a regeneration claim (`layout/regen-gds.sh`); cited for `2.analog`. |
| `item6-digital-spec.json`, `item6-digital-statement.json` | Item 6, digital: the `not_applicable` form. The spec is a verbatim extract of the digital-bearing rows of `spec/efuse-otp.md` section 2, bound to it by sha256 (`signoff/check-item6-digital.sh`, run in CI); the statement gives each row's non-statistical class and reason. Both are hash-bound in `block-manifest.json` (`6.digital`). |
| `check-item6-digital.sh` | Fails when `spec/efuse-otp.md` changes (sha256) or an extract row no longer matches a line of it. Run after any spec change, re-derive the extract, then re-hash the manifest. |
| `block-manifest.signoff.json` | Committed `klt signoff --manifest` output: the verdict of record. Items 1, 2, 8, 9 and 10 are `met` for both partitions; item 5 is `met` (analog); item 6 is `met` (analog) and `not_applicable` (digital); every other T1 row is `unmet` / `no_evidence`, and the T2, T3 and T4 rows are `unmet` / `tier_not_supported`. Item 6 analog `met` means the campaign discipline holds for the cited `margin_v` evidence (recorded seed, sufficient samples, detected negative control); it does not say the sense row is established, see `sim/sense-mc/README.md`. |
| `../sim/sense-mc/records/20261105T084326Z-f6eeac7/yield/{intact,prog}.yield.json` | Item 6, analog: the cited `klt yield` reports (`margin_v` only, post-#85 comparator), one per fuse population, cited with `rows: [P10]` in `block-manifest.json` (`6.analog`). The `*.decision.yield.json` files in the same record are not cited. Item 5 analog cites the six `bench_*` sense-margin corner reports of `sim/sense-margin/records/20261109T002043Z-f6eeac7` for P10 (they declare `margin_v >= 0`, signed so positive is the correct side; the `control_*` reports are not cited, the 260 ohm control fails by design) and reads `met`. |
| `../layout/drc-*.report.json` | Committed `klt drc` reports for T1 item 3 (`layout/drc.sh`). Both are `status: clean` under the curated deck (deck hash `sha256:cf44de63...`, klt 0.9.0 — the pin). The 0.9.0 deck gained an `EF` `deck_scope` entry and checks seven eFuse-layer rules on the analog partition, but all 24 foundry `EF.01`–`EF.22b` IDs remain under `coverage.unmodeled_rules` (klayout-tools#4312, #4002), so item 3 is still not cited and stays `unmet`; see `layout/README.md`, "DRC", and #60. |
| `klt-pin.txt` | The single place the grader version is pinned. CI installs `$(cat signoff/klt-pin.txt)`. |
| `klt.sh` | The single sourced definition of how the scripts reach the pinned klt: reads `klt-pin.txt` once (resolved from its own location, not cwd), preflights `uvx` (exit 2), and defines `klt`, `klt_python`, `KLT_PIN`, `KLT_ARGV` and the `[yield]`-extras `KLT_YIELD` array. `verification/run.sh` keeps its own inline preflight by design: it is the exemplar and a content-hashed attestation input. |
| `test-klt.sh` | Self-test for `klt.sh` (run in `check:ci`): the `uvx`-absent exit 2 and message, the `[yield]` splice, `klt`/`klt_python` argv through a fake `uvx`, the pin read exactly once, `KLT_NO_FUNCTION=1`, and pin resolution from a foreign cwd. |
| `item1-digital-inventory.json` | `t1-attestation-inventory` for T1 item 1, digital: the RTL source and the committed gate-level netlist `rtl/efuse_otp_ctrl.gl.v`, whose freshness `check` is `rtl/regen-gl.sh --check` (`local_only`: it needs Yosys and the PDK). |
| `item1-digital.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.digital` in `block-manifest.json`, pinned by the envelope's own composite `provenance.input.content_hash` (see "Re-attest item 1 (digital)"). |
| `item1-analog-inventory.json` | `t1-attestation-inventory` for T1 item 1, analog: the xschem schematics and cell symbols in `design/` and the netlist `design/efuse_otp_array.spice`, whose freshness `check` is `design/regen-netlist.sh --check` (`local_only`: it needs xschem). |
| `item1-analog.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.analog`, pinned by the envelope's own composite `provenance.input.content_hash` (see "Re-attest item 1 (analog)"). |
| `design-evidence-tiers.md` | Copy of the tiers doc shipped with the pinned klt (`klayout-tools==0.9.0`, `klayout_tools/data/design-evidence-tiers.md`), so the record does not move when an installed klt bundles a different doc. |

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

The item 8 envelope hashes `block-manifest.signoff.json`, so **any** regeneration
that changes the record leaves it stale: re-attest item 8 (see "Re-attest item 8")
afterwards, then regenerate once more and confirm the record is byte-identical.
That second pass always is — items `8.*` are pinned by the inventory sha256, which
a re-attest does not touch — so the two converge in one round. CI enforces this
with an item 8 `--check` step.

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
`provenance.input.content_hash` of `item1-digital.attest.json`, and regenerate
the record as above. From 0.9.0 that value is a composite digest over the whole
input set (the sources plus the inventory file), **not** the sha256 of
`item1-digital-inventory.json`; pin the inventory's own hash and the grader
returns `unmet` / `stale_evidence`. Verify a committed envelope with
`klt signoff --attest 1 --inventory ... --check signoff/item1-digital.attest.json`
(exit 3 = stale; the `local_only` freshness check is carried from attest time,
not re-run). The item 1 inventory schema has no `pins` block (that is item 9),
so the PDK and Yosys revision are recorded in the inventory `description`.

## Re-attest item 9 (testbenches shipped)

After any edit to a bench file listed in `attest/item9.json`, to `sim/cold-start.sh`
or to the pins:

```sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --attest 9 \
  --inventory signoff/attest/item9.json -o signoff/attest/item9.envelope.json
```

`--attest` runs `sim/cold-start.sh` (controller bench, then `--dry-run` of the two
analog request sets), so it needs the PDK, ngspice and Icarus. Then set the
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

## Re-attest item 8 (characterization report)

After any edit to `measurements/characterization/README.md` or `attest/item8.json`:

```sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --attest 8 \
  --inventory signoff/attest/item8.json -o signoff/attest/item8.envelope.json --format json
```

Pass `--format json`: 0.9.0's text renderer has no branch for `citation` checks, so they fall through to its pin-rendering branch, which reads a `value` key a *passing* citation check does not carry — `KeyError: 'value'`, exit 1 (`klayout_tools/signoff_attest_text.py:42`). One resolving citation is enough to trigger it, so the default text format always fails for item 8. The envelope is written before the renderer runs, so the file on disk is complete and only the exit status is wrong. Fixed upstream in klayout-tools#4941, after the pinned 0.9.0; a pin bump retires this workaround. Then set the `content_hash` for `8.analog` and `8.digital` in `block-manifest.json` to the sha256 of `attest/item8.json` and regenerate the record as above.

## Re-attest item 1 (analog)

After any change to `design/*.sch`, `design/*.sym` or the pin:

```sh
design/regen-netlist.sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --attest 1 \
  --inventory signoff/item1-analog-inventory.json \
  -o signoff/item1-analog.attest.json
```

Then set the `content_hash` for `1.analog` in `block-manifest.json` to the
`provenance.input.content_hash` of `item1-analog.attest.json` — the composite over
the input set, not the sha256 of `item1-analog-inventory.json`, the same rule as
item 1 digital above — and regenerate the record as above. CI re-hashes
the sources and the netlist with `--check`; it does not re-run xschem.

## Re-attest item 2 (both layout streams)

`layout/attest.sh` writes both item 2 envelopes with the pinned klt's own
producer, `klt signoff --attest 2 --input <stream>`: `layout/pnr.attest.json`
from `layout/efuse_otp_ctrl.gds` and `signoff/item2-analog.attest.json` from
`layout/efuse_otp_array.gds`. Re-attest after regenerating either stream —
digital, after a change to `rtl/efuse_otp_ctrl.gl.v`, `layout/pnr-request.json`
or the pin; analog, after a change to `layout/gen_efuse_otp.py`,
`design/efuse_otp_array.spice` or the pin:

```sh
layout/pnr.sh        # digital: refuses to write unless the P&R response passes
layout/regen-gds.sh  # analog
layout/attest.sh     # rewrites both envelopes
```

Then set the `content_hash` for `2.digital` and `2.analog` in
`block-manifest.json` to each envelope's `provenance.input.content_hash` (the
stream's own sha256) and regenerate the record as above. CI runs
`layout/attest.sh --check`, which re-attests both streams and exits 3 if either
committed envelope has drifted.

Each envelope carries a `provenance.regeneration` claim naming its generator;
the grader re-hashes the stream and compares the claim, but it never runs the
generator. The analog claim is the stream's raw-byte sha256 (`regen-gds.sh
--check` byte-compares). The digital claim is `hash_kind: geometry` — the
decoded-geometry digest, so GDS write times do not matter — and klt exposes no
public way to compute that value (klayout-tools#5551), so `layout/attest.sh`
reads it from klt's private `_provenance`; that single line is the only
private-API use left here, and a pin bump can break it. Neither envelope
re-runs the flow (`layout/pnr.sh --check --rerun` does) and neither makes a DRC,
LVS or connectivity statement: the three checks are the stream's readability, a
non-empty top cell and an on-grid database unit. See `layout/README.md`,
"What is not claimed".

## What CI does and does not check

`.github/workflows/ci.yml` has two jobs. `harness` installs only Python, the
pinned klt and `uv` (no PDK, ngspice or xschem; the KLayout Python module comes
with the pinned klt, which is how `--attest 2` reads a stream); `controller` builds the pinned
Icarus 13.0 and Yosys 0.67 (`scripts/ci/install_eda.sh`, cached), installs `uv`
(the bench reaches the pinned klt through `uvx`) and runs
`verification/run.sh`, its `--negative-control` and `rtl/synth.sh`. Together
they check that:

- the controller bench passes, the negative control catches every seeded
  defect, and no latch cell survives generic synthesis;
- the committed item 10 and item 9 envelopes match a fresh attestation;

- the checker self-tests still reject seeded-bad input;
- each evidence directory has a `README.md`, and any `sim/**/records/*.json`
  has the required fields, a PDK revision, and repo-relative paths only
  (vacuously true while there are no records);
- files under `sim/**/records/` are only added, never modified, deleted or renamed;
- the item 1 (analog) attestation still reproduces (`--attest 1 --check`);
- both item 2 attestations still reproduce (`layout/attest.sh --check`, i.e.
  `--attest 2 --check` on each stream); the generators named in their
  regeneration claims need OpenROAD and the PDK and are not re-run;
- the item 8 envelope's recorded hash of `block-manifest.signoff.json` is current
  (`--attest 8 --check --format json`), so regenerating the record without
  re-attesting item 8 fails;
- re-grading the manifest reproduces the committed record byte for byte.

**CI does not check that any evidence is correct.** It checks formats,
append-only history, and that the record reproduces.
