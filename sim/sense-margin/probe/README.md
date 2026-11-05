# Single-corner comparator probes (issue 77)

Local single-unit `ngspice -b` runs (one corner each, not a grid), built from the
decks in `records/20261030T223615Z-f6eeac7/` (old comparator sizes inline).

| Deck | Corner | What it shows |
|---|---|---|
| `probe_rf260.cir`, `probe_rf630.cir` | typical / 25 C / 3.30 V | Old sizes. `clkn` falls 3.3 V -> 0 (clocking is fine, not a bench-edge problem). `sbl` ~0.2 V, tail ~2.6 V, `cp`/`cn` both ~2.1 V: latch never regenerates. |
| `v_mx8_*`, `v_pair2_*`, `v_both_*` | typical / 25 C / 3.30 V | Latch NMOS 2u -> 8u, input pair 8u -> 2u, both. Each regenerates to the correct bit (260 ohm -> 0, 630 ohm -> 1). Root cause: the on-state PMOS input pair out-pulls the 2u latch. `both` is what the schematic now carries. |
| `probe_new_ff_rf140.cir` / `_100p.cir` | ff / 25 C / 3.30 V | New sizes, 140 ohm. Same deck at a 20 ps vs 100 ps step gives opposite decisions: the 100 ps step under-resolves the 200 ps edge and its 40-60 mV kickback. `run.sh` now uses 20 ps. |

Decks are probes, not results: the evidence of record is `records/`.
