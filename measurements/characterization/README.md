# Characterization report (T1 item 8)

One row per ratified spec row (`spec/efuse-otp.md` section 2 parameters `P01`-`P13`
and section 3 "can show" claims `C1`-`C3`), with the record each verdict rests on.
This report **aggregates committed records; it produces no evidence and edits no
`sim/` result.** State read at `main` `0e97c48`, 2026-10-28.

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
| P07 | Intact range for margin | 140-260 ohm (A4) | `ASSUMPTION`: only 200 ohm is documented (PDK model, `sm141064.ngspice`); used as a bench input, not a result | n/a | no | `sim/program-select/records/20261023T174839Z-f6eeac7/record.json` (program side); sense side not measured, owning issue #34 |
| P08 | Programmed range for margin | >= 630 ohm up to open (A5) | `ASSUMPTION`: only 900 ohm is documented; bench exists, no record | n/a | no | not measured, owning issue #34 (bench: `sim/sense-margin/`, request set validated by `--dry-run` only) |
| P09 | Sense topology | 400 ohm reference (A6), clocked comparator, 3.3 V domain | not measured: A6 is an `ASSUMPTION`; schematic committed, no margin record | n/a | no | `design/efuse_otp_array.sch` (design only), owning issue #34 |
| P10 | Sense margin | positive at every corner over A4/A5, incl. reference tolerance and comparator offset | not measured; tolerance and offset are also not yet simulated (no documented source) | n/a | yes, offset/tolerance need Monte Carlo | owning issues #34 (corners), #36 (Monte Carlo) |
| P11 | Controller interface | synchronous: clock, address, program-enable, read-enable, data out, busy | met (RTL functional): 12/12 checks pass in all 9 parameter sets | n/a (no PVT in an RTL bench) | no | `sim/controller-fv/*.report.json` |
| P12 | Controller behavior | arm state after reset; program drive inactive in reset and power-up; fixed settle count; address stable before enable | met (RTL functional); a negative control is defined in `verification/README.md` but no committed record of its result exists, so none is claimed | n/a (no PVT in an RTL bench) | no | `sim/controller-fv/*.report.json`, `verification/README.md` |
| P13 | PVT corners / Signoff | corner set of decision 0005; DRC clean incl. `EF.*`; LVS with the fuse as a device; controller verified | not met: DRC clean only without `EF.*` (#60); LVS not run (#32); controller section below covers 5 of the decision-0005 corners | see Controller | no | `signoff/block-manifest.signoff.json`, `layout/drc-*.report.json`, `sim/controller-sta/*.report.json` |

## Spec section 3 claims (what pre-silicon evidence can show)

| Row | Claim | Verdict | Binding corner | Statistical | Cited record |
|---|---|---|---|---|---|
| C1 | Program path delivers >= A2 into an intact fuse at every PVT corner | `ASSUMPTION` bound; met on the simulated grid (5 process x 3 T x 3 Vprog x 140/200/260 ohm, 135 points, 60 um). Routing resistance 20 ohm and gate drive = Vprog are themselves assumptions recorded there. | ss, 125 C, 4.5 V, 260 ohm: 11.99 mA | no | `sim/program-select/records/20261023T174839Z-f6eeac7/record.json` |
| C2 | Sense path distinguishes intact and programmed populations with positive margin at every PVT corner | not measured | n/a | yes (offset, tolerance) | owning issues #34, #36 |
| C3 | Controller sequencing, incl. no program activity at reset and power-up | met (RTL functional, ideal timing); gate-level / SDF timing re-run not done | n/a | no | `sim/controller-fv/*.report.json`; post-layout re-run owned by #61 |

## Controller (digital partition): Fmax, area, power

Clock target is decision 0006, `Status: proposed` (10 MHz). It is **not ratified**;
the 100 ns column below is not "ratified spec". The 10 ns report is cited only as
out-of-spec headroom.

Fmax, worst setup and hold slack come from `klt sta` on the routed DEF
(`geometry_source: routed`, `clock_mode: ideal`, no SPEF: wire parasitics are
estimated by the engine). Source: `sim/controller-sta/sta-100ns.report.json`
(`corners[]`).

| Corner | Fmax (MHz) | Setup slack @ 100 ns (ns) | Hold slack (ns) | Estimated power (mW) |
|---|---|---|---|---|
| ss_n40C_3v00 | 130.122 | 92.3149 | 1.61053 | 0.2765 |
| ss_125C_3v00 | 89.0309 | 88.7679 | 2.30944 | 0.2932 |
| tt_025C_3v30 | 181.228 | 94.4821 | 1.13542 | 0.3505 |
| ff_n40C_3v60 | 316.613 | 96.8416 | 0.64285 | 0.4236 |
| ff_125C_3v60 | 215.51 | 95.3598 | 0.90653 | 0.4519 |

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

Not omitted, only unmeasured: P02 (#60), P08, P09, P10, C2 (#34, #36), and the
LVS part of P13 (#32). Post-layout rows (#61) and the clock-target ratification
(decision 0006, #35) will change the controller section; update the rows then.

## Reproduce / re-derive

Every number above is read from the committed file named beside it. No value is
computed here; to check the table, re-read those files (`corners[]` in the STA
report, `die_area_um2`/`core_area_um2` in `layout/pnr-report.json`).
