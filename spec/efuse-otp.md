# gf180mcu eFuse OTP — target specification

Status: **ratified** by this document and decision records 0001–0005 in
`spec/decisions/`. Changes go through a new decision record; nothing here is
relaxed to make a result pass.

Scope: device physics, array/addressing, program and sense circuits, the
controller, and simulated or measured yield/margin. See `CLAUDE.md`.

## 1. Documentation survey

Citation baseline: PDK `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`,
installed at `~/.ciel/gf180mcuD` (file `SOURCES`). Paths below are relative to
that root. Tool: `klt 0.7.1.dev1754+g81ac4d3915c1`.

### 1.1 Documented

| Item | Value | Source |
|---|---|---|
| Fuse width (PLFUSE) | 0.18 µm exact (EF.02) | `libs.tech/klayout/tech/drc/rule_decks/efuse.rb` |
| Fuse length (PLFUSE) | 1.26 µm exact (EF.03) | same |
| Total fuse Poly2 length | 5.53 µm exact (EF.21) | same |
| Cathode Poly2 | 2.26 µm wide, 1.84 µm long, exact (EF.06, EF.07) | same |
| Anode Poly2 | 1.06 µm wide, 2.43 µm long, exact (EF.08, EF.09) | same |
| Cathode / anode overlap with PLFUSE (width direction) | 1.04 µm / 0.44 µm exact (EF.22a/b) | same |
| Contacts | exactly 4 at each end (EF.16a/b); none touching PLFUSE (EF.15); contact-to-PLFUSE-end space ≥ 0.155 µm cathode, ≥ 0.14 µm anode (EF.12, EF.13) | same |
| Keep-out | PLFUSE ≥ 2.73 µm from COMP/Nplus/Pplus/Resistor/ESD/SAB (EF.20); no crossing COMP, Nplus, Pplus, ESD, SAB, Resistor, Metal1, Metal2 (EF.18, EF.19) | same |
| Spacing | Poly2 to cathode/anode ≥ 0.26 µm (EF.10, EF.11); EFUSE_MK to EFUSE_MK ≥ 0.26 µm (EF.17) | same |
| Marker rules | EF.01, EF.04a–d, EF.05, EF.14 (butting, rectangularity, `LVS_Source`, EFUSE_MK enclosure) | same |
| Rule set | EF.01–EF.15, EF.16a/b, EF.17–EF.21, EF.22a/b, with EF.04 split into a–d | same |
| Layers | PLFUSE 125/5, EFUSE_MK 80/5 | klt `decks/gf180mcu.py` layer table; PDK deck |
| Layout primitive | `libs.ref/gf180mcu_fd_pr/gds/efuse.gds`, `mag/efuse_cell.mag`; PCell `libs.tech/klayout/tech/pymacros/cells/efuse.py` | PDK |
| Compact model | `.subckt efuse in out pblow=0`: `rfuse in out r='200*(1-pblow)+900*pblow'`; header comment "Subcircuit model for 6V/(5V) efuse"; included from the `res_*` corner libs | `libs.tech/ngspice/sm141064.ngspice` (`.lib efuse`, ~line 46924) |
| Intact resistance | 200 Ω (model, `pblow=0`). The LVS deck uses 28.5714 Ω/sq; over 7 squares (1.26/0.18) that is 200 Ω | `sm141064.ngspice`; `libs.tech/klayout/tech/lvs/rule_decks/efuse_extraction.lvs`; `lvs/testing/unit/efuse_devices/netlist/efuse.cdl` |
| Programmed resistance | 900 Ω (model, `pblow=1`) — a single model constant, not a distribution | `sm141064.ngspice` |
| Process corner names | `typical`, `ff`, `ss`, `fs`, `sf` (`.lib` blocks at lines 105–233) | `sm141064.ngspice` |
| LVS device | The PDK LVS deck extracts the fuse as a two-terminal `efuse` device (anode/cathode from `LVS_Source`), `R` ignored in comparison | `efuse_extraction.lvs`, `efuse_derivations.lvs` |

### 1.2 Not documented

| Item | Status |
|---|---|
| Program current, pulse width, program voltage | **Not documented** in the installed PDK. The model comment says "6V/(5V)" only. |
| Intact and programmed resistance distributions | **Not documented.** Only the single points 200 Ω / 900 Ω above. |
| Programming behavior in the model | The model is a switch parameter `pblow`; it does not simulate the fuse changing state. |
| `gf180mcu_re_efuse` macros and their compiler | **Not installed** in the pinned tree (`libs.ref/` holds `gf180mcu_fd_io`, `fd_ip_sram`, `fd_pr`, two `fd_sc_mcu*`, two `osu_sc_gp*`). The macro reference row is empty; no figures are guessed. |
| Read-disturb limit | Not documented. |

### 1.3 Tool survey (klt)

- `klt drc --list-rules --deck gf180mcu`: 94 rules, zero `EF.*` rule IDs at
  the survey revision (`0.7.1.dev1754+g81ac4d3915c1`, 2026-10-17). At the
  pinned klt 0.9.2 (2026-11-21): 127 rules, still zero `EF.*` IDs, but seven
  EF-scope rules — `efuse_mk.space.1`, `efuse_mk.enclosing.lvs_source.1`,
  `plfuse.separation.{comp,nplus,esd,sab,resistor}.1` — so a prefix count
  alone understates curated EF coverage.
  [0007](decisions/0007-drc-tool-survey.md).
- `klt drc` on `libs.ref/gf180mcu_fd_pr/gds/efuse.gds`: status `violations`,
  64, all `*.ongrid.1` (off-grid vertices on contact, efuse_mk, metal1,
  plfuse, poly2, pplus). No `EF.*` rule fires, passes, or is reported as
  skipped: the exact-value rules are not run.
- `klt drc --engine klayout`: at the survey revision (2026-10-17) klt found
  no PDK-native deck ("no PDK-native klayout DRC deck script found for this
  PDK variant"). At the pinned klt 0.9.2, `layout/drc.sh` runs the foundry
  deck by supplying the main deck explicitly — `--deck-file
  pdk/<variant>/libs.tech/klayout/tech/drc/gf180mcu.drc` with `decks=all`,
  array variant `gf180mcuC`, controller variant `gf180mcuD` — and both
  committed reports (PR #313) check all 27 `EF.*` IDs with zero EF markers,
  status `violations`. Automatic deck discovery is a separate claim, not
  made. [0007](decisions/0007-drc-tool-survey.md).
- LVS: klt's gf180mcu deck uses `efuse_mk`/`plfuse` only as layers excluded
  from other derivations (resistor, MiM); a search of the installed klt
  package found no fuse device extraction. The PDK's own deck does extract
  one. End-to-end `klt lvs` on a fuse was not run here.
- Friction items for `2AMLogic/klayout-tools` (generic wording, to be filed
  without design detail): (1) exact-value (min = max) width/length rules and
  marker-derived-layer rules are absent from the curated gf180mcu deck;
  (2) a marker-defined two-terminal resistor-like device is not extracted by
  the curated LVS path.

## 2. Parameters

"Assumption" = no documented source (section 1.2): a stated working value,
not a fact, replaced only by a decision record that cites a source.

| Parameter | Target | Fallback | Stretch | Rationale |
|---|---|---|---|---|
| Array | 256 bits, 32 rows × 8 columns | 8 bits, 1 × 8 | 1 kbit | Exercises row/column decode and tiling; the fallback keeps program and sense paths testable. (0001) |
| Fuse cell | PDK geometry per 1.1, no deviation | — | — | Rules are exact-value; the cell is not a design variable. |
| Program-select device | 5 V/6 V-oxide NMOS (`nfet_06v0`) per cell, in series with the fuse; width set by simulation | 3.3 V NMOS if simulation shows it delivers the current within its rated voltage | — | The model is labeled 6V/(5V); the select device sees the program supply. (0002) |
| Program supply | external, nominal 5.0 V ±10% (A1) | — | on-die (decision record) | Test vehicle. (0002) |
| Required program current | ≥ 10 mA through the fuse at the worst corner (A2) | — | — | No PDK source. Claim is path delivery only (section 3). |
| Pulse width | 10 µs nominal, controller range 1–100 µs (A3) | — | — | No PDK source. |
| Intact range for margin | 140–260 Ω (A4: documented 200 Ω ±30%) | — | — | Only the 200 Ω point is documented. |
| Programmed range for margin | ≥ 630 Ω, up to open (A5: documented 900 Ω −30%) | — | — | Only the 900 Ω point is documented. |
| Sense topology | Current comparison against a 400 Ω reference resistor (A6; geometric midpoint of 200/900 Ω is ≈ 424 Ω) with a clocked comparator, 3.3 V domain, small read current | Resistor divider into a clocked comparator | Replicated-reference column | Resistor reference tracks resistor corners. (0003) |
| Sense margin | Positive at every corner over the A4/A5 ranges, including reference tolerance and comparator offset | — | — | |
| Controller interface | Synchronous: clock, address, program-enable, read-enable, data out, busy | Asynchronous parallel read | Serial interface | (0004) |
| Controller behavior | Program only after an explicit registered arm state set after reset release; program drive held inactive in reset and power-up; fixed sense-settle count for read; address stable before enable | — | — | Protection against unintended programming at power-up. (0004) |
| PVT corners | Process `typical`, `ff`, `ss`, `fs`, `sf`; T = −40, 25, 125 °C; logic/sense supply 3.3 V ±10% (2.97/3.30/3.63 V); program supply 5.0 V ±10% (4.5/5.0/5.5 V) | — | — | Names confirmed against `sm141064.ngspice`. (0005) |
| Signoff | DRC clean including every `EF.*` rule; LVS clean with the fuse as a recognized device; controller verified (cocotb + Icarus, Yosys, OpenROAD) | — | — | |

Every result recorded in `sim/` states its PVT points (process × temperature
× supply); a result without its corner set is not evidence.

Assumptions: A1 program supply, A2 program current, A3 pulse width, A4 intact
range, A5 programmed range, A6 reference value.

## 3. What pre-silicon evidence can and cannot show

Can show (simulation):

- The program path (select device, drive, supply, routing resistance)
  delivers at least the assumed program current (A2) into a fuse at its
  intact resistance, at every PVT corner above.
- The sense path distinguishes the intact and programmed populations with
  positive margin over stated ranges (A4, A5) at every PVT corner.
- Controller sequencing, including no program activity at reset and power-up.

Cannot show:

- That the fuse changes state. No compact model simulates it; the PDK model
  is a resistance switch (`pblow`). "Programmed" in a simulation means the
  fuse is replaced by its programmed-resistance value, never that a pulse
  caused it.
- That the assumed current and pulse (A2, A3) program a real fuse, or the
  real programmed-resistance distribution (A5).
- Read-disturb or post-program drift.

These close only by measurement (`measurements/`) or by a documented source
replacing an assumption through a decision record.

## 4. Decision records

`spec/decisions/`: 0001 array, 0002 program path, 0003 sense topology,
0004 interface and protection, 0005 PVT set.
