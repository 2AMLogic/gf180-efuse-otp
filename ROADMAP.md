# Roadmap

An eFuse one-time-programmable array on the gf180mcu open PDK (32 x 8 fuse
array, program path, sense path, synchronous controller), built as a canary
that exercises klayout-tools (`klt`) on a rule-defined device.

**Status as of 2026-11-13, `main` @ `d16f22b`.** The verdict of record is
[`signoff/block-manifest.signoff.json`](signoff/block-manifest.signoff.json)
(pinned `klayout-tools==0.9.0`, re-graded in CI); this file says what comes
next. Label state is in [`WORK_PLAN.md`](WORK_PLAN.md); the tracker is #3.

## Where it stands

T1 (sim-validated) reads **12 of 22 partition items met, 1 not applicable, 9
unmet**. Block kind is mixed-signal, so every item is graded once per partition.

| T1 item | analog | digital | Evidence or owner |
|---|---|---|---|
| 1 Design sources | met | met | `design/`, `rtl/`, `signoff/item1-*.attest.json` |
| 2 Layout | met (placed, not routed) | met (routed) | `layout/efuse_otp_array.gds`, `layout/efuse_otp_ctrl.gds`, `layout/pnr-report.json` |
| 3 DRC clean | unmet | unmet | #60; both reports are clean but uncited |
| 4 LVS clean | unmet | unmet | #32 |
| 5 Corner verification | met | unmet | analog: `sim/corner-verification/`; digital: #35, PR #94 |
| 6 Monte Carlo | met | not applicable | `sim/sense-mc/`, `signoff/item6-digital-statement.json` |
| 7 Post-layout verification | unmet | unmet | #61 |
| 8 Characterization report | met | met | `measurements/characterization/README.md` |
| 9 Testbenches shipped | met | met | `sim/README.md`, `verification/` |
| 10 Repo hygiene | met | met | `signoff/attest/item10.envelope.json` |
| 11 Power delivery | unmet | unmet | #33 |

Done and merged since the spec was ratified (decisions 0001 to 0005):

- Analog: schematics and netlist, program-select sweep, column driver widened
  (#95), comparator resolving resistive fuses (#77), graded margin campaign
  (#98), Monte Carlo evidence (#36).
- Digital: controller RTL, cocotb bench with negative control, routed layout
  (#30), nine `klt functional-verification` and three `klt sta` reports.
- DRC clean on both partitions under the curated deck (#48, #49); item 8
  report attested (#62, #100); evidence-hygiene fixes #106 to #152.

The README's current-position line now reads "sense path simulated across PVT"
(#181), matching this record.
The remaining nine unmet items reduce to four causes: the analog stream is not
routed, `klt` has no eFuse device class for LVS, `klt drc` does not model the
foundry `EF.*` rule set, and decision 0006 is not yet ratified.

## Now

1. **Replace the latch log scraper with a Yosys assertion** (#161,
   `loom:building` — in flight, do not pick it up again). Done when
   `rtl/synth.sh` fails on one inferred latch through `select -assert-none`
   and no longer sums `stat` lines from the log.
2. **Route `efuse_ls` in the generator and LVS-match it** (#172,
   `loom:triage`; first slice of #73). Done when `klt lvs` of the routed cell
   against its `.subckt` in `design/efuse_otp_array.spice` reports
   `status: match` and the report is committed under `layout/`. The cell holds
   six MOS devices and no fuse, so the missing eFuse device class does not
   block it. `klt gen-compose` alone left two of seven nets unrouted in the
   #73 attempt.
3. **LVS the routed controller** (#173, `loom:triage`; digital half of #32).
   Done when `klt lvs` of `layout/efuse_otp_ctrl.gds` against
   `layout/efuse_otp_ctrl.asbuilt.v` is committed with `status: match`. The
   controller draws no fuse. Re-run if #154 lands after: reports are hash-pinned.
4. **SDF-annotated controller re-run** (#174, `loom:triage`; digital half of
   #61). Done when a `klt functional-verification` report on the as-built
   netlist with `environment.sdf.annotated: true` is committed and every test
   passes. The committed reports carry `"sdf": null`. Same hash note as item 3.

In flight, not to be picked up twice: #161 (Now item 1), #154 (digital stream
re-established on the pinned klt), PRs #153, #156, #157, #158, #159, #162, and
curated #155 and #160. Issue and label state in this section is as read on
2026-11-14; the evidence claims elsewhere stand at the sha in the header.

## Next

- **Route `efuse_coldrv` and `efuse_rowdrv`, LVS-match each** (#73 remainder).
  Unblocked by Now item 2, which fixes the floorplan pattern for the level
  shifter both cells instantiate. Done when each has a committed `match` report.
- **Route `efuse_sense` and `efuse_comp`.** After the drivers. Done when each
  has a committed LVS report and the ideal resistor in `efuse_sense`, which the
  generator approximates, has a stated disposition.
- **Cite 4.digital and run the digital ERC supply spec** (#33, digital half).
  Unblocked by Now item 3. Done when a `klt erc` report for `efuse_otp_ctrl`
  declares the supplies and 11.digital reads `met`.
- **Cite 7.digital.** Unblocked by Now item 4 and #154 together.
- **Rebase PR #94 and cite 5.digital** once the operator releases the
  ratification hold (see below). Done when 5.digital reads `met`.
- **Make `sta/run.sh` report the 10 ns case without gating on it** (#145),
  after PR #94. **Drop the private klt call in `layout/attest.sh`** (#130),
  after klayout-tools#5551 ships in the pinned release.

## Later

- **Full-array routing and assembly** (`efuse_bitcell`, `efuse_row`, top).
  Question first: are fuse-bearing cells routed before `klt lvs` can recognise
  the fuse (klayout-tools#4312), or only after?
- **7.analog, `klt pex` re-run of the analog benches** (#61). Question first:
  what does extraction report for the fuse element? 11.analog (#33) follows 4.analog.
- **Comparison against the PDK's `gf180mcu_re_efuse` macros.** The spec records
  them as not installed in the pinned PDK tree. Question first: can they be
  obtained in a pinned, reproducible way?
- **Shuttle seat and measured silicon**, the last rungs of the README ladder.
  Nothing is scheduled. No compact model simulates programming, so only silicon
  closes the rows the spec marks "not documented". Question first: an operator
  decision to seek a seat.

## Blocked and waiting

On the operator:

- **PR #94** ratifies decision 0006 (10 MHz controller clock). Judge-approved,
  under a ratification hold, and now conflicting with `main` in two `signoff/`
  files — `signoff/README.md` and `signoff/block-manifest.signoff.json`. Two
  further `signoff/` files are in the merge and auto-merge clean. It gates
  5.digital (#35) and #145.
- **Item 3 disclosure wording** (#60). Under klt 0.9.0 the deck checks seven
  eFuse-layer rules but still lists all 24 foundry `EF.*` IDs as unmodeled.
  Whether item 3 may be cited with a partial-coverage statement, and whether
  `spec/efuse-otp.md` section 1.3 is re-measured through a decision record, are
  open questions on #60.
- **Hermit proposals awaiting a ruling:** #118, #120, #131, #145.
- **#73** is parked with an unstated blocker after one Builder attempt; Now
  item 2 and Next carry the split its Builder note proposed.

On upstream klayout-tools:

- klayout-tools#4312, eFuse device class for LVS: blocks 4.analog (#32) and,
  behind it, 7.analog and 11.analog.
- klayout-tools#4312 and klayout-tools#4002, `EF.*` rule evaluation: block
  item 3 on both partitions (#60). klayout-tools#5551 blocks #130.

## Not planned

- Any statement about applications of the block. `CLAUDE.md` scope firewall.
- A visibility change, or any public mirror of this content. Operator-only.
- Relaxing a ratified spec row, or skipping the `EF.*` rules, to make a result
  pass. A tool gap is filed upstream, generically, and the item stays unmet.
- Reimplementing the PDK's eFuse primitive or its compiled macros.
