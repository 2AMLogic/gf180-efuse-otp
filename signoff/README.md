# signoff

The block's verdict of record against the klayout-tools evidence tiers.

| File | Role |
|---|---|
| `attest/item10.json` | `t1-attestation-inventory` for T1 item 10, repo hygiene: the hygiene files and the bare-runner harness checks (checker self-tests, evidence-format check). |
| `attest/item10.envelope.json` | Envelope emitted by `klt signoff --attest 10`; cited for `10` in `block-manifest.json`, pinned by the inventory's sha256. |
| `attest/item8.json` | `t1-attestation-inventory` for T1 item 8, characterization report (klayout-tools 0.9.0 schema): the report `measurements/characterization/README.md`, the records each spec row cites, a presence check per cited record, and the controller Fmax, power and area bound per `klt sta` corner. P08, P09, P10 and C2 cite the graded post-#85 sense-margin corner reports (`sim/sense-margin/records/20261109T002043Z-f6eeac7`) and, for P10 and C2, the `sim/sense-mc` yield reports; P02 and P13 cite the committed partition DRC reports, curated and PDK-native. Those citations say the bench evidence exists and is graded; the ranges behind it (A4-A6, reference-tolerance sigma) stay `ASSUMPTION`s in the report. |
| `attest/item8.envelope.json` | Envelope emitted by `klt signoff --attest 8`; cited for `8.analog` and `8.digital` in `block-manifest.json`, pinned by the inventory's sha256. |
| `attest/item9.json` | `t1-attestation-inventory` for T1 item 9, testbenches shipped: the controller, program-select and sense-margin bench files, the shared record-provenance module `sim/lib/bench_record.py` both analog summarizers import, the cold-start command `sim/cold-start.sh` (`local_only`), and the PDK and tool pins. |
| `attest/item9.envelope.json` | Envelope emitted by `klt signoff --attest 9`; cited for `9` in `block-manifest.json`, pinned by the inventory's sha256. |
| `block-manifest.json` | Block name, kind (`mixed-signal`), the `partition_boundary` (analog and digital nets) and the `evidence` map (`1.digital`, `1.analog`, `2.digital`, `2.analog`, `3.analog`, `3.digital`, `4.digital`, `5.digital`, `5.analog`, `6.analog`, `6.digital`, `8.digital`, `8.analog`, `9`, `10`, `11.digital`). |
| `item2-analog.attest.json` | Envelope emitted by `klt signoff --attest 2 --input layout/efuse_otp_array.gds` (via `layout/attest.sh`): binds the stream by sha256 with a regeneration claim (`layout/regen-gds.sh`); cited for `2.analog`. |
| `item6-digital-spec.json`, `item6-digital-statement.json` | Item 6, digital: the `not_applicable` form. The spec is a verbatim extract of the digital-bearing rows of `spec/efuse-otp.md` section 2, bound to it by sha256 (`signoff/check-item6-digital.sh`, run in CI); the statement gives each row's non-statistical class and reason. Both are hash-bound in `block-manifest.json` (`6.digital`). |
| `check-item6-digital.sh` | Fails when `spec/efuse-otp.md` changes (sha256) or an extract row no longer matches a line of it. Run after any spec change, re-derive the extract, then re-hash the manifest. |
| `block-manifest.signoff.json` | Committed `klt signoff --manifest` output: the verdict of record. Items 1, 2, 3, 8, 9 and 10 are `met` for both partitions (item 3 through the compound curated-plus-native DRC citations below); item 5 is `met` (analog) and `met` (digital — cites `sim/controller-sta/sta-100ns.ddba55a3.report.json` and the `sim/controller-fv` reports; the 10 ns report is out-of-spec headroom under decision 0006 and is not cited); item 6 is `met` (analog) and `not_applicable` (digital); item 4 is `met` (digital, cited `layout/lvs-ctrl.report.json`); item 11 is `met` (digital, the compound `erc`/`lvs`/`place-and-route` citation below); every other T1 row is `unmet` / `no_evidence`, and the T2, T3 and T4 rows are `unmet` / `tier_not_supported`. Item 6 analog `met` means the campaign discipline holds for the cited `margin_v` evidence (recorded seed, sufficient samples, detected negative control); it does not say the sense row is established, see `sim/sense-mc/README.md`. |
| `../sim/sense-mc/records/20261105T084326Z-f6eeac7/yield/{intact,prog}.yield.json` | Item 6, analog: the cited `klt yield` reports (`margin_v` only, post-#85 comparator), one per fuse population, cited with `rows: [P10]` in `block-manifest.json` (`6.analog`). The `*.decision.yield.json` files in the same record are not cited. Item 5 analog cites the six `bench_*` sense-margin corner reports of `sim/sense-margin/records/20261109T002043Z-f6eeac7` for P10 (they declare `margin_v >= 0`, signed so positive is the correct side; the `control_*` reports are not cited, the 260 ohm control fails by design) and reads `met`. |
| `../layout/drc-*.report.json` | T1 item 3, cited for both partitions as the two-member compound `[curated, native]` evidence list (`3.analog`: `layout/drc-array.report.json` + `layout/drc-array.native.report.json`; `3.digital`: `layout/drc-ctrl.report.json` + `layout/drc-ctrl.native.report.json`), each member pinned to its report's `provenance.input.content_hash` and graded `met` (`members_covered: 2`, `input_verified: true`; #60). Both members of both partitions are `status: "clean"` with 0 violations; the native reports check all 27 foundry `EF.*` rules with 0 eFuse markers. Each graded citation copies three fields from its report's `coverage` block (`layers_in_stream_without_rules`, `rules_skipped` and `deck_scope`). The item 3 disclosure below gives their values and explains the scope of each partition's result. See also [layout DRC results](../layout/README.md#drc-t1-item-3). |
| `../layout/lvs-ctrl.report.json` | Committed `klt lvs` report for T1 item 4, digital (`layout/lvs.sh`): `status: match` with `power_connectivity.status: match` against `layout/efuse_otp_ctrl.asbuilt.v` under the curated deck (same deck hash as the DRC reports, klt 0.9.2 — the pin), cited for `4.digital`. What the `match` reaches (and does not) is in `layout/README.md`, "LVS"; the re-run procedure is below. |
| `../layout/erc-ctrl.spec.json` | The `klt erc` supply spec for T1 item 11, digital: `VDD`/`VSS` as `kind: "supply"` nets, a stackup through every strap layer `layout/pnr-report.json` reports (Metal1-Metal5 with Contact/Via1-Via4), and the two well/substrate ties (n-well tap `Comp∩Nplus` in `Nwell` → VDD; p-substrate tap `Comp∩Pplus` outside `Nwell` → VSS). Layer numbers are the curated gf180mcu deck's own; the file documents each choice. |
| `../layout/erc-ctrl.report.json` | Committed `klt erc --findings-only` report for T1 item 11, digital (`layout/erc.sh`, pinned klt, `--deck gf180mcu`): `erc_status: clean`, `VDD` and `VSS` each `matched_islands: 1`, zero findings, no skipped or inapplicable work, `erc.supply_short.substrate` checked (the deck's DNWELL isolation makes the substrate pass decidable), input hash = the `efuse_otp_ctrl.gds` sha256. Cited as the leading `erc` part of the compound `11.digital` set beside `lvs-ctrl` and `pnr-report` (`klt signoff` grades the compound; the citation's `power_delivery` block records what it resolved). `layout/erc.sh --check` re-hashes input, spec and deck against it (CI runs this); `--negative-control` proves the spec can fail (CI runs this too). The antenna half is deliberately not graded (`status: not_checked`, klt exit 4): item 11 grades the `erc_findings` supply rules only. `erc_coverage.layers_in_stream_without_declaration` (quoted, claimant-enforced by item 11): `21/10`, `63/63`, `204/10`. Measured on the committed stream: all three carry text only and no polygons, so none is conductor or strap geometry and none is a declared stackup layer (Poly, Metal1-Metal5). `21/10` holds 1178 `VNW` texts and `204/10` 1178 `VPW` texts (the foundry cells' well-pin names), `63/63` holds 5684 foundry-library comment texts (`& Vendor`, `& Product`, `& Version`, `& Metric`, 1421 each). The list is a strict subset of the digital DRC `layers_in_stream_without_rules` row: the four that drop out are `34/10`, `36/10`, `81/10` (the spec's three `label_layers`) and `0/0` (1422 polygons, bounding boxes equal to cell pitch by row height, e.g. 560x3920 nm for `fill_1`, consistent with a cell outline); why klt's ERC list omits `0/0` was not investigated. The well ties are declared in the spec (`nwell_vdd`, `psub_vss`), not derived from these texts. |
| `../layout/erc-array.spec.json`, `../layout/erc-array.report.json` | Analog supply probe on the routed array. Each of `vdd33`, `vprog` and `vss` resolves to one island. The two n-well bias classes pass the tie check. KLT 0.9.2 reports `clean_partial` with zero findings and one skipped substrate tie. Drawn n-wells cover 0.9753% of the top extent, triggering the 1% threshold for the geometry-derived substrate. Removing Metal4 splits the three rails into 41, 41 and 73 islands respectively. `layout/erc.sh`, `--check` and `--negative-control` run both partitions. Item 11 analog remains open for substrate coverage and LVS supply pairing. [Upstream reproducer](https://github.com/2AMLogic/klayout-tools/issues/7942) |
| `klt-pin.txt` | The single place the grader version is pinned. CI installs `$(cat signoff/klt-pin.txt)`. |
| `klt.sh` | The single sourced definition of how the scripts reach the pinned klt: reads `klt-pin.txt` once (resolved from its own location, not cwd), preflights `uvx` (exit 2), and defines `klt`, `klt_python`, `KLT_PIN`, `KLT_ARGV` and the `[yield]`-extras `KLT_YIELD` array. The functions are unconditional -- the file reads neither the environment nor its positional parameters, so no inherited variable or caller argument can take a signoff script off the pinned klt; the one caller that wants a bare klt (`sim/sense-mc/run.sh`) unsets the functions itself right after sourcing. `verification/run.sh` keeps its own inline preflight by design: it is the exemplar and a content-hashed attestation input. |
| `test-klt.sh` | Self-test for `klt.sh` (run in `check:ci`): the `uvx`-absent exit 2 and message, the `[yield]` splice, `klt`/`klt_python` argv through a fake `uvx`, the pin read exactly once and actually exported (the `declare -x` attribute, not mere set-ness), the regression that neither an inherited `KLT_NO_FUNCTION` export nor a caller whose own first parameter is `--no-function` removes the function facets (they are unconditional, and still forward their argv), and pin resolution from a foreign cwd. |
| `check-pvt-grid.sh` | decision-0005 PVT grid binding check (run in `check:ci`): fails when the `pvt-corners` row of `item6-digital-spec.json` no longer appears verbatim as a line of `spec/efuse-otp.md`, or when the four `PVT_*` constants `sim/lib/pdk_env.sh` exports no longer equal the four axes parsed from that row (processes, temperatures, both supply triplets). Exit 1 = stale; after a spec amendment (which needs a decision record) update `sim/lib/pdk_env.sh` and the golden literals in `sim/lib/test_pdk_env.sh` together with the spec and its extract. |
| `item1-digital-inventory.json` | `t1-attestation-inventory` for T1 item 1, digital: the RTL source and the committed gate-level netlist `rtl/efuse_otp_ctrl.gl.v`, whose freshness `check` is `rtl/regen-gl.sh --check` (`local_only`: it needs Yosys and the PDK). |
| `item1-digital.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.digital` in `block-manifest.json`, pinned by the envelope's own composite `provenance.input.content_hash` (see "Re-attest item 1 (digital)"). |
| `item1-analog-inventory.json` | `t1-attestation-inventory` for T1 item 1, analog: the xschem schematics and cell symbols in `design/` and the netlist `design/efuse_otp_array.spice`, whose freshness `check` is `design/regen-netlist.sh --check` (`local_only`: it needs xschem). |
| `item1-analog.attest.json` | Envelope emitted by `klt signoff --attest 1` from that inventory; cited for `1.analog`, pinned by the envelope's own composite `provenance.input.content_hash` (see "Re-attest item 1 (analog)"). |

## T1 item 3 disclosure (DRC coverage quoted from the cited envelopes)

`3.analog` and `3.digital` cite a two-member compound evidence list per
partition — the curated report first, then the PDK-native report — each member
pinned by its report's `provenance.input.content_hash`. The SHA-256 prefixes
are `ec599bcc…` for `layout/efuse_otp_array.gds` and `b80bfb50…` for
`layout/efuse_otp_ctrl.gds`. Both members grade `met` with `status: "clean"`
and `input_verified: true`.

In the graded record, `citations[].coverage` copies three fields verbatim
from each report — `layers_in_stream_without_rules`, `rules_skipped` and
`deck_scope`. All three arrays are empty for each native citation. To verify
the 27 foundry `EF.*` rule IDs, read `coverage.rules_checked` in the cited
native DRC report. The claimant discloses the coverage gaps and scope below.
Reviewers assess that disclosure separately from the automated grade.

### Curated envelope, analog — `layout/drc-array.report.json`

- `coverage.layers_in_stream_without_rules` (8): `22/4`, `30/4`, `34/4`,
  `34/10`, `36/4`, `42/4`, `46/4`, `81/4`. The seven `/4` entries are the
  density-fill dummy datatypes (#310). `34/10` is the Metal1 label layer.
- `coverage.rules_skipped` (39): `bjt.separation.comp.1`, `cap_mk.ongrid.1`,
  `comp.separation.guard_ring_mk.1`, `diode_mk.ongrid.1`, `dnwell.ongrid.1`,
  `drc_bjt.ongrid.1`, `esd.area.1`, `esd.holes_area.1`, `esd.overlap.comp.1`,
  `esd.separation.nplus.1`, `esd.separation.pplus.1`, `esd.space.1`,
  `esd.width.1`, `fusetop.ongrid.1`, `ldmos_xtor.enclosing.mvpsd.1`,
  `metal1.separation.guard_ring_mk.1`, `metal2.separation.guard_ring_mk.1`,
  `metal3.separation.guard_ring_mk.1`, `metal4.separation.guard_ring_mk.1`,
  `metal5.separation.guard_ring_mk.1`, `metaltop.ongrid.1`,
  `metaltop.separation.guard_ring_mk.1`, `metaltop.space.1`,
  `metaltop.width.1`, `mim.enclosing.fusetop.1`, `mim.enclosing.via4.1`,
  `mim.space.1`, `mim_l_mk.ongrid.1`, `mvpsd.ongrid.1`, `mvsd.ongrid.1`,
  `mvsd.separation.dnwell.1`, `mvsd.width.1`, `nwell.separation.guard_ring_mk.1`,
  `pad.enclosing.metal5.1`, `pad.ongrid.1`, `plfuse.separation.esd.1`,
  `plfuse.separation.resistor.1`, `poly2.separation.guard_ring_mk.1`,
  `resistor.ongrid.1`. (With top-level M4/Via3/M5/Via4 routing in #307, the
  16 Metal4/Metal5/Via3/Via4 rules moved from `rules_skipped` into
  `rules_checked` — 87 checked, 0 violations.)
- `coverage.deck_scope` (19): 10.4.2 MIM Option B, 10.7 DRC_BJT Mark Layer,
  7.12 Contact, 7.13 Metaln, 7.14 Vian, 7.15 MetalTop, 7.4 Nwell, 7.5 Comp,
  7.7 Poly2, 7.8 Nplus, 7.9 Pplus, 9.1 Bond Pad, EF, ESD, GR, MDN, MDP,
  OFFGRID, SB.

### Curated envelope, digital — `layout/drc-ctrl.report.json`

- `coverage.layers_in_stream_without_rules` (14): `0/0`, `21/10`, `22/4`,
  `30/4`, `34/4`, `34/10`, `36/4`, `36/10`, `42/4`, `46/4`, `63/63`, `81/4`,
  `81/10`, `204/10`. The seven `/4` entries are the density-fill dummy
  datatypes (#310); the rest are text/outline layers (`0/0` cell outlines,
  `21/10`/`204/10` well-pin texts, `63/63` foundry comment texts, the
  `34/10`/`36/10`/`81/10` label layers — the same reading `layout/README.md`
  gives the ERC declaration list).
- `coverage.rules_skipped` (54): `bjt.separation.comp.1`, `cap_mk.ongrid.1`,
  `comp.separation.guard_ring_mk.1`, `comp.tap_distance.nwell.lv.1`,
  `comp.tap_distance.psub.lv.1`, `diode_mk.ongrid.1`, `dnwell.ongrid.1`,
  `drc_bjt.ongrid.1`, `efuse_mk.enclosing.lvs_source.1`, `efuse_mk.ongrid.1`,
  `efuse_mk.space.1`, `esd.area.1`, `esd.holes_area.1`, `esd.overlap.comp.1`,
  `esd.separation.nplus.1`, `esd.separation.pplus.1`, `esd.space.1`,
  `esd.width.1`, `fusetop.ongrid.1`, `ldmos_xtor.enclosing.mvpsd.1`,
  `metal1.separation.guard_ring_mk.1`, `metal2.separation.guard_ring_mk.1`,
  `metal3.separation.guard_ring_mk.1`, `metal4.separation.guard_ring_mk.1`,
  `metal5.separation.guard_ring_mk.1`, `metaltop.ongrid.1`,
  `metaltop.separation.guard_ring_mk.1`, `metaltop.space.1`,
  `metaltop.width.1`, `mim.enclosing.fusetop.1`, `mim.enclosing.via4.1`,
  `mim.space.1`, `mim_l_mk.ongrid.1`, `mvpsd.ongrid.1`, `mvsd.ongrid.1`,
  `mvsd.separation.dnwell.1`, `mvsd.width.1`, `nwell.separation.guard_ring_mk.1`,
  `pad.enclosing.metal5.1`, `pad.ongrid.1`, `plfuse.ongrid.1`,
  `plfuse.separation.comp.1`, `plfuse.separation.esd.1`,
  `plfuse.separation.nplus.1`, `plfuse.separation.resistor.1`,
  `plfuse.separation.sab.1`, `poly2.enclosing.sab.1`,
  `poly2.separation.guard_ring_mk.1`, `res_mk.ongrid.1`, `resistor.ongrid.1`,
  `sab.ongrid.1`, `sab.separation.contact.1`, `sab.space.1`, `sab.width.1`.
  All nine eFuse-layer rules are skipped here — the digital partition draws no
  `PLFUSE`/`EFUSE_MK`.
- `coverage.deck_scope` (19): identical to the analog list above.

### Native envelopes — `layout/drc-array.native.report.json`, `layout/drc-ctrl.native.report.json`

Both native envelopes record `coverage.layers_in_stream_without_rules: []`,
`coverage.rules_skipped: []` and `coverage.deck_scope: []`. Those three arrays
are the curated deck's introspection fields; the engine-native run (the PDK
main script `tech/drc/gf180mcu.drc`, `decks=all`) does not populate them and
klt leaves them empty rather than measuring a native equivalent. What the
native envelope records instead is `coverage.rules_checked`: 763 rule
categories with `coverage_assertion.satisfied: true`, including all 27 foundry
`EF.*` IDs. Of those, 24 appear in the curated deck's
`coverage.unmodeled_rules` (`EF.01`–`EF.03`, `EF.04a`–`EF.04d`,
`EF.05`–`EF.13`, `EF.15`, `EF.16a`, `EF.16b`, `EF.18`, `EF.19`, `EF.21`,
`EF.22a` and `EF.22b`). The other three are `EF.14`, `EF.17` and `EF.20`.

The native deck emits a global-density category only on a finding. Both
native reports have zero findings, so `DCF.1b`, `PL.8`, `M1.4`–`M5.4` and
`MT.3` are absent from `coverage.rules_checked`. For the array, the fill
generator records the layer ratios and passing bounds in
[`fill-array.report.json`](../layout/fill-array.report.json). For the
controller, the deck logger captured the ratios for all eight rules in a
standalone run. The [density table](../layout/README.md#density-fill-310)
lists the ratios beside each stream's SHA-256.

### Scope caveats on the `EF.*` zero-marker result

1. **The controller's 0 `EF.*` markers are vacuous.** `efuse_otp_ctrl` draws
   no `PLFUSE`/`EFUSE_MK`, so the foundry fuse rules have no geometry to act
   on in that stream; only `layout/efuse_otp_array.gds` exercises them.
2. **Analog LVS signoff remains separate.** All eight cells of the analog
   hierarchy — `efuse_bitcell`, `efuse_ls`, `efuse_rowdrv`, `efuse_coldrv`,
   `efuse_comp`, `efuse_sense`, `efuse_row` and the array top `efuse_otp_array`
   — are routed, filled and DRC-clean (0 markers across all 763 native rules
   including all 27 `EF.*` IDs). Recognized-fuse top-level LVS (`4.analog`)
   remains with #32.

## Regenerate the record

Always with the pinned release, never a host-installed `klt`:

```sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff \
  --manifest signoff/block-manifest.json \
  --format json > signoff/block-manifest.signoff.json
```

Exit 3 means the report was produced with items unmet; that is the expected
state. Any other non-zero exit is a failure.

The checklist itself comes from the pinned tool: `klt signoff` grades against
the design-evidence tiers doc shipped inside the pinned release
(`klayout-tools==0.9.2`;
[`docs/design-evidence-tiers.md`](https://github.com/2AMLogic/klayout-tools/blob/v0.9.2/docs/design-evidence-tiers.md)
at the tag — decision
[0008](../spec/decisions/0008-vendored-tiers-doc-removal.md)). The record's
`source_doc` names that doc by klt's source-relative label, not a path in this
repo, and `source_doc_content_hash` pins its content, so a checklist change at
a pin bump shows up in the re-grade `cmp` below and in CI.

The item 8 envelope hashes `block-manifest.signoff.json`, so **any** regeneration
that changes the record leaves it stale: re-attest item 8 (see "Re-attest item 8")
afterwards, then regenerate once more and confirm the record is byte-identical.
That second pass always is — items `8.*` are pinned by the inventory sha256, which
a re-attest does not touch — so the two converge in one round. CI enforces this
with an item 8 `--check` step.

To bump the pin: change `klt-pin.txt`, regenerate, and commit both together.
The committed netlist is a product of the pinned klt, so also run
`rtl/regen-gl.sh` and re-attest (below) in the same commit. The new release's
tiers doc replaces the old one inside the tool itself; nothing to copy.

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

After any edit to `measurements/characterization/README.md` or `attest/item8.json`, or to any file the inventory hashes (including the committed `layout/lvs-*.report.json` evidence):

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
`layout/efuse_otp_array.gds`. Re-attest after regenerating either stream.

- Regenerate the digital stream after a change to `rtl/efuse_otp_ctrl.gl.v`,
  `layout/pnr-request.json`, `layout/dbu_export.py` (the final export both
  producers share) or the pin.
- Run `layout/regen-gds.sh` when a change to code or inputs can affect the
  analog GDS. This includes `layout/gen_efuse_otp.py` and its imported drawing
  and routing modules, final export (`layout/dbu_export.py`), density fill
  (`layout/fill_partitions.py`), the source netlist (`design/efuse_otp_array.spice`)
  and the tool pin (`signoff/klt-pin.txt`).

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
the stream, the netlist and the deck against the committed report, and
`--check --rerun` re-runs the compare. It needs the PDK. The gate-level
reference resolves each standard cell's pin order from the library's own
spice/cdl under `<PDK_ROOT>/gf180mcuD/libs.ref`, so CI (which installs no
PDK) cannot run it — the same local-only class as `rtl/regen-gl.sh`.
`PDK_ROOT` defaults to `~/.ciel`, `layout/pnr.sh`'s default, and is passed
to klt explicitly (`reference.pdk_root`) so the report records one resolved
install instead of an ambiguous search. For the controller the rerun is the
script's, not klt's own: the committed report records
`reference_conversion.pdk_root` as the portable `$PDK_ROOT` token (the
request sets `portable_paths: true`), and pinned klt's `--check --rerun`
copies that token back into its reconstructed request verbatim, so its PDK
search resolves it as a cwd-relative path and dies before the compare
(klayout-tools#7589). `layout/lvs.sh --check --rerun` therefore keeps klt's
cheap hash gate, regenerates a fresh portable report in scratch from the
same shared request — the PDK root re-resolved from the invocation's
environment, so the default and any relocated root verify alike — and diffs
it against the committed evidence with the pinned klt's own verdict-field
exclusion set, so the status, the power-connectivity verdict, the
stream/reference hashes, the pin-order library evidence and
`environment.engine_version` all stay compared. A check never rewrites the
committed reports.

Re-run it after anything that changes the routed stream or the as-built
netlist (i.e. after `layout/pnr.sh` writes new ones). If the fresh report is
again `status: match` with `power_connectivity.status: match`, update the
`4.digital` `content_hash` in `block-manifest.json` to the report's
`provenance.input.content_hash` — the stream's own sha256, **not** the report
file's own digest, the same rule every other entry follows — and regenerate
the record. That changes the record, so finish with the item 8 round trip
under "Regenerate the record" (re-attest item 8, regenerate once more,
byte-identical). A refresh that moves only machine-local provenance — an
engine-version bump under the same pin, like the 2026-11-23 re-record at
klayout 0.30.14 — leaves the input hash, the `4.digital` citation and the
record byte-identical, so no manifest edit and no second record-regeneration
pass is needed — but item 8 must still be re-attested in the same commit,
because the envelope pins the report's own raw bytes (`sha256-raw-bytes`),
which an engine-version-only refresh changes (see "Re-attest item 8"). A
`status: mismatch` report is committed uncited instead,
`4.digital` stays `unmet`, and the mismatch classes are listed in
`layout/README.md`, "LVS".

## What CI does and does not check

`.github/workflows/ci.yml` has two jobs. `harness` installs only Python, the
pinned klt, `uv` and `jq`
(no PDK, ngspice or xschem; the KLayout Python module comes
with the pinned klt, which is how `--attest 2` reads a stream); `controller` builds the pinned
Icarus 13.0 and Yosys 0.67 (`scripts/ci/install_eda.sh`, cached), installs `uv`
(the bench reaches the pinned klt through `uvx`) and runs
`verification/run.sh`, its `--negative-control`, `rtl/synth.sh` and its
`--negative-control`. Together they check that:

- the controller bench passes, the negative control catches every seeded
  defect, no latch cell survives generic synthesis, and the latch gate's own
  negative control (the committed latch-bearing fixture) still trips it;
- the committed item 10 and item 9 envelopes match a fresh attestation;
- the hermetic checks of the `harness` job's `check:ci` step pass
  ([`scripts/ci/check_ci.sh`](../scripts/ci/check_ci.sh), the same script
  `npm run check:ci` runs locally). Its term list is single-sourced there --
  one `run` line per check, each announced with a `==> <name>` line so a
  failure names its check -- so the checks are not enumerated here;
- files under `sim/**/records/` are only added, never modified, deleted or renamed;
- every cell of each committed stream (`layout/efuse_otp_array.gds` and
  `layout/efuse_otp_ctrl.gds`) has zero via2 shapes with no M3 above or no M2
  below (`layout/check_via2_landing.sh`, counted per cell with the pinned klt's
  klayout). The deck does not model the `V2.3c`, `V2.3d`, `V2.4b` or `V2.4c`
  rules, so this count is the only gate for that class on those streams; it
  runs on the committed streams and does not regenerate them;
- the item 1 (analog) attestation still reproduces (`--attest 1 --check`);
- both item 2 attestations still reproduce (`layout/attest.sh --check`, i.e.
  `--attest 2 --check` on each stream); the generators named in their
  regeneration claims need OpenROAD and the PDK and are not re-run;
- both committed ERC reports match their stream, supply spec and deck hashes
  (`layout/erc.sh --check`). Removing Metal4 fragments both controller rails
  and all three array rails (`layout/erc.sh --negative-control`);
- the item 8 envelope's recorded hash of `block-manifest.signoff.json` is current
  (`--attest 8 --check`), so regenerating the record without
  re-attesting item 8 fails;
- re-grading the manifest reproduces the committed record byte for byte.

**CI does not check that any evidence is correct.** It checks formats,
append-only history, and that the record reproduces.
