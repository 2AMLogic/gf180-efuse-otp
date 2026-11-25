# sense-breakeven

Programmed-resistance sweep through the committed `efuse_sense` (with `efuse_comp`), to
find the fuse resistance at which `v(sbl) - v(sref)` crosses zero. Same deck
(`sim/sense-margin/sense.cir.in`), measurements and decision-0005 grid (45 corners) as
`sim/sense-margin`; the fuse stand-in is swept 300, 340, ... 540 ohm against the ideal 400 ohm
reference (A6) and against the committed physical `XRref` (`ppolyf_u`).

```sh
sim/sense-breakeven/run.sh --dry-run   # validates the 14 requests; runs no corner
sim/sense-breakeven/run.sh             # batch only (--wait-for-capacity 600); writes a record
```

The break-even per corner is a linear interpolation between the two swept points that bracket
the sign change; the 40 ohm step is the interpolation interval. A corner with no single sign
change gets `break_even_ohm: null` and the record is `complete: false`. Same assumptions as
sense-margin (A4-A6, A8); reference tolerance and comparator offset are not simulated. Records
are append-only.

## Record `records/20261125T093522Z-f6eeac7/record.json`

14 batch jobs, 45 corners each. Break-even programmed resistance over the 45 corners:

| Reference | Min | Max | Spread |
|---|---|---|---|
| ideal 400 ohm | 400.69 ohm (fs, -40 C, 3.63 V) | 400.72 ohm (sf, 125 C, 2.97 V) | 0.03 ohm |
| physical `XRref` | 327.91 ohm (ff, 125 C, 3.63 V) | 471.99 ohm (ss, -40 C, 2.97 V) | 144.08 ohm |

Under the physical reference a programmed fuse that drifts below about 472 ohm can read as
intact at the worst corner; the 630 ohm A5 edge keeps about 158 ohm of headroom there.
fs/sf resistor corners hold the typical sheet rho (A8).
