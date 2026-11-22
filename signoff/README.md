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
| `block-manifest.json` | Block name, kind (`mixed-signal`), the `partition_boundary` (analog and digital nets) and the `evidence` map (`1.digital`, `1.analog`, `2.digital`, `2.analog`, `4.digital`, `5.digital`, `5.analog`, `6.analog`, `6.digital`, `8.digital`, `8.analog`, `9`, `10`). |
| `item2-analog.attest.json` | Envelope emitted by `klt signoff --attest 2 --input layout/efuse_otp_array.gds` (via `layout/attest.sh`): binds the stream by sha256 with a regeneration claim (`layout/regen-gds.sh`); cited for `2.analog`. |
| `item6-digital-spec.json`, `item6-digital-statement.json` | Item 6, digital: the `not_applicable` form. The spec is a verbatim extract of the digital-bearing rows of `spec/efuse-otp.md` section 2, bound to it by sha256 (`signoff/check-item6-digital.sh`, run in CI); the statement gives each row's non-statistical class and reason. Both are hash-bound in `block-manifest.json` (`6.digital`). |
| `check-item6-digital.sh` | Fails when `spec/efuse-otp.md` changes (sha256) or an extract row no longer matches a line of it. Run after any spec change, re-derive the extract, then re-hash the manifest. |
| `block-manifest.signoff.json` | Committed `klt signoff --manifest` output: the verdict of record. Items 1, 2, 8, 9 and 10 are `met` for both partitions; item 5 is `met` (analog) and `met` (digital — cites `sim/controller-sta/sta-100ns.ddba55a3.report.json` and the `sim/controller-fv` reports; the 10 ns report is out-of-spec headroom under decision 0006 and is not cited); item 6 is `met` (analog) and `not_applicable` (digital); item 4 is `met` (digital, cited `layout/lvs-ctrl.report.json`); every other T1 row is `unmet` / `no_evidence`, and the T2, T3 and T4 rows are `unmet` / `tier_not_supported`. Item 6 analog `met` means the campaign discipline holds for the cited `margin_v` evidence (recorded seed, sufficient samples, detected negative control); it does not say the sense row is established, see `sim/sense-mc/README.md`. |
| `../sim/sense-mc/records/20261105T084326Z-f6eeac7/yield/{intact,prog}.yield.json` | Item 6, analog: the cited `klt yield` reports (`margin_v` only, post-#85 comparator), one per fuse population, cited with `rows: [P10]` in `block-manifest.json` (`6.analog`). The `*.decision.yield.json` files in the same record are not cited. Item 5 analog cites the six `bench_*` sense-margin corner reports of `sim/sense-margin/records/20261109T002043Z-f6eeac7` for P10 (they declare `margin_v >= 0`, signed so positive is the correct side; the `control_*` reports are not cited, the 260 ohm control fails by design) and reads `met`. |
| `../layout/drc-*.report.json` | T1 item 3 stays uncited. Both partition reports are clean under the curated deck. The full native reports have 253 array and 9 controller violations. See [layout DRC results](../layout/README.md#drc-t1-item-3) and [#60](https://github.com/2AMLogic/gf180-efuse-otp/issues/60). |
| `../layout/lvs-ctrl.report.json` | Committed `klt lvs` report for T1 item 4, digital (`layout/lvs.sh`): `status: match` with `power_connectivity.status: match` against `layout/efuse_otp_ctrl.asbuilt.v` under the curated deck (same deck hash as the DRC reports, klt 0.9.2 — the pin), cited for `4.digital`. What the `match` reaches (and does not) is in `layout/README.md`, "LVS"; the re-run procedure is below. |
| `klt-pin.txt` | The single place the grader version is pinned. CI installs `$(cat signoff/klt-pin.txt)`. |
| `klt.sh` | The single sourced definition of how the scripts reach the pinned klt: reads `klt-pin.txt` once (resolved from its own location, not cwd), preflights `uvx` (exit 2), and defines `klt`, `klt_python`, `KLT_PIN`, `KLT_ARGV` and the `[yield]`-extras `KLT_YIELD` array. The `--no-function` source argument (`. signoff/klt.sh --no-function`; skip the functions, keep `KLT_PIN`/`KLT_YIELD` -- the shape `sim/sense-mc/run.sh` uses) is the opt-out: an argument is passed to the sourced file alone and cannot be inherited, so no environment variable can take a signoff script off the pinned klt. `verification/run.sh` keeps its own inline preflight by design: it is the exemplar and a content-hashed attestation input. |
| `test-klt.sh` | Self-test for `klt.sh` (run in `check:ci`): the `uvx`-absent exit 2 and message, the `[yield]` splice, `klt`/`klt_python` argv through a fake `uvx`, the pin read exactly once and actually exported (the `declare -x` attribute, not mere set-ness), the `--no-function` source argument versus a non-opt-out argument and no argument, and the issue-#225 env-var shapes (an export, an export reassigned sourcing-locally, a `declare -ix` export, empty and `0`) proved unable to remove the function facets, the invariant that no caller handles `--no-function` as its own first parameter (every file sourcing `klt.sh` is scanned, with a fixture negative control), and pin resolution from a foreign cwd. |
| `item1-digital-inventory.json` | `t1-attestation-inventory` for T1 item 1, digital: the RTL source and the committed gate-level netlist `rtl/efuse_otp_ctrl.gl.v`, whose freshness `check` is `rtl/regen-gl.sh --check` (`local_only`: it needs Yosys and the PDK). |
| `item1-digital.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.digital` in `block-manifest.json`, pinned by the envelope's own composite `provenance.input.content_hash` (see "Re-attest item 1 (digital)"). |
| `item1-analog-inventory.json` | `t1-attestation-inventory` for T1 item 1, analog: the xschem schematics and cell symbols in `design/` and the netlist `design/efuse_otp_array.spice`, whose freshness `check` is `design/regen-netlist.sh --check` (`local_only`: it needs xschem). |
| `item1-analog.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.analog`, pinned by the envelope's own composite `provenance.input.content_hash` (see "Re-attest item 1 (analog)"). |
| `design-evidence-tiers.md` | Copy of the tiers doc shipped with the pinned klt (`klayout-tools==0.9.2`, `klayout_tools/data/design-evidence-tiers.md`), so the record does not move when an installed klt bundles a different doc. |

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
  --inventory signoff/attest/item8.json -o signoff/attest/item8.envelope.json
```

0.9.0's text renderer had no branch for `citation` checks: they fell through to its pin-rendering branch, which reads a `value` key a *passing* citation check does not carry — `KeyError: 'value'`, exit 1 (`klayout_tools/signoff_attest_text.py:42`) — so item 8 was attested with `--format json` as a workaround. One resolving citation was enough to trigger it, and the envelope was written before the renderer ran, so the file on disk was complete and only the exit status was wrong. Fixed upstream in klayout-tools#4941; the workaround was retired at pin 0.9.2 (#257), where the text format exits 0 on a passing item 8. Then set the `content_hash` for `8.analog` and `8.digital` in `block-manifest.json` to the sha256 of `attest/item8.json` and regenerate the record as above.

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
decoded-geometry digest that `klt stats --format json` reports as
`geometry_digest`, so GDS write times do not matter. Neither envelope
re-runs the flow (`layout/pnr.sh --check --rerun` does) and neither makes a DRC,
LVS or connectivity statement: the three checks are the stream's readability, a
non-empty top cell and an on-grid database unit. See `layout/README.md`,
"What is not claimed".

## Re-run the controller LVS (item 4, digital)

`layout/lvs.sh` runs `klt lvs` on `layout/efuse_otp_ctrl.gds` against the
as-built netlist `layout/efuse_otp_ctrl.asbuilt.v` with the pinned klt and
keeps the report (`layout/lvs-ctrl.report.json`) as found; `--check` re-hashes
the stream, the netlist and the deck against the committed report (`--rerun`
re-runs the compare). It needs the PDK. The gate-level reference resolves each standard cell's pin order
from the library's own spice/cdl under `<PDK_ROOT>/gf180mcuD/libs.ref`, so
CI (which installs no PDK) cannot run it — the same local-only class as
`rtl/regen-gl.sh`. `PDK_ROOT` defaults to `~/.ciel`, `layout/pnr.sh`'s
default, and is passed to klt explicitly (`reference.pdk_root`) so the
report records one resolved install instead of an ambiguous search.

Re-run it after anything that changes the routed stream or the as-built
netlist (i.e. after `layout/pnr.sh` writes new ones). If the fresh report is
again `status: match` with `power_connectivity.status: match`, update the
`4.digital` `content_hash` in `block-manifest.json` to the report's
`provenance.input.content_hash` — the stream's own sha256, **not** the report
file's own digest, the same rule every other entry follows — and regenerate
the record. That changes the record, so finish with the item 8 round trip
under "Regenerate the record" (re-attest item 8, regenerate once more,
byte-identical). A `status: mismatch` report is committed uncited instead,
`4.digital` stays `unmet`, and the mismatch classes are listed in
`layout/README.md`, "LVS".

## What CI does and does not check

`.github/workflows/ci.yml` has two jobs. `harness` installs only Python, the
pinned klt, `uv` and `jq`
(no PDK, ngspice or xschem; the KLayout Python module comes
with the pinned klt, which is how `--attest 2` reads a stream); `controller` builds the pinned
Icarus 13.0 and Yosys 0.67 (`scripts/ci/install_eda.sh`, cached), installs `uv`
(the bench reaches the pinned klt through `uvx`) and runs
`verification/run.sh`, its `--negative-control` and `rtl/synth.sh`. Together
they check that:

- the controller bench passes, the negative control catches every seeded
  defect, and no latch cell survives generic synthesis;
- the committed item 10 and item 9 envelopes match a fresh attestation;
- the checker self-tests still reject seeded-bad input;
- the `decision-0005` PVT corner grid exported by `sim/lib/pdk_env.sh` still
  matches the ratified `pvt-corners` row of the spec, parsed through the item 6
  extract (`signoff/check-pvt-grid.sh`);
- the `pdk_env.sh` self-test still passes (`sim/lib/test_pdk_env.sh`, hermetic
  fake trees and a stubbed `klt` on `PATH`);
- the attestation-envelope pin check still passes
  (`scripts/ci/check_attest_pins.py` re-hashes every attested path pin,
  composite and manifest binding);
- the klt helper self-test still passes (`signoff/test-klt.sh`, hermetic: it
  fakes `uvx` on `PATH` and asserts on the argv the pinned-klt facets emit, so
  it never invokes a real `klt`);
- the bench-record loader self-test still passes
  (`sim/lib/test_bench_record.py`, hermetic: hand-built fixtures in a temp
  directory, pins that a partial report set is refused with exit 4 before
  anything is returned);
- the program-select summarize self-test still passes
  (`sim/program-select/test_summarize.py`, hermetic, pins that the record
  describes the submitted grid rather than whatever reports are present);
- the sense-margin summarize self-test still passes
  (`sim/sense-margin/test_summarize.py`, hermetic, pins that the record
  describes the submitted request set rather than whatever reports are present);
- each evidence directory has a `README.md`, and any `sim/**/records/*.json`
  has the required fields, a PDK revision, and repo-relative paths only
  (vacuously true while there are no records);
- files under `sim/**/records/` are only added, never modified, deleted or renamed;
- each `layout/*report*.json` that records a `provenance.input.content_hash`
  still names a stream whose sha256 equals it
  (`scripts/ci/check_report_inputs.py`), so a report that was not re-run
  after its stream was regenerated fails. The step reads the report's own
  `provenance.input.role` to find the stream (`.file.path`, `.layout.path`
  or `.netlist.path`); it does not re-run `layout/drc.sh`, `layout/pnr.sh`
  or any flow, and it does not check the deck hash -- the deck hash is
  engine-dependent while `signoff/klt-pin.txt` does not constrain the
  engine (klayout-tools#5601), so only the engine-independent input hash is
  gated;
- every cell of each committed stream (`layout/efuse_otp_array.gds` and
  `layout/efuse_otp_ctrl.gds`) has zero via2 shapes with no M3 above or no M2
  below (`layout/check_via2_landing.sh`, counted per cell with the pinned klt's
  klayout). The deck does not model the `V2.3c`, `V2.3d`, `V2.4b` or `V2.4c`
  rules, so this count is the only gate for that class on those streams; it
  runs on the committed streams and does not regenerate them;
- the item 6 digital extract is still bound to the ratified
  `spec/efuse-otp.md` (`signoff/check-item6-digital.sh`): the spec's sha256
  matches the extract's recorded hash and every quoted row still appears
  verbatim; the digital flow that produced the item is not re-run;
- the item 1 (analog) attestation still reproduces (`--attest 1 --check`);
- both item 2 attestations still reproduce (`layout/attest.sh --check`, i.e.
  `--attest 2 --check` on each stream); the generators named in their
  regeneration claims need OpenROAD and the PDK and are not re-run;
- the item 8 envelope's recorded hash of `block-manifest.signoff.json` is current
  (`--attest 8 --check`), so regenerating the record without
  re-attesting item 8 fails;
- re-grading the manifest reproduces the committed record byte for byte.

**CI does not check that any evidence is correct.** It checks formats,
append-only history, and that the record reproduces.
