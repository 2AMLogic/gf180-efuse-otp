"""The comparator decision shared by the sense benches.

One definition of "resolved" and "decision bit" so sim/sense-margin and
sim/sense-breakeven cannot drift apart:

  resolved      |v(cp) - v(cn)| >= 0.5 * vdd33   (the latch left the metastable band)
  decision_bit  1 if v(sense_out) >= 0.7 * vdd33, 0 if <= 0.3 * vdd33, else None
  decision_ok   resolved AND decision_bit == expected_bit

Both thresholds are inclusive. finite(x) accepts finite int/float readings and
excludes bool; a missing or non-finite measurement is never a decision:
resolved is False, the bit is None and decision_ok is False.
"""
import math

RESOLVED_DEF = "|v(cp) - v(cn)| >= 0.5 * vdd33 after the edge"
DECISION_BIT_DEF = "1 if v(sense_out) >= 0.7 vdd33, 0 if <= 0.3 vdd33, else null"

RESOLVE_FRAC = 0.5
HIGH_FRAC = 0.7
LOW_FRAC = 0.3


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def decide(cp, cn, so, vdd, expected_bit):
    """Return (resolved, decision_bit, decision_ok) for one corner reading."""
    if not all(finite(v) for v in (cp, cn, so, vdd)):
        return False, None, False
    resolved = abs(cp - cn) >= RESOLVE_FRAC * vdd
    bit = 1 if so >= HIGH_FRAC * vdd else (0 if so <= LOW_FRAC * vdd else None)
    return resolved, bit, bool(resolved and bit == expected_bit)
