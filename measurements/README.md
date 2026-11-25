# measurements

`characterization/README.md` is the T1 item 8 characterization report: one row per ratified
spec row, the verdict and the committed record it rests on, plus controller Fmax, area and
estimated power. It aggregates `sim/`, `layout/` and `verification/` records and holds no
bench measurement of its own. No silicon measurement has been made. See the repo README for scope.

## Cross-check against the poly-fuse blow report

Background only: Cooker, Dellar et al., *An Investigation into the Physics of
Blowing Polysilicon Fuses*, 62nd European Study Group with Industry, Limerick
2008 (<https://miis.maths.ox.ac.uk/201/1/analog-1.pdf>). A workshop report, not
peer-reviewed, on a WSi/poly dog-bone fuse (1.5 um x 0.35 um neck) in a
different process. Its numbers are a **reference shape, not a gf180 value**, and
nothing below changes a ratified spec row (A1-A6). Report figures are as quoted
in the issue; the PDF was not re-read here.

**Program path (A2, A3).** The primary comparison is the PDK, and the PDK
documents no program current, pulse width or voltage (the model comment says
"6V/(5V)" only; spec 1.2). So there is no documented spec to measure margin
against; A2 (>= 10 mA) and A3 (10 us, 1-100 us) remain assumptions. As a shape
check only:

| Quantity | Report (reference shape) | Committed gf180 record |
|---|---|---|
| Supply | 6 V applied | 4.5 / 5.0 / 5.5 V (A1) |
| Peak current | about 90 mA, rise in <= 1 ns | Select-device sweep, ideal gate drive: 11.99 mA minimum (ss, 125 C, 4.5 V, 260 ohm), 13.66 mA at 200 ohm, 28.25 mA maximum (ff, -40 C, 5.5 V, 140 ohm), 60 um select device (`sim/program-select/records/20261023T174839Z-f6eeac7/record.json`). Full program path (`efuse_coldrv`, `efuse_rowdrv`, `efuse_ls`, `efuse_bitcell`): 10.87 mA minimum (ss, 125 C, 4.5 V / 2.97 V, 260 ohm), 12.39 mA at 200 ohm, 26.22 mA maximum (ff, -40 C, 5.5 V / 3.63 V, 140 ohm) (`sim/corner-verification/records/20261123T205019Z-f6eeac7/record.json`). One current per point, no waveform |
| Pulse | upper half about 40 ns wide, whole blow about 500 ns | 10 us nominal, 1-100 us (A3), RTL only (`sim/controller-fv/`); no analog result depends on it |

The committed current is roughly 8 times below the report's peak (26.22 mA maximum of the full path against about 90 mA) and the
committed pulse is orders of magnitude longer, so the shapes differ. The report's
fuse is a different material, geometry and process, so neither difference says
the gf180 path is short or long on margin. A2 is neither tightened nor relaxed
here. What would settle it is the documented programming condition of the PDK
eFuse or its `gf180mcu_re_efuse` macros (not installed, spec 1.2) or a silicon
measurement; both remain open.

**Multi-pulse or weak-pulse programming.** Open and unmeasured. The report does
not test it and its melt-then-pinch mechanism suggests sub-melt pulses do little.
No design, simulation or controller change is made for it.

**Retention and re-connection.** The report observes needle growth after 1000 h
at 125 C under bias. The plan item and how the sense-margin assumptions cover a
partly re-connected fuse are in [`retention-plan.md`](retention-plan.md).

**Geometry.** The `EF.*` rules fix the fuse as exact values (width 0.18 um
EF.02, length 1.26 um EF.03, total Poly2 length 5.53 um EF.21; spec 1.1), so no
midpoint-narrowing freedom exists in the cell. The report's neck (1.5 x 0.35 um)
is not the PDK geometry.
