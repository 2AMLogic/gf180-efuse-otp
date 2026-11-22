# Characterization report (T1 item 8)

One row per ratified spec row (`spec/efuse-otp.md` section 2 parameters `P01`-`P13`
and section 3 "can show" claims `C1`-`C3`), with the record each verdict rests on.
This report **aggregates committed records; it produces no evidence and edits no
`sim/` result.** The original snapshot used `main` at `fafa4a6` on 2026-11-10.
The controller timing and power table uses the 100 ns STA report added in `302f29d`.

Verdict vocabulary: `met` (a committed record shows the bound over the stated
conditions), `not met`, `partial` (record covers part of the bound), `not measured`
(no record yet; the owning issue is named). Nothing here shows that a fuse changes
state (spec section 3, "Cannot show").

**Assumptions.** A1 program supply, A2 program current, A3 pulse width, A4 intact
range, A5 programmed range, A6 reference value have **no documented source**
(spec section 1.2). A bound that rests on one is marked `ASSUMPTION` below: it is a
working value, not a fact, and a verdict against it says nothing about a real fuse.

## Spec rows

| Row | Spec row | Bound | Verdict | Binding corner | Statistical | Cited record |
|---|---|---|---|---|---|---|
| P01 | Array | 256 bits, 32 x 8 (fallback 1 x 8) | partial: controller bench runs 32 x 8 and 1 x 8 (RTL only); array layout committed, no array-level electrical result | n/a | no | `sim/controller-fv/32x8_nom.report.json`, `sim/controller-fv/1x8_nom.report.json`, `layout/efuse_otp_array.report.json` |
| P02 | Fuse cell | PDK geometry per spec 1.1, no deviation | not measured: `EF.*` exact-value rules are not evaluated by the pinned klt deck (klayout-tools#4312) | n/a | no | `layout/drc-array.report.json` (clean under the curated deck; `EF.*` not in `rules_checked`), owning issue #60 |
| P03 | Program-select device | `nfet_06v0` per cell, width set by simulation | met for the swept grid: 60 um (L 0.7 um) is the smallest swept width passing the A2 requirement; Vgs 5.5 V, Vds 2.32 V as simulated | ss, 125 C, 4.5 V, fuse 260 ohm (see P06) | no | `sim/program-select/records/20261023T174839Z-f6eeac7/record.json` |
| P04 | Program supply | external, 5.0 V +/-10% (A1) | `ASSUMPTION`: swept at 4.5/5.0/5.5 V as the grid axis; not a result | n/a | no | `sim/program-select/records/20261023T174839Z-f6eeac7/record.json` |
| P05 | Pulse width | 10 us nominal, 1-100 us (A3) | `ASSUMPTION`: controller generates 1/10/100 us pulses at 10 MHz (and 100 us at 100 MHz) in an ideal-timing RTL bench; no analog result depends on it | n/a | no | `sim/controller-fv/32x8_min.report.json`, `32x8_nom.report.json`, `32x8_max.report.json`, `32x8_100MHz_max.report.json` |
| P06 | Required program current | >= 10 mA through the fuse at the worst corner (A2) | `ASSUMPTION` bound; met at 60 um over the 135-point grid: minimum 11.99 mA at the A4 260 ohm end, 13.66 mA at the documented 200 ohm | ss, 125 C, 4.5 V, 260 ohm | no | `sim/program-select/records/20261023T174839Z-f6eeac7/record.json`, `design/README.md` |
| P07 | Intact range for margin | 140-260 ohm (A4) | `ASSUMPTION`: only 200 ohm is documented (PDK model, `sm141064.ngspice`); used as a bench input, not a result. Sense side: 140/200/260 ohm intact points all read the correct side (see P10) | n/a | no | `sim/program-select/records/20261023T174839Z-f6eeac7/record.json` (program side); `sim/sense-margin/records/20261109T002043Z-f6eeac7/` (sense side, bench inputs) |
| P08 | Programmed range for margin | >= 630 ohm up to open (A5) | `ASSUMPTION` bound; 630 / 900 ohm / open (1 Gohm) programmed points read the correct side at all 45 corners each (`status: pass`, 45/45); minimum signed margin 0.0260 V at 630 ohm. Only 900 ohm is documented; 630 ohm and open are assumed edges | ss, 125 C, 2.97 V, 630 ohm | no (corners only; spread in P10) | `sim/sense-margin/records/20261109T002043Z-f6eeac7/sets/bench_rf630_rr400/report.json`, `.../bench_rf900_rr400/report.json`, `.../bench_rfopen_rr400/report.json` |
| P09 | Sense topology | 400 ohm reference (A6), clocked comparator, 3.3 V domain | `ASSUMPTION` (A6): the committed sense path with a 400 ohm reference, simulated over the decision-0005 grid (45 corners) against both populations, all 45/45 pass per fuse value. Shows the topology as built works over those ranges; says nothing about whether 400 ohm is the right reference for a real fuse. Fuse leg is an ideal resistor behind a switch (no bitline capacitance, no column-mux leakage) | ss, 125 C, 2.97 V (intact 260 ohm, margin 0.0160 V) | no | `design/efuse_otp_array.sch`, `sim/sense-margin/records/20261109T002043Z-f6eeac7/sets/bench_rf260_rr400/report.json`, `.../bench_rf630_rr400/report.json` (and the other four bench reports listed under P10) |
| P10 | Sense margin | positive at every corner over A4/A5, incl. reference tolerance and comparator offset | `partial`, `ASSUMPTION` ranges. Corners: signed `margin_v` positive at every one of 6 fuse values x 45 corners (minimum 0.0160 V, intact 260 ohm). Monte Carlo (seed 36036, 540 samples per population, mismatch at PDK default plus 5 % relative-sigma reference tolerance): intact 260 ohm minimum 0.0122 V and programmed 630 ohm minimum 0.0223 V, 0 failing samples each; empirical yield 100 % with the honest statement "at least 99.3192 % at 95 % confidence, N = 540"; negative control detected. Pooled across corners (a worst-case envelope), normality rejected, so the parametric Cpk is indicative only. The reference-tolerance sigma is itself an assumption (no documented source) | corners: ss, 125 C, 2.97 V, intact 260 ohm; Monte Carlo: ss/125 C/2.97 V (intact), typical/125 C/2.97 V (programmed) | yes (offset, tolerance) | `sim/sense-margin/records/20261109T002043Z-f6eeac7/sets/bench_rf140_rr400/report.json`, `.../bench_rf200_rr400/report.json`, `.../bench_rf260_rr400/report.json`, `.../bench_rf630_rr400/report.json`, `.../bench_rf900_rr400/report.json`, `.../bench_rfopen_rr400/report.json`; `sim/sense-mc/records/20261105T084326Z-f6eeac7/yield/intact.yield.json`, `.../prog.yield.json` |
| P11 | Controller interface | synchronous: clock, address, program-enable, read-enable, data out, busy | met (RTL functional): 12/12 checks pass in all 9 parameter sets | n/a (no PVT in an RTL bench) | no | `sim/controller-fv/*.report.json` |
| P12 | Controller behavior | arm state after reset; program drive inactive in reset and power-up; fixed settle count; address stable before enable | met (RTL functional); a negative control is defined in `verification/README.md` but no committed record of its result exists, so none is claimed | n/a (no PVT in an RTL bench) | no | `sim/controller-fv/*.report.json`, `verification/README.md` |
| P13 | PVT corners / Signoff | corner set of decision 0005; DRC clean incl. `EF.*`; LVS with the fuse as a device; controller verified | not met: DRC clean only without `EF.*` (#60); LVS not run (#32); controller section below covers 5 of the decision-0005 corners | see Controller | no | `signoff/block-manifest.signoff.json`, `layout/drc-*.report.json`, `sim/controller-sta/*.report.json` |

## Spec section 3 claims (what pre-silicon evidence can show)

| Row | Claim | Verdict | Binding corner | Statistical | Cited record |
|---|---|---|---|---|---|
| C1 | Program path delivers >= A2 into an intact fuse at every PVT corner | `ASSUMPTION` bound; met on the simulated grid (5 process x 3 T x 3 Vprog x 140/200/260 ohm, 135 points, 60 um). Routing resistance 20 ohm and gate drive = Vprog are themselves assumptions recorded there. | ss, 125 C, 4.5 V, 260 ohm: 11.99 mA | no | `sim/program-select/records/20261023T174839Z-f6eeac7/record.json` |
| C2 | Sense path distinguishes intact and programmed populations with positive margin at every PVT corner | `partial`, `ASSUMPTION` ranges: same evidence and caveats as P10 (corner grid positive everywhere; Monte Carlo 0 failing of 540 per population over the assumed A4/A5 edge points). Does not cover a real fuse | corners: ss, 125 C, 2.97 V, intact 260 ohm | yes (offset, tolerance) | same records as P10 |
| C3 | Controller sequencing, incl. no program activity at reset and power-up | met (RTL functional, ideal timing); gate-level / SDF timing re-run not done | n/a | no | `sim/controller-fv/*.report.json`; post-layout re-run owned by #61 |

## Controller (digital partition): Fmax, area, power

Clock target is decision 0006, `Status: ratified` (10 MHz, 100 ns period). The
10 ns report is cited only as out-of-spec headroom.

Fmax, worst setup and hold slack come from `klt sta` on the routed DEF
(`geometry_source: routed`, `clock_mode: ideal`, no SPEF: wire parasitics are
estimated by the engine). Source: `sim/controller-sta/sta-100ns.ddba55a3.report.json`
(`corners[]`).

| Corner | Fmax (MHz) | Setup slack @ 100 ns (ns) | Hold slack (ns) | Estimated power (mW) |
|---|---|---|---|---|
| ss_n40C_3v00 | 130.122 | 92.3149 | 1.61053 | 0.2798 |
| ss_125C_3v00 | 89.0309 | 88.7679 | 2.30944 | 0.2968 |
| tt_025C_3v30 | 181.228 | 94.4821 | 1.13542 | 0.3548 |
| ff_n40C_3v60 | 316.613 | 96.8416 | 0.64285 | 0.4288 |
| ff_125C_3v60 | 215.51 | 95.3598 | 0.90653 | 0.4577 |

- **Power is an estimate, not a switching-activity result.** Basis in the
  report: `activity_source: engine_default`, `parasitics: estimate_only`. It
  says nothing about worst-case or measured power. Post-layout re-runs: #61.
- **Slowest corner:** `ss_125C_3v00`, Fmax 89.0309 MHz. At the 10 ns case the same
  corner fails setup (-1.23 ns, `sim/controller-sta/sta-10ns.report.json`;
  `sta/README.md`); that is headroom beyond decision 0006's 10 MHz, not a failure
  against a requirement while 0006 stands.
- **Corner coverage gap.** Decision 0005 asks for `typical/ff/ss/fs/sf` x
  {-40, 25, 125 C} x 3.3 V +/-10%. The library offers no `fs`/`sf`, no 3.3 V-family
  `tt` at -40/125 C, no `ss`/`ff` at 25 C, and brackets 3.3 V at 3.00/3.60 V. The
  five corners above are the coverage; the rest is a gap, not a pass
  (`sta/README.md`).
- **Area** (`layout/pnr-report.json`): die 27342.3 um^2, core 20468 um^2,
  utilization 46.2248 %.

## Rows with no record yet

Not omitted, only unmeasured: P02 (#60) and the LVS part of P13 (#32). P08, P09,
P10 and C2 are cited above from the post-#85 corner and Monte Carlo records; they
rest on assumptions A4-A6 and the unsourced reference-tolerance sigma. Issue #61
tracks the remaining post-layout controller measurements.

## Reproduce / re-derive

Every number above is read from the committed file named beside it. No value is
computed here; to check the table, re-read those files (`corners[]` in the STA
report, `die_area_um2`/`core_area_um2` in `layout/pnr-report.json`).
