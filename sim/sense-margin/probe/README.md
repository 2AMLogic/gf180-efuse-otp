# Single-corner comparator probes (issue 77)

Local single-unit `ngspice -b` runs (one corner each, not a grid), built from the
decks in `records/20261030T223615Z-f6eeac7/` (old comparator sizes inline).

| Deck | Corner | What it shows |
|---|---|---|
| `probe_rf260.cir`, `probe_rf630.cir` | typical / 25 C / 3.30 V | Old sizes. `clkn` falls 3.3 V -> 0 (clocking is fine, not a bench-edge problem). `sbl` ~0.2 V, tail ~2.6 V, `cp`/`cn` both ~2.1 V: latch never regenerates. |
| `v_mx8_*`, `v_pair2_*`, `v_both_*` | typical / 25 C / 3.30 V | Latch NMOS 2u -> 8u, input pair 8u -> 2u, both. Each regenerates to the correct bit (260 ohm -> 0, 630 ohm -> 1). Root cause: the on-state PMOS input pair out-pulls the 2u latch. `both` is what the schematic now carries. |
| `probe_new_ff_rf140.cir` / `_100p.cir` | ff / 25 C / 3.30 V | New sizes, 140 ohm. Same deck at a 20 ps vs 100 ps step gives opposite decisions: the 100 ps step under-resolves the 200 ps edge and its 40-60 mV kickback. `run.sh` now uses 20 ps. |

Decks are probes, not results: the evidence of record is `records/`.

## Intact-edge failure trace and input-pair area (issue 77, second increment)

The resized comparator (2u/0.28u pair) latched the wrong bit at full swing in 51 of 540 intact-edge
Monte Carlo samples (`sim/sense-mc/records/20261105T062142Z-f6eeac7`). Reading that record's
`yield/intact.samples.json`: every failure is `decision_margin` about -0.5 (a resolved, wrong
decision, not a non-regenerating latch), while the analog `margin_v` of the failing samples is
+13 to +36 mV, all positive. The failure rate falls monotonically with the sample's analog margin
(6/21 below 15 mV, 12/78 at 15-20 mV, 19/142 at 20-25 mV, 9/136 at 25-30 mV, 5/137 at 30-40 mV,
0/26 above 40 mV) and the corners with the smallest mean margin (125 C, 2.97 V) fail most. Root
cause: comparator input-referred mismatch offset, set by the input pair's gate area (0.56 um^2),
is of the same order as the 12-50 mV signal. It is a design sizing effect, not a bench or clocking
effect (`clkn` swings fully, see above).

| Deck | Corner | What it shows |
|---|---|---|
| `new_1p12_260.cir`, `new_1p12_630.cir` | typical / 25 C / 3.30 V | Input pair 4u/1.12u (8x area; drive about half of 2u/0.28u so it stays weaker than the 8u latch). 260 ohm: `cp` 0.04 V, `cn` 3.19 V; 630 ohm: `cp` 3.19 V, `cn` 0.04 V. Latch regenerates to opposite bits. |

Result of record: `sim/sense-margin/records/20261105T071054Z-f6eeac7` and
`sim/sense-mc/records/20261105T071340Z-f6eeac7` (see `sim/sense-mc/README.md`).
