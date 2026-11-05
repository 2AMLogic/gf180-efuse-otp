# sense-mc

Sense-path Monte Carlo campaign for T1 item 6 (statistical claims), analog partition. The
ratified "Sense margin" row (`spec/efuse-otp.md` section 2) asks for positive margin over the
A4/A5 ranges "including reference tolerance and comparator offset". A corner matrix cannot
show that (`signoff/design-evidence-tiers.md`, item 6); this is the Monte Carlo layer on top of
the `sim/sense-margin` bench (same DUT extraction, same deck, same grid).

```sh
sim/sense-mc/run.sh --dry-run        # validates the four requests with `klt sim --dry-run`; runs nothing
sim/sense-mc/run.sh                  # submits to the batch fleet, grades with `klt yield`, writes a record
sim/sense-mc/check-repro.sh <record> # re-runs one sample at one corner locally and compares it with the record
```

## What it runs

Four `klt sim` requests, submitted with `klt sim --batch-set` (batch only; a refused or
failed submit stops the script and is never re-run locally), each over the decision-0005 grid
of 45 corners (5 process x -40/25/125 C x vdd33 2.97/3.30/3.63 V), with `monte_carlo` seeded
(`seed` 36036, `seed_scope: point`, `vary: mismatch`):

| Request | Fuse | Reference | Samples/corner | Role |
|---|---|---|---|---|
| `mc_intact_rf260_rr400` | 260 ohm (A4 upper edge) | 400 ohm (A6) | 12 | nominal |
| `mc_prog_rf630_rr400` | 630 ohm (A5 lower edge) | 400 ohm | 12 | nominal |
| `ctl_intact_rf260_rr200` | 260 ohm | 200 ohm | 6 | negative control: reference inside the intact range |
| `ctl_prog_rf630_rr1000` | 630 ohm | 1000 ohm | 6 | negative control: reference above the programmed range |

The edges are the binding values: the other A4/A5 points sit farther from the reference
(`sim/sense-margin` records every point). The fuse value is not varied inside the Monte Carlo.

Two sources of variation:

- **Comparator / mirror offset**: the PDK's MOS mismatch (`monte_carlo.mismatch_scale: 1`,
  i.e. `sw_stat_mismatch=1`), active on every MOS device of `efuse_sense` and `efuse_comp`.
- **Reference tolerance**: klt-injected Gaussian multiplier on `Rref`
  (`monte_carlo.injected`, `mc_inj_rref_r`). The PDK does not mismatch-model the netlist's
  ideal reference resistor, and the gf180mcu poly-resistor mismatch is structurally disabled in
  the model, so the tolerance is design-owned.

## Measurements and limits

| Measurement | Limit | Meaning |
|---|---|---|
| `margin_v` (cited) | `> 0` V | `v(sref) - v(sbl)` (intact) or `v(sbl) - v(sref)` (programmed) just before the clock edge; positive is the correct side of the reference. The ratified row's limit. |
| `decision_margin` (reported, **not cited**) | `>= 0.2` | latched `sense_out / vdd33` past the 0.5 midpoint, signed for the expected bit (the 0.7 / 0.3 rails of `sim/sense-margin`) |

Both carry `spec_row: P10`. `klt yield` runs with `--min-samples 200 --target-ci-halfwidth 0.01`
at 95 %; `klt yield-samples` pairs each nominal with its control. The yield step uses the pinned
`klayout-tools[yield]` (`signoff/klt-pin.txt`) through `uvx`; the fleet runs `klt sim`.

## Assumptions (flagged in each record)

- A4, A5, A6 as in `spec/efuse-otp.md` (only the 200 ohm and 900 ohm points are documented).
- **A7, new, not in the spec: reference relative sigma 0.05.** No documented source exists for the
  reference tolerance; it is a stated working value, not a fact. Adopting a value is a spec change
  (decision record); this record does not make one.
- Not modelled: bitline capacitance, column-mux leakage, supply noise, post-layout parasitics.

## Result and what it does and does not show

`records/20261105T053444Z-f6eeac7/record.json` has the numbers. In short:

- `margin_v`: yield 1.0 (Clopper-Pearson 95 % lower bound 0.993) over 540 samples per population,
  sample size `sufficient`, negative control `detected` (control yield 0.0) for both populations.
  The smallest sampled margin is 12 mV (intact, ss / 125 C / 2.97 V) and 22 mV (programmed,
  typical / 125 C / 2.97 V).
- `decision_margin` is **not** a pass and is not cited. The committed `sim/sense-margin` record
  already shows the comparator not resolving for a resistive fuse (the latched output reads 0 at nearly
  every corner for every fuse short of open). Here the programmed population's decision yield is 0.05 and the intact
  population's negative control is `not_detected` (the output cannot move, so it cannot discriminate).
  **Comparator offset is therefore not established by this record**; the analog margin includes the
  reference tolerance and the mirror-branch mismatch, but not the comparator's own offset.
- So item 6 (analog) grades `met` on campaign discipline (recorded seed and sample count, sufficient
  samples, detected negative control, corners combined with MC). That grade is not a statement that
  the ratified sense-margin row holds.

Records are append-only; `run.sh` refuses to reuse a directory. `klt.err`, `set-report.json` and the
sample sets carry the absolute paths the tools wrote, as in `sim/sense-margin/records`.

## Path normalisation (PR #78 review)

The first commit of this record stored absolute builder-worktree paths in `set-report.json`,
`sets/set-manifest.json` and `yield/*.json`, which no other checkout can resolve (klt could not
verify the samples hash in CI). `run.sh` now runs klt from the repo root with repo-relative record
paths. For this record (never on `main`), the stored path prefix was stripped and the `yield/`
outputs were regenerated with `klt yield-samples` / `klt yield` from the unchanged fleet reports
under `sets/*/report.json`; no grid was re-run and the raw fleet reports are untouched.

## Re-run on the resized comparator (issue 77)

The comparator latch was resized and the bench timestep changed (`tran` step 100p -> 20p, as in
`sim/sense-margin/run.sh`); `run.sh` now uses 20p. The record above predates that and is kept
untouched as evidence of the old DUT. New record: `records/20261105T062142Z-f6eeac7/record.json`
(same seed, grid, samples and assumptions A4-A7; 4 batch jobs in `remote_job_ids`).

- `margin_v` (cited): yield 1.0, 540 samples per population, sufficient, negative control `detected`;
  smallest margin 12 mV (intact, ss / 125 C / 2.97 V) and 22 mV (programmed, typical / 125 C / 2.97 V).
- `decision_margin` (not cited), now a measured result rather than a non-resolving latch:
  intact yield 0.906 (95 % CI 0.878-0.929; 51 of 540 samples fail, 29 of 45 corners affected,
  sample size `insufficient`, control `detected`); programmed yield 0.991 (CI 0.979-0.997; 5 of 540
  fail, sample size `sufficient`, control `detected`).
- **The resized comparator does not meet a resolved-decision yield of 1.0 under mismatch at the
  intact edge (260 ohm vs a 400 ohm reference).** This is the comparator offset the ratified row asks
  to include; it is not a pass, and nothing here relaxes the spec. The decision criterion's sample
  size (about 3300 needed at that yield) was not reached.
- A7 (reference sigma 0.05) remains an assumption with no documented source.

## Re-run with a larger comparator input pair (issue 77, second increment)

Trace and root cause: `sim/sense-margin/probe/README.md`. The intact-edge failures of the previous
record were resolved wrong decisions whose rate tracks the analog margin, i.e. comparator
input-referred offset. `M1`/`M2` of `efuse_comp` changed 2u/0.28u -> 4u/1.12u (8x gate area).
New record: `records/20261105T071340Z-f6eeac7/record.json` (same seed, grid, samples and
assumptions A4-A7; previous records untouched). Batch only.

- `margin_v` (cited): yield 1.0, 540 samples per population, sufficient, control `detected`.
- `decision_margin` (not cited), intact edge: yield 0.9963 (95 % CI 0.9867-0.9996; 2 of 540 fail:
  typical / 2.97 V / 125 C, margin 14.6 mV, and ss / 3.63 V / 125 C, margin 14.1 mV), sample size
  `sufficient`, control `detected` (0.056). Was 0.906.
- `decision_margin`, programmed edge: yield 1.0 (CI lower bound 0.9932), `sufficient`, control `detected`.
- Corner matrix, `sim/sense-margin/records/20261105T071054Z-f6eeac7`: 45 corners for each of
  140/200/260/630/900/open ohm, `decision_correct_everywhere` true, no unresolved point.

**Residual:** comparator offset is now covered by a measured result, but the intact edge is not at
yield 1.0: two 125 C samples with about 14 mV of analog margin still decide wrong. Not a pass of
a 1.0 criterion and nothing here relaxes the spec; the smallest analog margin (12 mV) is the
limit, so a further gain needs a larger pair or more signal. A7 is still an assumption.

`design/efuse_otp_array.spice` was edited by hand on the two `XM1`/`XM2` lines (matching the
schematic). `design/regen-netlist.sh` on this host with the pinned klt rewrites ~230 unrelated lines
(drops `pd=`/`ps=` on every device), and `--check` already reports that drift on unmodified `main`,
so the regenerated file was not committed. The T1 item 1 analog attestation hashes are not
refreshed here.

## Re-run with an 8u/2.24u comparator input pair (issue 77, third increment)

The two residual intact-edge failures of the previous record are the input-referred offset of the
4u/1.12u pair (trace: `sim/sense-margin/probe/README.md`). `M1`/`M2` of `efuse_comp` changed to
8u/2.24u (4x gate area, same W/L). New record: `records/20261105T084326Z-f6eeac7/record.json`
(same seed, grid, samples and assumptions A4-A7; previous records untouched). Batch only; the
single-unit probes in `sim/sense-margin/probe/` are the only local runs.

- `margin_v` (cited): yield 1.0, 540 samples per population, sufficient, control `detected`;
  smallest margin 12 mV (intact, ss / 125 C / 2.97 V).
- `decision_margin` (not cited), intact edge: yield 1.0000 (95 % CI lower bound 0.9932), 0 of 540
  fail, sample size `sufficient`, control `detected` (control yield 0.0037). Was 0.9963.
- `decision_margin`, programmed edge: yield 1.0000, `sufficient`, control `detected`.
- Corner matrix, `sim/sense-margin/records/20261105T083938Z-f6eeac7`: 45 corners for each of
  140/200/260/630/900/open ohm, `decision_correct_everywhere` true, no unresolved point.

A 1.0 yield over 540 samples bounds the failure rate below about 0.7 % at 95 % confidence; it does
not show zero failures. A7 (reference sigma 0.05) is still an assumption with no documented source,
as are A4-A6. The item 1 analog and item 2 analog attestations, the array GDS and the re-graded
record are refreshed for the new netlist (`design/regen-netlist.sh --check` passes on the pinned klt).
